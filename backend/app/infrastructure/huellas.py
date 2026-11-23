"""La huella (SHA-256) de los documentos que se subieron antes de guardarla (2026-11-22).

Los nuevos la llevan desde que se reciben. A los de antes se les calcula una vez, con el
archivo que haya hoy: desde ese momento se puede comprobar que no cambió."""
import asyncio
import logging

from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal

logger = logging.getLogger(__name__)

LOTE = 200


def _calcular(documentos: list) -> list[tuple[int, str]]:
    """(id, huella) de los que están en el disco. Corre en un hilo."""
    huellas = []
    for d in documentos:
        archivo = almacenamiento.ruta_segura(d.ruta)
        try:
            if archivo and archivo.is_file():
                huellas.append((d.id, almacenamiento.huella_de(archivo)))
        except OSError as exc:
            logger.warning("[huellas] No se pudo leer el documento %s: %s", d.id, exc)
    return huellas


async def completar_huellas() -> int:
    """A todos los que les falta, de a LOTE. Devuelve a cuántos se les puso."""
    total, ultimo = 0, 0
    while True:
        async with SesionLocal() as sesion:
            documentos = await RepositorioSolicitud(sesion).documentos_sin_huella(ultimo, LOTE)
        if not documentos:
            break
        ultimo = documentos[-1].id
        huellas = await asyncio.to_thread(_calcular, documentos)
        async with SesionLocal() as sesion:
            repo = RepositorioSolicitud(sesion)
            for documento_id, sha256 in huellas:
                await repo.poner_huella(documento_id, sha256)
            await sesion.commit()
        total += len(huellas)
    return total
