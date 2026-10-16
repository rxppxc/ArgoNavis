"""Datos y llamadas que comparten las pruebas del flujo."""
import io
import json
import secrets
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from conftest import Actor

HOY     = datetime.now(ZoneInfo("America/Panama")).date()
MANANA  = (HOY + timedelta(days=1)).isoformat()
VIGENTE = (HOY + timedelta(days=400)).isoformat()


def pdf(nombre: str) -> tuple[str, bytes, str]:
    contenido = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + nombre.encode()
    return (f"{nombre}.pdf", contenido, "application/pdf")


def _ooxml(parte_principal: str, *extra: str) -> bytes:
    """Un .docx/.xlsx mínimo: ZIP con [Content_Types].xml y su parte principal."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(parte_principal, "<documento/>")
        for parte in extra:
            z.writestr(parte, b"x")
    return buf.getvalue()


MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def docx(nombre: str, *extra: str) -> tuple[str, bytes, str]:
    return (f"{nombre}.docx", _ooxml("word/document.xml", *extra), MIME_DOCX)


def xlsx(nombre: str) -> tuple[str, bytes, str]:
    return (f"{nombre}.xlsx", _ooxml("xl/workbook.xml"), MIME_XLSX)


def tripulante(nombre: str, nacionalidad: str = "PHL", rango: str = "marino", **extra) -> dict:
    datos = {
        "nombre": nombre, "apellido": "Pérez", "fecha_nacimiento": "1990-05-01",
        "pais_nacimiento": nacionalidad, "nacionalidad": nacionalidad, "sexo": "M",
        "pasaporte": f"P{secrets.token_hex(3)}", "pasaporte_expira": VIGENTE,
        "rango": rango, "ocupacion": "Marinero",
    }
    if rango == "marino":
        datos.update({"libreta_marino": f"SB{secrets.token_hex(2)}", "libreta_expira": VIGENTE})
    datos.update(extra)
    return datos


def cabecera(codigo: str | None, puesto_id: int, **extra) -> dict:
    datos = {
        "puesto_control_id": puesto_id, "fecha_operacion": MANANA,
        "nombre_buque": "MSC AURORA", "imo": "IMO 9074729", "bandera": "PAN",
        "observaciones": "Cambio de tripulación programado",
    }
    if codigo:
        datos["codigo_tramite"] = codigo
    datos.update(extra)
    return datos


async def enviar(cliente, actor: Actor, datos: dict, archivos: list, metodo: str = "POST", ruta: str = "/solicitudes"):
    return await cliente.request(
        metodo, ruta, data={"solicitud": json.dumps(datos)},
        files=[("files", a) for a in archivos] or None, headers=actor.headers,
    )
