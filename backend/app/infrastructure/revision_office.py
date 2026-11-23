"""Revisión de los documentos de Word y Excel que suben las agencias (2026-11-22).

Son archivos no confiables y se revisan sin abrirlos con una librería de análisis. La que
buscaba las macros (oletools) leía partes enteras, sin tope: con un .docx de 40 KB se
llenaba la memoria del contenedor, y con un .doc de 2 MB se ocupaba la CPU varios minutos.
Aquí el archivo se recorre de a trozos, sin guardar lo que se descomprime:

  - .docx / .xlsx: un ZIP con las partes de su formato, con la compresión que usa Office y
    que, descomprimido, no pasa de MAXIMO_DESCOMPRIMIDO_MB.
  - .doc / .xls: un contenedor OLE2 con el flujo principal de su formato. La firma sola no
    alcanza: un instalador (.msi), un correo (.msg) o un .ppt también son OLE2.
  - Macros: el proyecto VBA (MS-OVBA 2.2.1), en el documento o en un objeto incrustado. Se
    busca por el nombre de su flujo en el directorio del contenedor OLE2, donde va siempre
    entero y sin comprimir, y por el comienzo de su código.

La memoria no depende de lo que el archivo diga traer, y el tiempo crece con su tamaño
(tests/test_revision_office.py).
"""
import copy
import io
import sys
import zipfile
import zlib
from collections.abc import Iterator
from enum import Enum
from pathlib import Path


class Problema(Enum):
    """Por qué se rechaza un documento."""
    FORMATO = "no es de su formato"    # o está dañado, cifrado o manipulado
    INFLADO = "ocupa demasiado al abrirse"
    MACROS  = "trae macros"


# Con el tope de 2 MB por archivo, un documento normal abierto ocupa unos pocos MB (decenas,
# si trae imágenes sin comprimir). Uno que pasa de esto colgaría también el navegador de
# quien revisa, que lo abre para la vista previa.
MAXIMO_DESCOMPRIMIDO_MB = 50
# Partes de un .docx o .xlsx: los de verdad tienen decenas (cientos, con muchas imágenes).
MAXIMO_PARTES = 2000
TROZO = 256 * 1024

_FIRMA_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
_FICHA_ZIP = b"PK\x01\x02"          # la de cada parte en el índice del ZIP
_COMPRESIONES = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
_PARTE_PRINCIPAL = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml"}
_FLUJO_PRINCIPAL = {".doc": ("WordDocument",), ".xls": ("Workbook", "Book")}   # Book: Excel 5.0 y 95


def _en_directorio(nombre: str) -> bytes:
    """Un nombre como queda en el directorio de un contenedor OLE2 (UTF-16), en minúsculas:
    Office no las distingue."""
    return nombre.lower().encode("utf-16-le")


_MARCAS_VBA = (_en_directorio("_VBA_PROJECT"), b"attribut\x00")
_SOLAPE = max(len(marca) for marca in _MARCAS_VBA) - 1


def _trae_vba(minusculas: bytes) -> bool:
    return any(marca in minusculas for marca in _MARCAS_VBA)


def revisar_office(ruta: Path, ext: str) -> Problema | None:
    """Por qué se rechaza el documento, o None si está bien. Síncrono (milisegundos; unas
    décimas en el peor caso): llamar vía asyncio.to_thread()."""
    contenido = ruta.read_bytes()   # como mucho TAMANO_MAXIMO_MB (almacenamiento.py)
    if ext in _FLUJO_PRINCIPAL:
        return _revisar_ole2(contenido, ext)
    try:
        return _revisar_ooxml(contenido, ext)
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError):
        return Problema.FORMATO


def _revisar_ole2(contenido: bytes, ext: str) -> Problema | None:
    minusculas = contenido.lower()
    flujos = [_en_directorio(f"{flujo}\x00") for flujo in _FLUJO_PRINCIPAL[ext]]
    if not contenido.startswith(_FIRMA_OLE2) or not any(flujo in minusculas for flujo in flujos):
        return Problema.FORMATO
    return Problema.MACROS if _trae_vba(minusculas) else None


def _revisar_ooxml(contenido: bytes, ext: str) -> Problema | None:
    if contenido.count(_FICHA_ZIP) > MAXIMO_PARTES:   # antes de leer el índice
        return Problema.INFLADO
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        partes = archivo.infolist()
        nombres = {parte.filename for parte in partes}
        if not {"[Content_Types].xml", _PARTE_PRINCIPAL[ext]} <= nombres:
            return Problema.FORMATO
        # Un .docx/.xlsx legítimo nunca trae proyecto de macros: se rechaza aunque esté dañado.
        if any(nombre.lower().endswith("vbaproject.bin") for nombre in nombres):
            return Problema.MACROS
        libre = MAXIMO_DESCOMPRIMIDO_MB * 1024 * 1024
        for parte in partes:
            if parte.compress_type not in _COMPRESIONES:
                return Problema.FORMATO
            leido, es_ole2, cola = 0, False, b""
            for trozo in _trozos(archivo, parte):
                if not leido:
                    es_ole2 = trozo.startswith(_FIRMA_OLE2)   # vbaProject renombrado u objeto incrustado
                leido += len(trozo)
                if leido > libre:
                    return Problema.INFLADO
                if es_ole2:
                    ventana = (cola + trozo).lower()
                    if _trae_vba(ventana):
                        return Problema.MACROS
                    cola = ventana[-_SOLAPE:]
            if leido != parte.file_size:
                return Problema.FORMATO
            libre -= leido
    return None


def _trozos(archivo: zipfile.ZipFile, parte: zipfile.ZipInfo) -> Iterator[bytes]:
    """Lo que la parte ocupa de verdad, de a trozos; cuánto leer lo decide quien llama. El
    tamaño que declara lo escribe quien arma el ZIP, y zipfile corta ahí: sin él, llega
    hasta donde la parte termina y comprueba el CRC de todo."""
    entera = copy.copy(parte)
    entera.file_size = sys.maxsize
    with archivo.open(entera) as flujo:
        while trozo := flujo.read(TROZO):
            yield trozo
