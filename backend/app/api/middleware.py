"""Los middlewares propios (auditoría del 2026-11-14; hasta entonces, en main.py):
el tope del cuerpo de cada petición y el código de pedido. ASGI puro, no
BaseHTTPMiddleware: el código acompaña también a las tareas en segundo plano.

Lo que tiene que coincidir con nginx (frontend/nginx.conf): TOPE_CUERPO_MB,
TOPE_CUERPO_ENVIO_MB y _RUTA_DE_ENVIO (lo compara tests/test_recursos.py)."""
import logging
import re
import secrets

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.core.registro import id_pedido
from app.domain.services.solicitud_service import TOPE_CUERPO_ENVIO_MB
from app.infrastructure.almacenamiento import TAMANO_MAXIMO_MB

logger = logging.getLogger(__name__)

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


MENSAJE_ESQUEMA_ATRASADO = ("El sistema no está disponible: falta poner al día la base de datos. "
                            "Avisa al administrador del sistema.")


class EsquemaAlDia:
    """Mientras a la base le falte algo que el código usa, la API responde 503 con el
    motivo, que el frontend muestra (2026-11-17). Antes era un 500 «Error interno» en
    cada pedido, sin pista: el código se había puesto al día y la base no. Lo revisa el
    arranque (infrastructure/esquema.py), que deja la lista en `app.state.esquema_faltante`
    y en el log dice qué falta y qué hacer. /api/health lo dice por su cuenta."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        estado = getattr(scope.get("app"), "state", None)
        if (scope["type"] == "http" and scope["path"].startswith("/api/") and scope["path"] != "/api/health"
                and getattr(estado, "esquema_faltante", None)):
            respuesta = JSONResponse(status_code=503, content={"detail": MENSAJE_ESQUEMA_ATRASADO})
            await respuesta(scope, receive, send)
            return
        await self.app(scope, receive, send)


_CODIGO_VALIDO = re.compile(r"[A-Za-z0-9._-]{8,64}")


class CodigoDePedido:
    """Cada pedido lleva un código (X-Request-ID): va en cada línea del log, en la
    respuesta y en el cuerpo de los errores 5xx, que el frontend muestra. Quien
    reporta un error dice el código y en el log está su traza (revisión del
    2026-11-08; antes había que adivinar cuál de todos los errores era el suyo).

    Un error sin controlar se registra aquí, con el código y la traza completa, y
    se responde un 500 con el código."""

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
