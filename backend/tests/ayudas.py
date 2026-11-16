"""Datos y llamadas que comparten las pruebas del flujo."""
import io
import json
import secrets
import zipfile
from datetime import datetime, timedelta
from app.core.horario import ZONA_PANAMA
from conftest import Actor

HOY     = datetime.now(ZONA_PANAMA).date()
MANANA  = (HOY + timedelta(days=1)).isoformat()
VIGENTE = (HOY + timedelta(days=400)).isoformat()


def panama(*partes: int) -> datetime:
    """Un momento en hora de Panamá: panama(2026, 10, 30, 15, 1)."""
    return datetime(*partes, tzinfo=ZONA_PANAMA)


async def login(cliente, usuario: str, clave: str):
    return await cliente.post("/auth/login", json={"username": usuario, "password": clave})


def cuerpo_impedimentos(detalle: dict, con_impedimento: set[str] = frozenset(),
                        comentario: str | None = "Sin impedimentos en SIMPLUS") -> dict:
    """La verificación por pasajero: todos "sin impedimento" salvo los nombrados."""
    return {
        "tripulantes": [{"tripulante_id": t["id"], "con_impedimento": t["nombre"] in con_impedimento}
                        for t in detalle["tripulantes"]],
        "comentario": comentario,
    }


async def verificar_impedimentos(cliente, actor: Actor, solicitud_id: int, *,
                                 con_impedimento: set[str] = frozenset(), ruta: str = "impedimentos") -> dict:
    """La de UCVMM (`impedimentos`) o la del puesto de control (`impedimentos-puesto`)."""
    detalle = (await cliente.get(f"/solicitudes/{solicitud_id}", headers=actor.headers)).json()
    r = await cliente.post(f"/solicitudes/{solicitud_id}/{ruta}",
                           json=cuerpo_impedimentos(detalle, con_impedimento), headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


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


FORMULARIO_3 = "DOC-FORMULARIO-3"


async def enviar(cliente, actor: Actor, datos: dict, archivos: list, metodo: str = "POST", ruta: str = "/solicitudes",
                 *, formulario_3: bool = True):
    """Crea (POST) o corrige (PUT) una solicitud. Al crear, si las asignaciones no
    traen el Formulario No. 3, que todos los trámites piden desde el 2026-11-13, se
    agrega con su archivo: así cada prueba no tiene que repetirlo. `formulario_3=False`
    lo deja afuera (para probar que falta). Al corregir no se agrega: el de la
    solicitud se conserva con `documentos_conservados`."""
    asignaciones = datos.get("asignaciones")
    if (formulario_3 and metodo == "POST" and isinstance(asignaciones, list)
            and not any(isinstance(a, dict) and a.get("documento_codigo") == FORMULARIO_3 for a in asignaciones)):
        datos = {**datos, "asignaciones": [*asignaciones, {"documento_codigo": FORMULARIO_3}]}
        archivos = [*archivos, pdf("formulario-3")]
    return await cliente.request(
        metodo, ruta, data={"solicitud": json.dumps(datos)},
        files=[("files", a) for a in archivos] or None, headers=actor.headers,
    )
