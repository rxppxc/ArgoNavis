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
import logging
import re
import secrets
import shutil
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import obtener_configuracion

try:
    import magic  # type: ignore
    _MAGIC_DISPONIBLE = True
except Exception:  # pragma: no cover — libmagic no disponible
    magic = None  # type: ignore
    _MAGIC_DISPONIBLE = False

try:
    from oletools.olevba import VBA_Parser  # type: ignore
    _OLETOOLS_DISPONIBLE = True
except Exception:  # pragma: no cover — oletools no disponible
    VBA_Parser = None  # type: ignore
    _OLETOOLS_DISPONIBLE = False

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
# _verificar_contenido y los de Office, además, sin macros.
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
_FIRMA_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")     # .doc y .xls (formato binario de Office)
_PARTE_OOXML = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml"}
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
    """Borra un documento del storage. No lanza: se usa en limpiezas (tras un
    error o al confirmar una corrección) y un archivo que no se pudo borrar
    (p. ej. abierto en Windows) solo queda en el log."""
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
    """MIME por contenido (python-magic). Si magic no está o no precisa el tipo
    (para algunas versiones de libmagic un Office es solo un ZIP u OLE2), el del
    formato, que ya se verificó por su estructura."""
    if _MAGIC_DISPONIBLE:
        try:
            mime = magic.from_file(str(ruta), mime=True)
            if mime and mime not in _MIME_GENERICOS:
                return mime
        except Exception as exc:  # pragma: no cover
            logger.warning("[mime] Detección por contenido falló: %s", exc)
    return _MIME_POR_EXTENSION[ext]


def _tiene_macros_sync(ruta: Path) -> bool:
    """Analiza un archivo Office en busca de macros VBA. Síncrono y
    potencialmente lento — llamar siempre vía asyncio.to_thread()."""
    if zipfile.is_zipfile(ruta):
        # Un .docx/.xlsx legítimo nunca trae proyecto de macros: se rechaza
        # aunque esté dañado y oletools no logre analizarlo.
        with zipfile.ZipFile(ruta) as archivo:
            if any(parte.lower().endswith("vbaproject.bin") for parte in archivo.namelist()):
                return True
    parser = VBA_Parser(str(ruta))
    try:
        return parser.detect_vba_macros()
    finally:
        parser.close()


async def _verificar_sin_macros(ruta: Path, ext: str, nombre_original: str) -> None:
    """Rechaza documentos de Office con macros. Falla cerrado: si oletools no
    está o no puede analizar el archivo, se rechaza igual."""
    if ext == ".pdf":
        return
    if not _OLETOOLS_DISPONIBLE:
        logger.error("[macros] oletools no disponible — rechazando '%s' por precaución.", nombre_original)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar el archivo de forma segura. Contacta al administrador.",
        )
    try:
        tiene_macros = await asyncio.to_thread(_tiene_macros_sync, ruta)
    except Exception as exc:
        logger.warning("[macros] No se pudo analizar '%s': %s", nombre_original, exc)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"No se pudo validar '{nombre_original}' de forma segura: el archivo podría estar dañado.",
        )
    if tiene_macros:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{nombre_original}' contiene macros y no está permitido. Guárdalo sin macros e intenta de nuevo.",
        )


def _validar_extension(nombre_archivo: str) -> str:
    ext = Path(nombre_archivo).suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{nombre_archivo}' no es un formato admitido: solo PDF, Word (.doc, .docx) o Excel (.xls, .xlsx).",
        )
    return ext


def _contenido_valido(ruta: Path, ext: str) -> bool:
    """El contenido corresponde de verdad al formato: un archivo de otro tipo
    renombrado (p. ej. un .exe con extensión .docx) no pasa."""
    with open(ruta, "rb") as f:
        inicio = f.read(1024)
    if ext == ".pdf":
        return b"%PDF-" in inicio                    # firma en el primer kilobyte
    if ext in (".doc", ".xls"):
        return inicio.startswith(_FIRMA_OLE2)        # contenedor OLE2
    # .docx / .xlsx: ZIP con la estructura OOXML de su tipo (solo se lee el índice).
    try:
        with zipfile.ZipFile(ruta) as archivo:
            partes = set(archivo.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in partes and _PARTE_OOXML[ext] in partes


def _verificar_contenido(ruta: Path, ext: str, nombre_original: str) -> None:
    if not _contenido_valido(ruta, ext):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{nombre_original}' no es {_NOMBRE_FORMATO[ext]}.",
        )


async def _escribir(subida: UploadFile, ruta: Path, nombre_original: str) -> int:
    """Copia el archivo subido a `ruta` por fragmentos y devuelve su tamaño.
    413 si supera TAMANO_MAXIMO_MB. El error se lanza ya cerrado el archivo:
    en Windows no se puede borrar un archivo abierto."""
    max_bytes = TAMANO_MAXIMO_BYTES
    tamano = 0
    async with aiofiles.open(ruta, "wb") as f:
        while fragmento := await subida.read(TAMANO_CHUNK):
            tamano += len(fragmento)
            if tamano > max_bytes:
                break
            await f.write(fragmento)
    if tamano > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo '{nombre_original}' pesa más de {TAMANO_MAXIMO_MB} MB, el máximo por archivo.",
        )
    return tamano


async def guardar_archivos(destino: Path, archivos_subidos: list[UploadFile]) -> list[ArchivoGuardado]:
    """Valida y escribe los archivos en `destino`. Si uno falla, borra del
    disco los que ya había escrito en esta llamada (también el que falló) y
    relanza el error."""
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []
    guardados: list[ArchivoGuardado] = []
    try:
        for subida in archivos_subidos:
            nombre_original   = _sanear_nombre(subida.filename or "archivo")
            ext               = _validar_extension(nombre_original)
            nombre_almacenado = f"{secrets.token_hex(16)}{ext}"
            ruta_archivo      = destino / nombre_almacenado
            escritos.append(ruta_archivo)

            tamano = await _escribir(subida, ruta_archivo, nombre_original)
            await asyncio.to_thread(_verificar_contenido, ruta_archivo, ext, nombre_original)
            await _verificar_sin_macros(ruta_archivo, ext, nombre_original)
            guardados.append(ArchivoGuardado(
                nombre_original=nombre_original,
                nombre_almacenado=nombre_almacenado,
                ruta=str(ruta_archivo),
                tipo_mime=_detectar_mime(ruta_archivo, ext),
                tamano=tamano,
            ))
    except Exception:
        for ruta in escritos:
            ruta.unlink(missing_ok=True)
        raise
    return guardados
