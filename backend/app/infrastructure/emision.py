"""La autorización tal como se emitió (2026-11-22).

El PDF de la agencia se arma una vez al aprobar y otra al finalizar, y se guarda con su huella
(`documentos_emitidos`). La agencia y quien escanea el QR reciben siempre ese archivo: aunque
cambie el formato o el catálogo, dentro de muchos años es el que se emitió. La copia interna
del SNM no se emite: se arma cada vez, con los nombres.

Se emite apenas se confirma la aprobación o la finalización, en segundo plano: armar el PDF no
frena la respuesta ni retiene la fila. Si el proceso se cae justo ahí, la completa la tarea de
fondo (`emitir_pendientes`) o la primera descarga."""
import asyncio
import logging
import random

from app.domain.models.solicitud import DocumentoEmitido
from app.domain.repositories.solicitud_repository import EMITIDO_POR_ESTADO, RepositorioSolicitud
from app.domain.services.solicitud_service import ServicioSolicitud
from app.informes.autorizacion_pdf import generar_pdf_autorizacion
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal
from app.infrastructure.trabajo_pesado import en_hilo_con_tope

logger = logging.getLogger(__name__)

POR_VUELTA = 50


async def asegurar_emision(solicitud_id: int) -> DocumentoEmitido | None:
    """La autorización emitida en el estado de hoy; si falta, la emite. None si en ese
    estado no hay (ni aprobada ni finalizada)."""
    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        s = await svc.repo.buscar_por_id(solicitud_id)
        tipo = EMITIDO_POR_ESTADO.get(s.estado) if s else None
        if s is None or tipo is None or s.aprobada_en is None or not s.codigo_verificacion:
            return None
        emitido = await svc.repo.emitido(solicitud_id, tipo)
        if emitido is not None:
            return emitido
        datos = await svc.datos_para_emitir(s)
    # Sin la conexión: armarlo puede esperar turno (trabajo_pesado.py).
    contenido = await en_hilo_con_tope(generar_pdf_autorizacion, datos)
    ruta, sha256 = await asyncio.to_thread(almacenamiento.guardar_autorizacion, solicitud_id, tipo, contenido)
    async with SesionLocal() as sesion:
        repo = RepositorioSolicitud(sesion)
        nueva = await repo.agregar_emitido(solicitud_id=solicitud_id, tipo=tipo, ruta=ruta, tamano=len(contenido), sha256=sha256)
        await sesion.commit()
        if not nueva:
            almacenamiento.borrar_archivo(ruta)   # otro proceso la emitió a la vez: vale la suya
        return await repo.emitido(solicitud_id, tipo)


async def emitir(solicitud_id: int) -> None:
    """Para correr después de responder: un error queda en el log y la completa la tarea de fondo."""
    try:
        await asegurar_emision(solicitud_id)
    except Exception:
        logger.exception("[emision] No se pudo emitir la autorización de la solicitud %s; se reintenta sola.", solicitud_id)


async def autorizacion_emitida(solicitud_id: int) -> bytes | None:
    """El archivo que se emitió, si está y no cambió. None si no se puede dar: queda en el log
    y quien lo pide lo arma de nuevo, para no dejar a la agencia sin su autorización."""
    try:
        emitido = await asegurar_emision(solicitud_id)
        if emitido is None:
            return None
        archivo = almacenamiento.ruta_segura(emitido.ruta)
        if not archivo or not archivo.is_file():
            logger.error("[emision] La autorización emitida %s no está en el disco (%s).", emitido.id, emitido.ruta)
            return None
        if await asyncio.to_thread(almacenamiento.huella_de, archivo) != emitido.sha256:
            logger.error("[emision] La autorización emitida %s no coincide con su huella (%s).", emitido.id, emitido.ruta)
            return None
        return await asyncio.to_thread(archivo.read_bytes)
    except Exception:
        logger.exception("[emision] No se pudo dar la autorización emitida de la solicitud %s.", solicitud_id)
        return None


async def emitir_pendientes() -> int:
    """Emite las que falten (hasta POR_VUELTA) y devuelve cuántas. Una que falla no frena a las demás."""
    async with SesionLocal() as sesion:
        ids = await RepositorioSolicitud(sesion).sin_emitir(POR_VUELTA)
    random.shuffle(ids)   # una que siempre falla no tapa a las demás
    emitidas = 0
    for solicitud_id in ids:
        try:
            emitidas += (await asegurar_emision(solicitud_id)) is not None
        except Exception:
            logger.exception("[emision] No se pudo emitir la autorización de la solicitud %s.", solicitud_id)
    return emitidas
