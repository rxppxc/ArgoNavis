"""Cola de salida de los avisos por correo (tabla `correos_salida`).

  - encolar_avisos: en la transacción de la operación. Si no se confirma, no sale nada.
  - despachar_correos: envía los pendientes que ya tocan. La llama cada respuesta
    que encoló avisos (en segundo plano, para que salgan enseguida) y la tarea de
    correos (los reintentos).
  - tarea_correos: cada minuto, los reintentos y la limpieza.

Antes los reintentos vivían en memoria (30 s y 2 min): con el servidor de correo
caído más tiempo, o con un reinicio, el aviso se perdía.

Cada correo se toma con FOR UPDATE SKIP LOCKED, en su propia transacción: con
varios workers, ninguno envía el que otro está enviando. Si el backend se cae a
mitad de un envío, la transacción se revierte y el correo se reintenta: puede
llegar dos veces, pero no se pierde.
"""
import asyncio
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obtener_configuracion
from app.core.email import Aviso, construir_mensaje, enviar_mensaje
from app.domain.models.correo import CorreoSalida, EstadoCorreo
from app.domain.repositories.correo_repository import RepositorioCorreo
from app.infrastructure.database import SesionLocal

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

# Espera antes de cada reintento, en segundos. Son 10 intentos: el último, unas
# 24 horas después del primero. Agotados, el correo queda "fallido" y en el log.
ESPERAS_REINTENTO = (30, 120, 600, 1800, 3600, 7200, 14400, 28800, 28800)
_REVISION_SEGUNDOS = 60
_DIAS_GUARDADOS = 30


async def encolar_avisos(sesion: AsyncSession, avisos: list[Aviso]) -> int:
    """Guarda los avisos en la cola, dentro de la transacción de la operación.
    Devuelve cuántos encoló."""
    if not configuracion.MAIL_HOST:
        for aviso in avisos:
            logger.warning("SMTP no configurado — se omite el aviso '%s'.", aviso.asunto)
        return 0
    repo = RepositorioCorreo(sesion)
    encolados = 0
    for aviso in avisos:
        destinatarios = list(dict.fromkeys(d.strip() for d in aviso.destinatarios if d and d.strip()))
        if destinatarios:
            await repo.agregar(replace(aviso, destinatarios=destinatarios))
            encolados += 1
    return encolados


# Un solo despacho a la vez en cada proceso. Cada respuesta que encola avisos
# lanza uno, y cada despacho retiene una conexión de la BD mientras espera al
# servidor de correo: con el correo lento y muchas respuestas a la vez, agotaban
# el pool. El que llega mientras otro despacha le pide otra vuelta y termina
# enseguida. Entre workers los separa FOR UPDATE SKIP LOCKED (tomar_pendiente).
# Sin candado de asyncio: entre mirar y marcar no hay un await, así que no se cruzan.
_despachando = False
_otra_vuelta = False


async def despachar_correos(limite: int = 50) -> int:
    """Envía hasta `limite` correos pendientes que ya tocan (más, si mientras
    tanto otra respuesta pidió otra vuelta). Devuelve cuántos salieron.

    Si el servidor de correo falla, para ahí: los demás fallarían igual, y cada
    intento puede durar lo que tarda en vencer la conexión al SMTP, con una
    conexión de la BD tomada. Los reintenta la tarea de correos."""
    global _despachando, _otra_vuelta
    if not configuracion.MAIL_HOST:
        return 0
    if _despachando:
        _otra_vuelta = True
        return 0
    _despachando = True
    try:
        enviados = 0
        while True:
            _otra_vuelta = False
            salieron, fallo_el_smtp = await _despachar_lote(limite)
            enviados += salieron
            if fallo_el_smtp or not _otra_vuelta:
                return enviados
    finally:
        _despachando = False


async def _despachar_lote(limite: int) -> tuple[int, bool]:
    """Hasta `limite` correos que ya tocan, uno por transacción: (cuántos
    salieron, si falló el servidor de correo)."""
    enviados = 0
    for _ in range(limite):
        async with SesionLocal() as sesion:
            correo = await RepositorioCorreo(sesion).tomar_pendiente()
            if correo is None:
                break
            resultado = await _intentar(correo)
            await sesion.commit()
        if resultado == "error_smtp":
            return enviados, True
        enviados += resultado == "enviado"
    return enviados, False


async def _intentar(correo: CorreoSalida) -> str:
    """Un intento de envío de `correo`, que queda enviado, reprogramado o fallido.
    Devuelve "enviado", "error_smtp" (falló el servidor) o "error_aviso" (no se pudo armar)."""
    ahora = datetime.now(timezone.utc)
    correo.intentos += 1
    try:
        aviso = Aviso(**correo.aviso)
        mensaje = construir_mensaje(aviso, aviso.destinatarios)
    except Exception as e:
        # Armarlo no depende del servidor de correo: reintentar daría el mismo error.
        logger.exception("No se pudo armar el aviso '%s': queda como fallido.", correo.asunto)
        correo.estado, correo.ultimo_error = EstadoCorreo.FALLIDO.value, _describir(e)
        return "error_aviso"
    try:
        await enviar_mensaje(mensaje)
    except Exception as e:
        correo.ultimo_error = _describir(e)
        if correo.intentos > len(ESPERAS_REINTENTO):
            correo.estado = EstadoCorreo.FALLIDO.value
            logger.error("No se pudo enviar el aviso '%s' tras %d intentos. Último error: %s",
                         correo.asunto, correo.intentos, correo.ultimo_error)
        else:
            espera = ESPERAS_REINTENTO[correo.intentos - 1]
            correo.proximo_intento = ahora + timedelta(seconds=espera)
            logger.warning("Intento %d del aviso '%s' falló (%s); se reintenta en %d s.",
                           correo.intentos, correo.asunto, correo.ultimo_error, espera)
        return "error_smtp"
    correo.estado, correo.enviado_en = EstadoCorreo.ENVIADO.value, ahora
    logger.info("Aviso '%s' enviado a %d destinatario(s) (intento %d).",
                correo.asunto, len(aviso.destinatarios), correo.intentos)
    return "enviado"


def _describir(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:500]


async def tarea_correos() -> None:
    """Cada minuto envía lo que toca (los reintentos) y borra los enviados y
    fallidos de más de 30 días. Un error en una vuelta no corta las siguientes."""
    while True:
        try:
            await despachar_correos()
            async with SesionLocal() as sesion:
                await RepositorioCorreo(sesion).borrar_terminados(
                    datetime.now(timezone.utc) - timedelta(days=_DIAS_GUARDADOS))
                await sesion.commit()
        except Exception:
            logger.exception("[correos] Error en la vuelta; se reintenta en la siguiente")
        await asyncio.sleep(_REVISION_SEGUNDOS)
