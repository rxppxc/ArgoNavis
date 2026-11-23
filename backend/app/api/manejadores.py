"""Cómo responde la API a los errores que no son una HTTPException (auditoría del
2026-11-14; hasta entonces, en main.py): el tope de pedidos, una regla de la BD
rechazada y la BD caída, lenta o sin conexiones libres. Siempre con `detail`, que el
frontend muestra tal cual, y los 5xx con el código del pedido para buscar la traza."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolAgotado

from app.core.registro import id_pedido

logger = logging.getLogger(__name__)

_BD_NO_RESPONDE = {"detail": "La base de datos no respondió a tiempo. Intenta de nuevo en unos segundos."}


async def demasiadas_solicitudes(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 con `detail`, como el resto de los errores (el frontend lo muestra tal cual)."""
    logger.warning("[rate limit] %s %s superó %s", request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados intentos en poco tiempo. Espera unos minutos e intenta de nuevo."},
    )


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


def _no_disponible(contenido: dict) -> JSONResponse:
    return JSONResponse(status_code=503, content={**contenido, "codigo": id_pedido.get()},
                        headers={"Retry-After": "5"})


async def sin_conexiones_libres(request: Request, exc: PoolAgotado) -> JSONResponse:
    """Todas las conexiones del pool ocupadas durante BD_POOL_ESPERA: 503 con
    motivo (y el aviso en el log para dimensionar el pool) en vez de un 500."""
    logger.error("[bd] Sin conexiones libres en el pool (%s %s): revisa BD_POOL o las consultas lentas.",
                 request.method, request.url.path)
    return _no_disponible({"detail": "El sistema está muy ocupado. Intenta de nuevo en unos segundos."})


def es_falla_de_disponibilidad(exc: DBAPIError) -> bool:
    """La BD no está o cortó: conexión caída o rechazada, o una consulta
    cancelada por BD_TIEMPO_MAXIMO_CONSULTA (SQLSTATE 57014). Un error de
    programación (SQL mal armado) no es esto: ese sigue siendo un 500."""
    causa = getattr(exc.orig, "__cause__", None) or exc.orig
    return (isinstance(exc, (OperationalError, InterfaceError)) or exc.connection_invalidated
            or getattr(causa, "sqlstate", None) == "57014")


async def error_de_base_de_datos(request: Request, exc: DBAPIError) -> JSONResponse:
    """Errores de la BD que no son una regla rechazada (esas son IntegrityError,
    arriba). Si la BD no responde, 503 con motivo: el frontend lo muestra y se
    puede reintentar. Lo demás es un defecto: 500, con el detalle en el log."""
    if es_falla_de_disponibilidad(exc):
        logger.error("[bd] La base de datos no respondió en %s %s: %s",
                     request.method, request.url.path, type(exc.orig).__name__)
        return _no_disponible(_BD_NO_RESPONDE)
    logger.error("[bd] Error en %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor.", "codigo": id_pedido.get()})


async def servicio_no_disponible(request: Request, exc: ConnectionError) -> JSONResponse:
    """Una conexión rechazada o cortada (p. ej. PostgreSQL apagado: asyncpg la
    reporta así al conectar). 503 con motivo en vez de un 500."""
    logger.error("[red] Conexión rechazada en %s %s: %s", request.method, request.url.path, exc)
    return _no_disponible(_BD_NO_RESPONDE)


def registrar_manejadores(aplicacion: FastAPI) -> None:
    # Starlette busca por la clase de la excepción y luego por sus madres: IntegrityError
    # (409) gana sobre DBAPIError, de la que hereda.
    # Starlette tipa cada manejador con Exception, aunque recibe solo la suya: de ahí los ignore.
    aplicacion.add_exception_handler(RateLimitExceeded, demasiadas_solicitudes)  # type: ignore[arg-type]
    aplicacion.add_exception_handler(IntegrityError, conflicto_de_integridad)  # type: ignore[arg-type]
    aplicacion.add_exception_handler(PoolAgotado, sin_conexiones_libres)  # type: ignore[arg-type]
    aplicacion.add_exception_handler(DBAPIError, error_de_base_de_datos)  # type: ignore[arg-type]
    aplicacion.add_exception_handler(ConnectionError, servicio_no_disponible)  # type: ignore[arg-type]
