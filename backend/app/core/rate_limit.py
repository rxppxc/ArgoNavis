"""Rate limiter compartido para endpoints públicos.

Usamos slowapi (basado en limits) con almacenamiento en memoria. Para
despliegues multi-proceso o multi-host, configurar `storage_uri` a Redis.

`limite_verificacion` (LIMITE_VERIFICACIONES_POR_MINUTO, por IP) limita la
verificación pública del QR. La variable vieja RATE_LIMIT_DOWNLOADS_PER_MINUTE
se sigue leyendo (ver core/config.py):
    @enrutador.get("/{codigo}")
    @limiter.limit(limite_verificacion)
    async def verificar_autorizacion(request: Request, codigo: str, ...):
        ...
"""
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import obtener_configuracion
from app.core.security import decodificar_token

_config = obtener_configuracion()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)


def clave_usuario(request: Request) -> str:
    """Clave del límite por cuenta (el `sub` del token, sin ir a la BD): sigue
    al usuario aunque cambie de IP. Sin token válido, la IP."""
    autorizacion = request.headers.get("Authorization", "")
    if autorizacion[:7].lower() == "bearer ":
        try:
            return f"usuario:{decodificar_token(autorizacion[7:]).get('sub')}"
        except HTTPException:
            pass
    return get_remote_address(request)


def limite_envios() -> str:
    """Envíos (crear o corregir una solicitud) por usuario y por hora."""
    n = _config.LIMITE_ENVIOS_POR_HORA
    return f"{n}/hour" if n > 0 else "100000/hour"


def limite_verificacion() -> str:
    """Devuelve la cadena de límite (p. ej. "30/minute") según configuración.
    Si `LIMITE_VERIFICACIONES_POR_MINUTO` es 0, retorna un límite muy alto
    (efectivamente desactivado)."""
    n = _config.LIMITE_VERIFICACIONES_POR_MINUTO
    if n <= 0:
        return "100000/minute"
    return f"{n}/minute"
