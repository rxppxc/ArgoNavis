"""La aplicación: el ciclo de vida, los middlewares, las rutas, la salud y el frontend
compilado. Los manejadores de errores están en api/manejadores.py y los middlewares
propios, en api/middleware.py (auditoría del 2026-11-14)."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.formparsers import MultiPartParser
from app.api.manejadores import registrar_manejadores
from app.api.middleware import CodigoDePedido, EsquemaAlDia, TopeDelCuerpo
from app.core.config import obtener_configuracion
from app.core.rate_limit import limiter
from app.core.registro import configurar_registro
from app.core.security import CABECERA_CAMBIO_CONTRASENA
from app.api.v1 import auth, admin, tramites, solicitudes, verificacion, catalogos, bitacora, pendientes
# Registrar todos los modelos en el registry del ORM (relaciones por nombre).
from app.domain.models import rol, tramite, catalogo, solicitud, correo, boleta  # noqa: F401
from app.infrastructure.cola_correos import tarea_correos
from app.infrastructure.database import motor_bd
from app.infrastructure.esquema import revisar_esquema
from app.infrastructure.tareas import tarea_archivo, tarea_vencimientos

configurar_registro()
logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    """Ciclo de vida de la aplicación: deja corriendo en segundo plano la tarea
    que expira las solicitudes con plazos vencidos y la que cuida el archivo
    (infrastructure/tareas.py), y la que reintenta los correos pendientes
    (infrastructure/cola_correos.py).
    El esquema de BD lo maneja Alembic (`alembic upgrade head`: migrate.bat, o el
    entrypoint del contenedor antes de levantar uvicorn). Si a la base le falta algo
    que el código usa, lo dice el log, la API responde 503 con el motivo y las tareas
    no arrancan, porque fallarían en cada vuelta (infrastructure/esquema.py, 2026-11-17).
    Al apagar (Ctrl+C / SIGTERM) cancela las tareas limpiamente y cierra las
    conexiones del pool (si no, PostgreSQL las ve cortarse de golpe)."""
    if configuracion.MAIL_USERNAME and not (configuracion.MAIL_USAR_SSL or configuracion.MAIL_STARTTLS):
        logger.warning("Correo con usuario y sin TLS: la contraseña del SMTP viaja en claro "
                       "(activa MAIL_STARTTLS o MAIL_USAR_SSL).")
    app.state.esquema_faltante = await revisar_esquema(motor_bd)
    tareas = [] if app.state.esquema_faltante else [
        asyncio.create_task(tarea_vencimientos()), asyncio.create_task(tarea_correos()),
        asyncio.create_task(tarea_archivo()),
    ]
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


registrar_manejadores(aplicacion)

# El primero que se agrega queda por dentro de todos: el 413 lleva CORS y el código de pedido.
aplicacion.add_middleware(TopeDelCuerpo)
# Con la base sin migrar, 503 con el motivo (también con CORS y el código de pedido).
aplicacion.add_middleware(EsquemaAlDia)

# Cada archivo de un envío pasa al disco temporal desde los 64 KB (Starlette deja en
# memoria cada uno de hasta 1 MB): un envío de 142 archivos de casi 1 MB ocupaba ~140 MB
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
    marca el servicio como no sano (antes respondía «ok» con la BD caída). También
    503 si al arrancar a la base le faltaba algo que el código usa (sin migrar)."""
    ahora = time.monotonic()
    if ahora - _salud["momento"] >= _SALUD_VIGENCIA_S:
        # Antes de consultar: las que lleguen mientras tanto usan el resultado anterior
        # (con la BD caída, cada consulta tarda hasta _SALUD_ESPERA_S).
        _salud["momento"] = ahora
        _salud["bd_ok"] = await _bd_responde()
    if not _salud["bd_ok"]:
        response.status_code = 503
        return {"estado": "sin base de datos", "aplicacion": configuracion.APP_NAME}
    if getattr(aplicacion.state, "esquema_faltante", None):
        response.status_code = 503
        return {"estado": "base de datos sin migrar", "aplicacion": configuracion.APP_NAME}
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
