import logging
from collections.abc import AsyncIterator, Callable

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import obtener_configuracion

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()


def _ajustes_de_conexion() -> dict:
    """Topes que PostgreSQL aplica a cada conexión de la app (solo con asyncpg,
    el driver de DATABASE_URL): una consulta descontrolada se cancela y una
    transacción que queda abierta sin actividad se cierra, en vez de retener
    la conexión y sus bloqueos de fila hasta reiniciar. Alembic usa su propio
    motor (alembic/env.py): las migraciones no tienen estos topes."""
    if not make_url(configuracion.DATABASE_URL).drivername.endswith("asyncpg"):
        return {}
    ajustes = {}
    if configuracion.BD_TIEMPO_MAXIMO_CONSULTA > 0:
        ajustes["statement_timeout"] = str(configuracion.BD_TIEMPO_MAXIMO_CONSULTA * 1000)
    if configuracion.BD_TIEMPO_MAXIMO_INACTIVA > 0:
        ajustes["idle_in_transaction_session_timeout"] = str(configuracion.BD_TIEMPO_MAXIMO_INACTIVA * 1000)
    return {"server_settings": ajustes} if ajustes else {}


motor_bd = create_async_engine(
    configuracion.DATABASE_URL,
    # echo SQL solo en desarrollo. En producción evita exponer queries con
    # datos sensibles en los logs y mejora rendimiento.
    echo=not configuracion.es_produccion and configuracion.APP_ENV == "development",
    pool_pre_ping=True,
    # Por proceso (ver BD_POOL en core/config.py): con varios workers se multiplica.
    pool_size=configuracion.BD_POOL,
    max_overflow=configuracion.BD_POOL_EXTRA,
    pool_timeout=configuracion.BD_POOL_ESPERA,
    pool_recycle=3600,  # recicla conexiones cada hora (previene conn cerradas por idle)
    connect_args=_ajustes_de_conexion(),
)

SesionLocal = async_sessionmaker(
    motor_bd,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def obtener_sesion_bd() -> AsyncIterator[AsyncSession]:
    """Una sesión (y una transacción) por request: commit si el endpoint
    termina bien, rollback si lanza una excepción.

    Úsala SIEMPRE como `Depends(obtener_sesion_bd, scope="function")`:
      - Con scope "function" el commit corre al terminar el endpoint, ANTES de
        enviar la respuesta y de las tareas en segundo plano. Así un commit
        fallido llega al cliente como error, y los correos solo salen de
        transacciones confirmadas (y sin filas bloqueadas mientras se envían).
      - Con el scope por defecto el commit correría después de responder, y
        además FastAPI la trataría como otra dependencia: habría dos sesiones
        en el mismo request.
    """
    async with SesionLocal() as sesion:
        try:
            yield sesion
            await sesion.commit()
        except Exception:
            await sesion.rollback()
            raise


def al_confirmar(sesion: AsyncSession, accion: Callable[[], None]) -> None:
    """Ejecuta `accion` solo cuando la transacción de la sesión se confirme
    (no si se revierte). Para efectos fuera de la BD que no se deshacen, como
    borrar archivos: hacerlo antes del commit dejaba registros apuntando a
    archivos que ya no existían si el commit fallaba. Un error en `accion` solo
    queda en el log: el commit ya ocurrió y la respuesta no debe fallar."""
    pendiente = True

    def ejecutar(_sesion) -> None:
        nonlocal pendiente
        if not pendiente:
            return
        pendiente = False
        try:
            accion()
        except Exception:
            logger.exception("[bd] Falló una acción posterior al commit.")

    def descartar(_sesion) -> None:
        nonlocal pendiente
        pendiente = False

    event.listen(sesion.sync_session, "after_commit", ejecutar)
    event.listen(sesion.sync_session, "after_rollback", descartar)
