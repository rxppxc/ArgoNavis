"""Tareas de fondo: vencimientos de solicitudes y limpieza de temporales.

En producción uvicorn corre con varios workers y cada proceso arranca su
propia tarea. Un advisory lock de PostgreSQL (pg_try_advisory_xact_lock)
garantiza que en cada vuelta solo un worker haga el trabajo; los demás ven el
candado tomado y lo intentan en la vuelta siguiente. (Además, las filas se
toman con FOR UPDATE SKIP LOCKED, así que ni siquiera dos ejecutores a la vez
podrían expirar dos veces la misma solicitud.)
"""
import asyncio
import logging

from sqlalchemy import text

from app.core.config import obtener_configuracion
from app.core.email import Aviso, enviar_aviso
from app.domain.models.audit_log import AccionAuditoria
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.services.notificacion_service import ServicioNotificacion
from app.domain.services.solicitud_service import ServicioSolicitud
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

# Identifica el candado de esta tarea en pg_advisory_*: cualquier entero fijo
# sirve mientras ninguna otra tarea use el mismo.
_LLAVE_VENCIMIENTOS = 7_420_001


async def expirar_solicitudes() -> int:
    """Expira las autorizaciones aprobadas que no se finalizaron a tiempo y las
    solicitudes devueltas que no se corrigieron en el plazo. Deja la bitácora,
    avisa a la agencia por correo y limpia carpetas temporales abandonadas.
    Devuelve cuántas solicitudes expiró."""
    avisos: list[Aviso] = []
    try:
        async with SesionLocal() as sesion:
            tomado = (await sesion.execute(
                text("SELECT pg_try_advisory_xact_lock(:llave)"), {"llave": _LLAVE_VENCIMIENTOS},
            )).scalar()
            if not tomado:
                return 0   # otro worker está en esta vuelta

            vencidas = await ServicioSolicitud(sesion).expirar_vencidas()
            auditoria = RepositorioAuditoria(sesion)
            notificaciones = ServicioNotificacion(sesion)
            for v in vencidas:
                await auditoria.registrar(
                    AccionAuditoria.SOLICITUD_EXPIRADA,
                    username="sistema",
                    detalle={
                        "solicitud_id": v.solicitud.id, "numero": v.solicitud.numero,
                        "estado_anterior": v.estado_anterior, "motivo": v.motivo,
                    },
                )
                avisos += await notificaciones.expirada(v.solicitud, v.estado_anterior, v.motivo)
            await sesion.commit()   # libera el candado
            almacenamiento.limpiar_temporales()
    except Exception:
        logger.exception("[vencimientos] Error al expirar solicitudes")
        return 0

    for aviso in avisos:
        await enviar_aviso(aviso)
    return len(vencidas)


async def tarea_vencimientos() -> None:
    """Revisa plazos vencidos al arrancar y luego cada VENCIMIENTOS_INTERVALO_MINUTOS."""
    intervalo = max(configuracion.VENCIMIENTOS_INTERVALO_MINUTOS, 1) * 60
    while True:
        n = await expirar_solicitudes()
        if n:
            logger.info("[vencimientos] %d solicitud(es) expirada(s).", n)
        await asyncio.sleep(intervalo)
