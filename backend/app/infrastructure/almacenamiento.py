"""Capa documental: guarda, valida y localiza los archivos del expediente.

Es lo que quedó del storage original, adaptado: los archivos ya no son una
transferencia suelta con enlace público, sino documentos de una solicitud,
guardados bajo STORAGE_PATH en una carpeta por solicitud.

Toda subida pasa por la misma validación: formato admitido (PDF, Word o
Excel) comprobado por extensión y por contenido, tamaño máximo, sin macros
(Office) y MIME detectado por contenido — nunca se confía en lo que declara
el cliente.
"""
import asyncio
import hashlib
import logging
import re
import secrets
import shutil
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import obtener_configuracion
from app.infrastructure.revision_office import Problema, revisar_office

try:
    import magic  # type: ignore
    _MAGIC_DISPONIBLE = True
except Exception:  # pragma: no cover — libmagic no disponible
    magic = None  # type: ignore
    _MAGIC_DISPONIBLE = False

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

TAMANO_CHUNK = 1024 * 1024  # 1 MB por fragmento

# Tope por archivo, para cualquier formato (decisión del usuario, 2026-10-16).
# Es una regla fija, no una variable de entorno: así el backend y su espejo en
# frontend/src/utils/archivos.ts no pueden quedar con valores distintos.
TAMANO_MAXIMO_MB    = 2
TAMANO_MAXIMO_BYTES = TAMANO_MAXIMO_MB * 1024 * 1024

# Caracteres prohibidos en nombres de archivo (control + reservados de Windows
# + comillas y diagonales). Se reemplazan por "_".
_NOMBRE_INVALIDO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Largo máximo del nombre original que se guarda (la columna admite 500; los
# navegadores y los sistemas de archivos, 255). Más largo se recorta.
_LARGO_MAXIMO_NOMBRE = 200

# Formatos del expediente: PDF, Word y Excel (decisión del usuario, 2026-10-15:
# "de momento", además de PDF). El contenido se comprueba según el formato en
# _verificar_contenido; los de Office, además, sin macros (revision_office.py).
_MIME_POR_EXTENSION = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls":  "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSIONES_PERMITIDAS = set(_MIME_POR_EXTENSION)

# Lo que libmagic puede responder para un Office válido sin precisar el tipo.
_MIME_GENERICOS = {
    "application/zip", "application/octet-stream", "application/x-ole-storage",
    "application/CDFV2", "application/vnd.ms-office",
}
_NOMBRE_FORMATO = {
    ".pdf": "un PDF válido", ".doc": "un documento de Word válido", ".docx": "un documento de Word válido",
    ".xls": "un libro de Excel válido", ".xlsx": "un libro de Excel válido",
}


@dataclass
class ArchivoGuardado:
    """Un archivo ya validado y escrito en disco, listo para registrarse."""
    nombre_original:   str
    nombre_almacenado: str
    ruta:              str
    tipo_mime:         str
    tamano:            int
    sha256:            str


def raiz_documentos() -> Path:
    return Path(configuracion.STORAGE_PATH).resolve()


def carpeta_solicitud(solicitud_id: int) -> Path:
    return raiz_documentos() / f"solicitud-{solicitud_id}"


def carpeta_temporal() -> Path:
    """Carpeta de paso para los archivos de una solicitud nueva: se validan y
    escriben antes de registrarla (así un archivo rechazado no consume un
    número de solicitud) y luego la carpeta se renombra a `solicitud-{id}`."""
    return raiz_documentos() / f"tmp-{secrets.token_hex(8)}"


def mover_carpeta(origen: Path, destino: Path) -> None:
    """Renombra la carpeta (mismo volumen: es instantáneo)."""
    origen.rename(destino)


def limpiar_temporales(horas: int = 24) -> None:
    """Borra carpetas temporales abandonadas (p. ej. si el proceso se cayó a
    mitad de un envío). Una subida en curso nunca dura tantas horas."""
    raiz = raiz_documentos()
    if not raiz.is_dir():
        return
    limite = time.time() - horas * 3600
    for carpeta in raiz.glob("tmp-*"):
        try:
            if carpeta.is_dir() and carpeta.stat().st_mtime < limite:
                borrar_carpeta(carpeta)
        except OSError as exc:
            logger.warning("[almacenamiento] No se pudo limpiar %s: %s", carpeta.name, exc)


def ruta_relativa(archivo: Path) -> str:
    """La ruta que se guarda en la BD: relativa a STORAGE_PATH y con «/»
    («solicitud-12/abc.pdf»). Así la carpeta de documentos se puede mover o
    renombrar cambiando solo STORAGE_PATH."""
    return archivo.resolve().relative_to(raiz_documentos()).as_posix()


def ruta_segura(ruta: str) -> Path | None:
    """El archivo en disco de una ruta de la BD (relativa a STORAGE_PATH), si de
    verdad vive dentro de STORAGE_PATH; None si no (defensa contra path
    traversal, aunque la ruta venga de la BD)."""
    raiz = raiz_documentos()
    try:
        resuelta = (raiz / ruta).resolve()   # una ruta absoluta reemplaza a la raíz y se valida igual
        resuelta.relative_to(raiz)
    except (ValueError, OSError):
        logger.warning("[almacenamiento] Ruta fuera del storage: %s", ruta)
        return None
    return resuelta


def borrar_archivo(ruta: str) -> None:
    """Borra un archivo que nunca llegó a registrarse (tras un error). Los documentos de un
    expediente no se borran (2026-11-22). No lanza: un archivo que no se pudo borrar (p. ej.
    abierto en Windows) solo queda en el log."""
    archivo = ruta_segura(ruta)
    if archivo:
        try:
            archivo.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("[almacenamiento] No se pudo borrar %s: %s", archivo.name, exc)


def borrar_carpeta(carpeta: Path) -> None:
    raiz = raiz_documentos()
    try:
        resuelta = carpeta.resolve()
        resuelta.relative_to(raiz)
    except (ValueError, OSError):
        return
    if resuelta != raiz:
        shutil.rmtree(resuelta, ignore_errors=True)


def _sanear_nombre(nombre: str) -> str:
    """Nombre de archivo seguro: sin caracteres de control, sin barras, sin
    caracteres reservados en NTFS. Conserva tildes y unicode."""
    nombre = unicodedata.normalize("NFC", nombre or "")
    nombre = nombre.replace("\r", " ").replace("\n", " ")
    nombre = _NOMBRE_INVALIDO.sub("_", nombre)
    nombre = nombre.strip(" .")
    if len(nombre) > _LARGO_MAXIMO_NOMBRE:
        extension = Path(nombre).suffix[:16]
        nombre = nombre[: _LARGO_MAXIMO_NOMBRE - len(extension)].rstrip(" .") + extension
    return nombre or "archivo"


def _detectar_mime(ruta: Path, ext: str) -> str:
    """El MIME del formato, que ya se verificó por su estructura; python-magic
    queda como control cruzado. Antes se guardaba lo que dijera libmagic, y un
    «PDF» que empezaba con HTML (se admite contenido antes de %PDF-, como hace
    Acrobat) quedaba como text/html: el visor lo pintaba como una página del
    mismo origen. Si libmagic ve otra cosa que no sea un genérico (un Office
    puede ser para él solo un ZIP u OLE2), queda en el log."""
    esperado = _MIME_POR_EXTENSION[ext]
    if _MAGIC_DISPONIBLE:
        try:
            mime = magic.from_file(str(ruta), mime=True)
            if mime and mime != esperado and mime not in _MIME_GENERICOS:
                logger.warning("[mime] '%s' pasó la validación de %s pero libmagic lo ve como %s.", ruta.name, ext, mime)
        except Exception as exc:  # pragma: no cover
            logger.warning("[mime] Detección por contenido falló: %s", exc)
    return esperado


def mime_del_formato(nombre_almacenado: str) -> str:
    """Con qué tipo se sirve un documento: el de su formato verificado (la
    extensión del nombre con que se guardó), no el de la BD, que en documentos
    subidos antes de esta regla puede ser el de libmagic."""
    return _MIME_POR_EXTENSION.get(Path(nombre_almacenado).suffix.lower(), "application/octet-stream")


def _validar_extension(nombre_archivo: str) -> str:
    ext = Path(nombre_archivo).suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{nombre_archivo}' no es un formato admitido: solo PDF, Word (.doc, .docx) o Excel (.xls, .xlsx).",
        )
    return ext


def _es_pdf(ruta: Path) -> bool:
    with open(ruta, "rb") as f:
        return b"%PDF-" in f.read(1024)   # firma en el primer kilobyte


def _motivo_del_rechazo(problema: Problema, ext: str) -> str:
    """Cómo sigue el mensaje, después del nombre del archivo."""
    if problema is Problema.MACROS:
        return "contiene macros y no está permitido. Guárdalo sin macros e intenta de nuevo."
    if problema is Problema.INFLADO:
        return "ocupa demasiado al abrirse. Guárdalo como PDF e intenta de nuevo."
    return f"no es {_NOMBRE_FORMATO[ext]}."


async def _verificar_contenido(ruta: Path, ext: str, nombre_original: str) -> None:
    """El contenido corresponde de verdad al formato: un archivo de otro tipo
    renombrado (p. ej. un .exe con extensión .docx) no pasa. Los de Office, además,
    sin macros. Falla cerrado: lo que no se puede revisar se rechaza."""
    try:
        if ext == ".pdf":
            problema = None if await asyncio.to_thread(_es_pdf, ruta) else Problema.FORMATO
        else:
            problema = await asyncio.to_thread(revisar_office, ruta, ext)
    except Exception as exc:
        logger.warning("[archivos] No se pudo revisar '%s': %s", nombre_original, exc)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"No se pudo validar '{nombre_original}' de forma segura: el archivo podría estar dañado.",
        ) from exc
    if problema is None:
        return
    if problema is not Problema.FORMATO:
        logger.warning("[archivos] Se rechazó '%s': %s.", nombre_original, problema.value)
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"'{nombre_original}' {_motivo_del_rechazo(problema, ext)}",
    )


async def _escribir(subida: UploadFile, ruta: Path, nombre_original: str) -> tuple[int, str]:
    """Copia el archivo subido a `ruta` por fragmentos y devuelve su tamaño y su huella.
    413 si supera TAMANO_MAXIMO_MB. El error se lanza ya cerrado el archivo:
    en Windows no se puede borrar un archivo abierto."""
    max_bytes = TAMANO_MAXIMO_BYTES
    tamano, huella = 0, hashlib.sha256()
    async with aiofiles.open(ruta, "wb") as f:
        while fragmento := await subida.read(TAMANO_CHUNK):
            tamano += len(fragmento)
            if tamano > max_bytes:
                break
            huella.update(fragmento)
            await f.write(fragmento)
    if tamano > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo '{nombre_original}' pesa más de {TAMANO_MAXIMO_MB} MB, el máximo permitido por archivo.",
        )
    return tamano, huella.hexdigest()


def huella_de(ruta: Path) -> str:
    """El SHA-256 del archivo. Lee el disco: va en un hilo."""
    with open(ruta, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def guardar_autorizacion(solicitud_id: int, tipo: str, contenido: bytes) -> tuple[str, str]:
    """Escribe el PDF emitido en la carpeta de la solicitud y devuelve (ruta relativa,
    huella). Con otro nombre mientras se escribe: uno a medias nunca parece bueno."""
    carpeta = carpeta_solicitud(solicitud_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    _verificar_espacio_libre(carpeta)
    archivo = carpeta / f"autorizacion-{tipo}-{secrets.token_hex(8)}.pdf"
    parcial = archivo.with_suffix(".parcial")
    try:
        parcial.write_bytes(contenido)
        parcial.rename(archivo)
    except OSError:
        parcial.unlink(missing_ok=True)
        raise
    return ruta_relativa(archivo), hashlib.sha256(contenido).hexdigest()


def _verificar_espacio_libre(carpeta: Path) -> None:
    """Con menos de ESPACIO_MINIMO_LIBRE_MB libres en el disco de los documentos,
    no se recibe nada (507) y queda un error en el log (lo ve verificar-despliegue.sh).
    Ese disco es también el de PostgreSQL (en Docker, los dos volúmenes) y el de los
    respaldos: lleno, la base deja de escribir y se cae todo, no solo las subidas
    (revisión de recursos del 2026-11-10)."""
    minimo = configuracion.ESPACIO_MINIMO_LIBRE_MB
    if minimo <= 0:
        return
    libre = shutil.disk_usage(carpeta).free
    if libre < minimo * 1024 * 1024:
        logger.error("[almacenamiento] Quedan %d MB libres en el disco de los documentos (mínimo %d MB): "
                     "no se reciben archivos hasta liberar espacio.", libre // (1024 * 1024), minimo)
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="El servidor se está quedando sin espacio en disco y no puede recibir documentos. "
                   "Avisa a la Dirección de Tecnología e Innovación.",
        )


async def guardar_archivos(destino: Path, archivos_subidos: list[UploadFile]) -> list[ArchivoGuardado]:
    """Valida y escribe los archivos en `destino`. Si uno falla, borra del
    disco los que ya había escrito en esta llamada (también el que falló) y
    relanza el error."""
    destino.mkdir(parents=True, exist_ok=True)
    if archivos_subidos:
        _verificar_espacio_libre(destino)
    escritos: list[Path] = []
    guardados: list[ArchivoGuardado] = []
    try:
        for subida in archivos_subidos:
            nombre_original   = _sanear_nombre(subida.filename or "archivo")
            ext               = _validar_extension(nombre_original)
            nombre_almacenado = f"{secrets.token_hex(16)}{ext}"
            ruta_archivo      = destino / nombre_almacenado
            escritos.append(ruta_archivo)

            tamano, sha256 = await _escribir(subida, ruta_archivo, nombre_original)
            await _verificar_contenido(ruta_archivo, ext, nombre_original)
            guardados.append(ArchivoGuardado(
                nombre_original=nombre_original,
                nombre_almacenado=nombre_almacenado,
                ruta=str(ruta_archivo),
                tipo_mime=await asyncio.to_thread(_detectar_mime, ruta_archivo, ext),   # libmagic lee el archivo
                tamano=tamano,
                sha256=sha256,
            ))
    except Exception:
        for ruta in escritos:
            ruta.unlink(missing_ok=True)
        raise
    return guardados
