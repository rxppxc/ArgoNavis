"""Los documentos de Word y Excel se revisan sin abrirlos con una librería (2026-11-22).

La que buscaba las macros (oletools) leía partes enteras del archivo, sin tope: un .docx
de 20 KB hacía subir la memoria 500 MB, y un .doc de 400 KB ocupaba la CPU 8 segundos
(con los 2 MB que se admiten, minutos). Bastaba una cuenta de agencia para tumbar el
backend. Aquí: la memoria y la CPU no crecen con lo que el archivo dice traer, el
documento tiene que ser de su formato y las macros se siguen rechazando."""
import io
import struct
import time
import tracemalloc
import zipfile
import zlib

import pytest
from fastapi import HTTPException, UploadFile

from app.infrastructure import almacenamiento, revision_office
from ayudas import MIME_DOCX, MIME_XLSX, docx, ole2, xlsx

asincrona = pytest.mark.asyncio(loop_scope="session")

MB = 1024 * 1024
TOPE_MB = revision_office.MAXIMO_DESCOMPRIMIDO_MB
FIRMA_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
FICHA_DEL_INDICE = b"PK\x01\x02"
PARTES_WORD = {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<documento/>"}


def _word(partes: dict[str, bytes | tuple[bytes, int]], compresion: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Un .docx con esas partes. (principio, N) es una parte de N MB que empieza así y que,
    comprimida, ocupa mil veces menos."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compresion, compresslevel=9) as z:
        for nombre, contenido in {**PARTES_WORD, **partes}.items():
            if isinstance(contenido, bytes):
                z.writestr(nombre, contenido)
                continue
            principio, megas = contenido
            with z.open(nombre, "w") as f:
                f.write(principio)
                for _ in range(megas):
                    f.write(b"<a/>" * (MB // 4))
    return buf.getvalue()


async def _guardar(tmp_path, nombre: str, contenido: bytes):
    assert len(contenido) <= almacenamiento.TAMANO_MAXIMO_BYTES, "cabe en el tope por archivo: se puede enviar"
    return await almacenamiento.guardar_archivos(
        tmp_path / nombre, [UploadFile(file=io.BytesIO(contenido), filename=nombre)])


async def _rechazo(tmp_path, nombre: str, contenido: bytes) -> str:
    with pytest.raises(HTTPException) as error:
        await _guardar(tmp_path, nombre, contenido)
    assert error.value.status_code == 415
    assert not list((tmp_path / nombre).iterdir()), "lo rechazado no queda en el disco"
    return error.value.detail


# ── La memoria y la CPU no dependen de lo que el archivo diga traer ───────────

@asincrona
@pytest.mark.parametrize("parte", [
    ("word/embeddings/objeto.bin", FIRMA_OLE2, 40),   # 40 MB en un archivo de 40 KB
    ("_rels/.rels", b"<r>", 8),                       # el índice, que la librería leía entero
    ("[Content_Types].xml", b"<r>", 8),
    ("word/document.xml", b"<r>", 40),
], ids=lambda parte: parte[0])
async def test_un_word_muy_comprimido_no_ocupa_memoria(tmp_path, parte):
    nombre, principio, megas = parte
    contenido = _word({nombre: (principio, megas)})
    assert len(contenido) < 200 * 1024
    tracemalloc.start()
    try:
        try:
            await _guardar(tmp_path, "comprimido.docx", contenido)
        except HTTPException as error:
            assert error.status_code == 415
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert pico < 8 * MB, f"ocupó {pico / MB:.0f} MB"


@asincrona
async def test_un_word_que_se_infla_demasiado_se_rechaza(tmp_path):
    """Cabe en los 2 MB, pero abierto ocupa más de lo razonable: colgaría el navegador de quien revisa."""
    detalle = await _rechazo(tmp_path, "inflado.docx", _word({"word/document.xml": (b"", TOPE_MB + 1)}))
    assert "ocupa demasiado" in detalle and "PDF" in detalle
    # Repartido entre varias partes también: cuenta el total.
    repartido = _word({f"word/media/{n}.bmp": (b"BM", TOPE_MB // 4) for n in range(5)})
    assert "ocupa demasiado" in await _rechazo(tmp_path, "repartido.docx", repartido)
    # Dentro del tope, pasa.
    assert await _guardar(tmp_path, "normal.docx", _word({"word/media/1.bmp": (b"BM", TOPE_MB // 4)}))


@asincrona
@pytest.mark.parametrize("crc_de_todo", [False, True], ids=["CRC del comienzo", "CRC de todo"])
@pytest.mark.parametrize("megas", [TOPE_MB + 10, 5], ids=["pasa del tope", "dentro del tope"])
async def test_el_tamano_que_declara_el_zip_no_engana(tmp_path, megas, crc_de_todo):
    """El tamaño de cada parte lo escribe quien arma el ZIP: se mide el de verdad."""
    contenido = bytearray(_word({"word/document.xml": (b"", megas)}))
    ficha = contenido.rindex(FICHA_DEL_INDICE, 0, contenido.rindex(b"word/document.xml"))
    primeros = b"<a/>" * 25   # la ficha dice que la parte es solo esto
    struct.pack_into("<I", contenido, ficha + 24, len(primeros))
    if not crc_de_todo:
        struct.pack_into("<I", contenido, ficha + 16, zlib.crc32(primeros))
    await _rechazo(tmp_path, "mentira.docx", bytes(contenido))


@asincrona
async def test_un_word_con_miles_de_partes_se_rechaza(tmp_path):
    partes = {f"{n:x}": b"" for n in range(revision_office.MAXIMO_PARTES + 1)}
    assert "ocupa demasiado" in await _rechazo(tmp_path, "partes.docx", _word(partes, zipfile.ZIP_STORED))


@asincrona
@pytest.mark.parametrize("compresion", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA], ids=["bzip2", "lzma"])
async def test_solo_la_compresion_de_office(tmp_path, compresion):
    """Office solo usa deflate; las otras se inflan sin que se les pueda poner tope."""
    assert "no es un documento de Word válido" in await _rechazo(tmp_path, "raro.docx", _word({}, compresion))


@asincrona
async def test_un_doc_hostil_se_revisa_rapido(tmp_path):
    """Un .doc de 400 KB lleno de entradas que dicen ocupar, cada una, todo el archivo."""
    contenido = ole2("WordDocument", *(f"s{n}" for n in range(3200)), tamano=400 * 1024)
    inicio = time.perf_counter()
    await _guardar(tmp_path, "hostil.doc", contenido)
    assert time.perf_counter() - inicio < 2


# ── El contenido es de su formato ─────────────────────────────────────────────

@asincrona
async def test_word_y_excel_de_verdad_se_aceptan(tmp_path):
    for (nombre, contenido), mime in [
        (docx("carta")[:2], MIME_DOCX),
        (xlsx("lista")[:2], MIME_XLSX),
        (("viejo.doc", ole2("WordDocument", "1Table")), "application/msword"),
        (("viejo.xls", ole2("Workbook")), "application/vnd.ms-excel"),
        (("excel95.xls", ole2("Book")), "application/vnd.ms-excel"),
        (("con-objeto.docx", _word({"word/embeddings/oleObject1.bin": ole2("CONTENTS")})), MIME_DOCX),
    ]:
        [guardado] = await _guardar(tmp_path, nombre, contenido)
        assert guardado.tipo_mime == mime, nombre


@asincrona
async def test_un_excel_escrito_por_una_libreria_se_acepta(tmp_path):
    import xlsxwriter

    buf = io.BytesIO()
    with xlsxwriter.Workbook(buf, {"in_memory": True}) as libro:
        hoja = libro.add_worksheet("Tripulantes")
        for fila in range(500):
            hoja.write_row(fila, 0, ["Juan Pérez", "PA1234567", fila])
    assert await _guardar(tmp_path, "tripulantes.xlsx", buf.getvalue())


@asincrona
@pytest.mark.parametrize(("nombre", "contenido", "formato"), [
    # Un instalador (.msi), un correo (.msg) o un .ppt también son OLE2: la firma sola no alcanza.
    ("instalador.doc", ole2("SummaryInformation", "Tables"), "Word"),
    ("excel.doc", ole2("Workbook"), "Word"),
    ("word.xls", ole2("WordDocument"), "Excel"),
    ("cifrado.doc", ole2("EncryptionInfo", "EncryptedPackage"), "Word"),   # un .docx con contraseña
    ("sin-firma.doc", b"MZ" + ole2("WordDocument")[2:], "Word"),
    ("vacio.xls", FIRMA_OLE2 + bytes(512), "Excel"),
    ("texto.docx", b"no es un zip", "Word"),
    ("excel.docx", xlsx("x")[1], "Word"),
], ids=lambda valor: valor if isinstance(valor, str) and "." in valor else "")
async def test_otro_formato_renombrado_no_pasa(tmp_path, nombre, contenido, formato):
    detalle = await _rechazo(tmp_path, nombre, contenido)
    assert "válido" in detalle and formato in detalle


@asincrona
async def test_un_word_danado_no_pasa(tmp_path):
    contenido = bytearray(_word({"word/document.xml": b"<documento/>" * 1000}))
    datos = contenido.index(b"word/document.xml") + len(b"word/document.xml")
    contenido[datos + 5] ^= 0xFF
    assert "no es un documento de Word válido" in await _rechazo(tmp_path, "danado.docx", bytes(contenido))


# ── Sin macros ────────────────────────────────────────────────────────────────

@asincrona
@pytest.mark.parametrize(("nombre", "contenido"), [
    ("proyecto.docx", docx("x", "word/vbaProject.bin")[1]),
    ("macros.doc", ole2("WordDocument", "Macros", "VBA", "dir", "_VBA_PROJECT", "PROJECT")),
    ("macros.xls", ole2("Workbook", "_VBA_PROJECT_CUR", "VBA")),
    ("minusculas.doc", ole2("WordDocument", "vba", "_vba_project")),   # Office no distingue mayúsculas
    ("codigo.doc", ole2("WordDocument") + b"\x01\x16\xb0\x00Attribut\x00e VB_Nam"),   # el código, sin el proyecto
    ("renombrado.docx", _word({"word/otro.xml": ole2("VBA", "_VBA_PROJECT", "dir")})),
    ("incrustado.docx", _word({"word/embeddings/oleObject1.bin": ole2("WordDocument", "Macros", "_VBA_PROJECT")})),
], ids=lambda valor: valor if isinstance(valor, str) else "")
async def test_office_con_macros_se_rechaza(tmp_path, nombre, contenido):
    assert "macros" in await _rechazo(tmp_path, nombre, contenido)


@asincrona
@pytest.mark.parametrize("corrimiento", range(-24, 2))
async def test_las_macros_se_ven_aunque_caigan_entre_dos_trozos(tmp_path, corrimiento):
    objeto = FIRMA_OLE2.ljust(revision_office.TROZO + corrimiento, bytes(1)) + "_VBA_PROJECT".encode("utf-16-le")
    contenido = _word({"word/embeddings/oleObject1.bin": objeto + bytes(1000)})
    assert "macros" in await _rechazo(tmp_path, "borde.docx", contenido)


@asincrona
async def test_si_no_se_puede_revisar_se_rechaza(tmp_path, monkeypatch):
    def falla(ruta, ext):
        raise MemoryError

    monkeypatch.setattr(almacenamiento, "revisar_office", falla)
    assert "de forma segura" in await _rechazo(tmp_path, "carta.docx", docx("carta")[1])
