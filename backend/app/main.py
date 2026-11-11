import asyncio
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolAgotado
from starlette.formparsers import MultiPartParser
from app.core.config import obtener_configuracion
from app.core.rate_limit import limiter
from app.core.registro import configurar_registro, id_pedido
from app.core.security import CABECERA_CAMBIO_CONTRASENA
from app.api.v1 import auth, admin, tramites, solicitudes, verificacion, catalogos, bitacora, pendientes
# Registrar todos los modelos en el registry del ORM (relaciones por nombre).
from app.domain.models import rol, tramite, catalogo, solicitud, correo  # noqa: F401
from app.domain.services.solicitud_service import TOPE_CUERPO_ENVIO_MB
from app.infrastructure.almacenamiento import TAMANO_MAXIMO_MB
from app.infrastructure.cola_correos import tarea_correos
from app.infrastructure.database import motor_bd
from app.infrastructure.tareas import tarea_vencimientos

configurar_registro()
logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    """Ciclo de vida de la aplicación: deja corriendo en segundo plano la tarea
    que expira las solicitudes con plazos vencidos (infrastructure/tareas.py) y
    la que reintenta los correos pendientes (infrastructure/cola_correos.py).
    El esquema de BD lo maneja Alembic (`alembic upgrade head`, corrido por el
    entrypoint del contenedor antes de levantar uvicorn).
    Al apagar (Ctrl+C / SIGTERM) cancela las tareas limpiamente y cierra las
    conexiones del pool (si no, PostgreSQL las ve cortarse de golpe)."""
    if configuracion.MAIL_USERNAME and not (configuracion.MAIL_USAR_SSL or configuracion.MAIL_STARTTLS):
        logger.warning("Correo con usuario y sin TLS: la contraseña del SMTP viaja en claro "
                       "(activa MAIL_STARTTLS o MAIL_USAR_SSL).")
    tareas = [asyncio.create_task(tarea_vencimientos()), asyncio.create_task(tarea_correos())]
    yield
    for tarea in tareas:
        tarea.cancel()
    for tarea in tareas:
        with suppress(asyncio.CancelledError):
            await tarea
    await motor_bd.dispose()


aplicacion = FastAPI(
    title="ARGO NAVIS - SNM API",
    version="3.0.0",
    description="Autorizaciones Marítimas (UCVMM) — Servicio Nacional de Migración",
    docs_url="/api/docs" if configuracion.APP_ENV == "development" else None,
    redoc_url="/api/redoc" if configuracion.APP_ENV == "development" else None,
    lifespan=ciclo_vida,
)

# Rate limiting (protección contra abuso de los endpoints públicos)
aplicacion.state.limiter = limiter


@aplicacion.exception_handler(RateLimitExceeded)
async def demasiadas_solicitudes(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 con `detail`, como el resto de los errores (el frontend lo muestra tal cual)."""
    logger.warning("[rate limit] %s %s superó %s", request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados intentos en poco tiempo. Espera unos minutos e intenta de nuevo."},
    )


@aplicacion.exception_handler(IntegrityError)
async def conflicto_de_integridad(request: Request, exc: IntegrityError) -> JSONResponse:
    """Una regla de la BD (llave foránea, valor único) rechazó el cambio: 409
    en vez de 500. Los servicios deberían validarlo antes; si llega aquí, el
    log dice qué restricción fue, para agregar esa validación."""
    restriccion = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
    logger.warning("[bd] La restricción %s rechazó %s %s", restriccion or "?", request.method, request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "No se pudo completar: hay registros relacionados que lo impiden."},
    )


_BD_NO_RESPONDE = {"detail": "La base de datos no respondió a tiempo. Intenta de nuevo en unos segundos."}


def _no_disponible(contenido: dict) -> JSONResponse:
    return JSONResponse(status_code=503, content={**contenido, "codigo": id_pedido.get()},
                        headers={"Retry-After": "5"})


@aplicacion.exception_handler(PoolAgotado)
async def sin_conexiones_libres(request: Request, exc: PoolAgotado) -> JSONResponse:
    """Todas las conexiones del pool ocupadas durante BD_POOL_ESPERA: 503 con
    motivo (y el aviso en el log para dimensionar el pool) en vez de un 500."""
    logger.error("[bd] Sin conexiones libres en el pool (%s %s): revisa BD_POOL o las consultas lentas.",
                 request.method, request.url.path)
    return _no_disponible({"detail": "El sistema está muy ocupado. Intenta de nuevo en unos segundos."})


def _es_falla_de_disponibilidad(exc: DBAPIError) -> bool:
    """La BD no está o cortó: conexión caída o rechazada, o una consulta
    cancelada por BD_TIEMPO_MAXIMO_CONSULTA (SQLSTATE 57014). Un error de
    programación (SQL mal armado) no es esto: ese sigue siendo un 500."""
    causa = getattr(exc.orig, "__cause__", None) or exc.orig
    return (isinstance(exc, (OperationalError, InterfaceError)) or exc.connection_invalidated
            or getattr(causa, "sqlstate", None) == "57014")


@aplicacion.exception_handler(DBAPIError)
async def error_de_base_de_datos(request: Request, exc: DBAPIError) -> JSONResponse:
    """Errores de la BD que no son una regla rechazada (esas son IntegrityError,
    arriba). Si la BD no responde, 503 con motivo: el frontend lo muestra y se
    puede reintentar. Lo demás es un defecto: 500, con el detalle en el log."""
    if _es_falla_de_disponibilidad(exc):
        logger.error("[bd] La base de datos no respondió en %s %s: %s",
                     request.method, request.url.path, type(exc.orig).__name__)
        return _no_disponible(_BD_NO_RESPONDE)
    logger.error("[bd] Error en %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor.", "codigo": id_pedido.get()})


@aplicacion.exception_handler(ConnectionError)
async def servicio_no_disponible(request: Request, exc: ConnectionError) -> JSONResponse:
    """Una conexión rechazada o cortada (p. ej. PostgreSQL apagado: asyncpg la
    reporta así al conectar). 503 con motivo en vez de un 500."""
    logger.error("[red] Conexión rechazada en %s %s: %s", request.method, request.url.path, exc)
    return _no_disponible(_BD_NO_RESPONDE)

TOPE_CUERPO_MB = 1   # el resto de la API: sus cuerpos son JSON de pocos KB
_RUTA_DE_ENVIO = re.compile(r"/api/v1/solicitudes(/[0-9]+)?/?")


def _es_envio(metodo: str, ruta: str) -> bool:
    """Crear (POST /solicitudes) o corregir (PUT /solicitudes/{id}): llevan juntos
    todos los archivos de la solicitud."""
    return metodo in ("POST", "PUT") and _RUTA_DE_ENVIO.fullmatch(ruta) is not None


def tope_del_cuerpo(metodo: str, ruta: str) -> int:
    """Bytes que admite el cuerpo de una petición."""
    return (TOPE_CUERPO_ENVIO_MB if _es_envio(metodo, ruta) else TOPE_CUERPO_MB) * 1024 * 1024


def _cuerpo_demasiado_grande(metodo: str, ruta: str, tope: int) -> HTTPException:
    logger.warning("[tope] %s %s: el cuerpo pasa de %d MB", metodo, ruta, tope // (1024 * 1024))
    if _es_envio(metodo, ruta):
        detalle = (f"El envío pesa más de {TOPE_CUERPO_ENVIO_MB} MB, lo máximo para una solicitud. "
                   f"Cada archivo puede pesar hasta {TAMANO_MAXIMO_MB} MB.")
    else:
        detalle = "El contenido de la petición supera el máximo permitido."
    return HTTPException(status_code=413, detail=detalle)


class TopeDelCuerpo:
    """Corta un cuerpo más grande que su tope sin leerlo (revisión de recursos del 2026-11-10).

    FastAPI lee el cuerpo entero ANTES de comprobar la sesión y el límite de envíos:
    sin tope, cualquiera, sin cuenta, hacía que el backend leyera cientos de MB por
    petición en cualquier ruta, también en el login (un JSON va entero a la memoria; un
    formulario, al disco temporal). Con Content-Length se responde 413 sin leer nada; sin
    él (envío por partes), se cuenta lo que llega y se corta al pasar el tope. nginx tiene
    los mismos topes (frontend/nginx.conf), pero en Windows el backend atiende solo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        metodo, ruta = scope["method"], scope["path"]
        tope = tope_del_cuerpo(metodo, ruta)
        declarado = dict(scope["headers"]).get(b"content-length", b"")
        if declarado.isdigit() and int(declarado) > tope:
            error = _cuerpo_demasiado_grande(metodo, ruta, tope)
            await JSONResponse(status_code=error.status_code, content={"detail": error.detail})(scope, receive, send)
            return

        leidos = 0

        async def recibir():
            nonlocal leidos
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                leidos += len(mensaje.get("body", b""))
                if leidos > tope:
                    # FastAPI deja pasar la HTTPException que sale de leer el cuerpo: es un 413 con detail.
                    raise _cuerpo_demasiado_grande(metodo, ruta, tope)
            return mensaje

        await self.app(scope, recibir, send)


# El primero que se agrega queda por dentro de todos: el 413 lleva CORS y el código de pedido.
aplicacion.add_middleware(TopeDelCuerpo)

# Cada archivo de un envío pasa al disco temporal desde los 64 KB (Starlette deja en
# memoria cada uno de hasta 1 MB): un envío de 141 archivos de casi 1 MB ocupaba ~140 MB
# del proceso mientras se procesaba; así, ~9 MB. Cuenta para el límite de memoria del
# contenedor (docker-compose-prod.yml). Lo comprueba tests/test_recursos.py.
MultiPartParser.spool_max_size = 64 * 1024

# CORS: en desarrollo permite el frontend de Vite (no usamos "*" para poder enviar credenciales).
# En producción el frontend viene del mismo servidor → solo el FRONTEND_URL configurado.
_cors_origins = list({
    origen for origen in (configuracion.FRONTEND_URL, configuracion.APP_URL) if origen
})
aplicacion.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition", CABECERA_CAMBIO_CONTRASENA],
)

_CODIGO_VALIDO = re.compile(r"[A-Za-z0-9._-]{8,64}")


class CodigoDePedido:
    """Cada pedido lleva un código (X-Request-ID): va en cada línea del log, en la
    respuesta y en el cuerpo de los errores 5xx, que el frontend muestra. Quien
    reporta un error dice el código y en el log está su traza (revisión del
    2026-11-08; antes había que adivinar cuál de todos los errores era el suyo).

    Un error sin controlar se registra aquí, con el código y la traza completa, y
    se responde un 500 con el código. ASGI puro, no BaseHTTPMiddleware: el código
    acompaña también a las tareas en segundo plano del pedido (los correos)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        entrante = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        codigo = entrante if _CODIGO_VALIDO.fullmatch(entrante) else secrets.token_hex(6)
        marca = id_pedido.set(codigo)
        empezada = False

        async def enviar(mensaje):
            nonlocal empezada
            if mensaje["type"] == "http.response.start":
                empezada = True
                mensaje["headers"] = [*mensaje.get("headers", []), (b"x-request-id", codigo.encode())]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            logger.exception("Error no controlado en %s %s", scope.get("method"), scope.get("path"))
            if empezada:
                raise
            respuesta = JSONResponse(status_code=500, content={"detail": "Error interno del servidor.", "codigo": codigo})
            await respuesta(scope, receive, enviar)
        finally:
            id_pedido.reset(marca)


# El último que se agrega queda por fuera de todos: el código cubre también a CORS.
aplicacion.add_middleware(CodigoDePedido)

aplicacion.include_router(auth.enrutador,         prefix="/api/v1")
aplicacion.include_router(admin.enrutador,        prefix="/api/v1")
aplicacion.include_router(tramites.enrutador,     prefix="/api/v1")
aplicacion.include_router(solicitudes.enrutador,  prefix="/api/v1")
aplicacion.include_router(verificacion.enrutador, prefix="/api/v1")
aplicacion.include_router(catalogos.enrutador,    prefix="/api/v1")
aplicacion.include_router(bitacora.enrutador,     prefix="/api/v1")
aplicacion.include_router(pendientes.enrutador,   prefix="/api/v1")


# La respuesta de la BD se reusa unos segundos: /api/health es pública (la usan
# el healthcheck de Docker y un balanceador) y no debe servir para cargar la BD.
_SALUD_VIGENCIA_S = 5
_SALUD_ESPERA_S   = 3
_salud = {"momento": float("-inf"), "bd_ok": False}


async def _bd_responde() -> bool:
    async def consultar() -> None:
        async with motor_bd.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
    try:
        await asyncio.wait_for(consultar(), timeout=_SALUD_ESPERA_S)
        return True
    except Exception as exc:   # cualquier falla de la BD es "no responde"; el motivo, al log
        logger.warning("[salud] La base de datos no responde: %s", type(exc).__name__)
        return False


@aplicacion.get("/api/health")
async def verificar_salud(response: Response):
    """Viva y con base de datos. Si la BD no responde, 503: así el healthcheck
    marca el servicio como no sano (antes respondía «ok» con la BD caída)."""
    ahora = time.monotonic()
    if ahora - _salud["momento"] >= _SALUD_VIGENCIA_S:
        # Antes de consultar: las que lleguen mientras tanto usan el resultado anterior
        # (con la BD caída, cada consulta tarda hasta _SALUD_ESPERA_S).
        _salud["momento"] = ahora
        _salud["bd_ok"] = await _bd_responde()
    if not _salud["bd_ok"]:
        response.status_code = 503
        return {"estado": "sin base de datos", "aplicacion": configuracion.APP_NAME}
    return {"estado": "ok", "aplicacion": configuracion.APP_NAME}


# ── Servir el frontend compilado (npm run build) ──────────────────────────────
# Solo activo cuando existe la carpeta dist/. En dev se usa Vite directamente.
if _FRONTEND_DIST.exists():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        aplicacion.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    _RAIZ_DIST = _FRONTEND_DIST.resolve()
    # Las mismas cabeceras que pone nginx en Docker (ver frontend/nginx.conf),
    # para cuando el backend sirve el frontend directamente (start-backend-prod.bat).
    _CABECERAS_SPA = {
        # Solo corre código propio de ARGO NAVIS: sin scripts en línea, sin eval y sin
        # recursos de otros sitios (barrera ante un XSS: el token vive en localStorage).
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
            "frame-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        ),
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        # Sistema interno: que ningún buscador ni rastreador lo indexe (como nginx).
        "X-Robots-Tag": "noindex, nofollow",
    }

    @aplicacion.get("/{ruta_completa:path}", include_in_schema=False)
    async def servir_spa(ruta_completa: str):
        # Una ruta de la API que no existe es un 404, no la página del SPA.
        if ruta_completa == "api" or ruta_completa.startswith("api/"):
            raise HTTPException(status_code=404, detail="Recurso no encontrado.")
        # Defensa contra path traversal: resolver la ruta y verificar que el
        # resultado siga estando dentro de _FRONTEND_DIST. Si está fuera o si
        # no existe el archivo, se devuelve el index.html del SPA.
        if ruta_completa:
            try:
                archivo = (_FRONTEND_DIST / ruta_completa).resolve()
                archivo.relative_to(_RAIZ_DIST)
                if archivo.is_file():
                    return FileResponse(str(archivo), headers=_CABECERAS_SPA)
            except (ValueError, OSError):
                pass
        indice = _FRONTEND_DIST / "index.html"
        if indice.exists():
            # Sin hash en el nombre: que el navegador revalide para no quedarse
            # con un index.html que apunta al bundle de una versión anterior.
            return FileResponse(str(indice), headers={**_CABECERAS_SPA, "Cache-Control": "no-cache"})
        raise HTTPException(status_code=404, detail="Frontend no compilado.")
