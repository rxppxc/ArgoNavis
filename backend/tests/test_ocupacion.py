"""La ocupación del tripulante salió del formulario (2026-11-16).

La columna queda y admite nulo: las solicitudes enviadas antes la conservan y la
siguen mostrando, en el expediente y en el PDF de la autorización. Al corregir una
devuelta se borra: el formulario ya no la pide y, si no, podría quedar pegada a otra
persona cuando la agencia cambia a alguien en la misma ficha.
"""
import secrets

import pytest
from sqlalchemy import update

from app.domain.models.solicitud import TripulanteSolicitud
from app.infrastructure.database import SesionLocal
from ayudas import cabecera, enviar, pdf, tripulante, verificar_impedimentos
from conftest import Actor, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

# Cambio de nave: a un marino panameño se le piden las Generales (y el Formulario No. 3,
# que agrega `enviar`).
CODIGO = "F3-CAMBIO-NAVE"


def _datos(puesto_id: int, ficha: dict) -> tuple[dict, list]:
    datos = cabecera(CODIGO, puesto_id, tripulantes=[ficha],
                     asignaciones=[{"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0}])
    return datos, [pdf("generales")]


@pytest.fixture(scope="module")
async def agencia(cliente, admin) -> tuple[Actor, int]:
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Ocupación {secrets.token_hex(2)}"},
                           headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Ocupación {secrets.token_hex(2)}",
                                                   "sector_id": await id_sector()}, headers=admin.headers)
    return naviera, r.json()["id"]


async def _enviada_con_ocupacion(cliente, naviera: Actor, puesto_id: int) -> dict:
    """Una solicitud como las de antes del 2026-11-16: el tripulante con su ocupación."""
    datos, archivos = _datos(puesto_id, tripulante("Ana", "PAN"))
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    async with SesionLocal() as sesion:
        await sesion.execute(update(TripulanteSolicitud).where(TripulanteSolicitud.solicitud_id == s["id"])
                             .values(ocupacion="Primer oficial"))
        await sesion.commit()
    return s


async def test_el_tripulante_va_sin_ocupacion(cliente, agencia):
    naviera, puesto_id = agencia
    ficha = tripulante("Ana", "PAN")
    assert "ocupacion" not in ficha
    datos, archivos = _datos(puesto_id, ficha)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["tripulantes"][0]["ocupacion"] is None


async def test_un_navegador_con_la_version_anterior_no_falla(cliente, agencia):
    """Mientras no recargue, la versión anterior del formulario todavía manda la
    ocupación: se ignora."""
    naviera, puesto_id = agencia
    datos, archivos = _datos(puesto_id, tripulante("Ana", "PAN", ocupacion="Capitán"))
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["tripulantes"][0]["ocupacion"] is None


async def test_la_ocupacion_vieja_se_sigue_viendo(cliente, agencia, monkeypatch):
    """En el expediente y en el PDF de la autorización (los datos con que se arma:
    el texto del PDF va comprimido)."""
    from app.informes.autorizacion_pdf import generar_pdf_autorizacion
    from app.infrastructure import emision

    naviera, puesto_id = agencia
    s = await _enviada_con_ocupacion(cliente, naviera, puesto_id)
    r = await cliente.get(f"/solicitudes/{s['id']}", headers=naviera.headers)
    assert r.json()["tripulantes"][0]["ocupacion"] == "Primer oficial"

    armados = []

    def capturar(datos):
        armados.append(datos)
        return generar_pdf_autorizacion(datos)

    monkeypatch.setattr(emision, "generar_pdf_autorizacion", capturar)   # se arma al emitirla (2026-11-22)
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    await verificar_impedimentos(cliente, revisor, s["id"])
    r = await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    r = await cliente.get(f"/solicitudes/{s['id']}/autorizacion.pdf", headers=naviera.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert armados[-1].tripulantes[0].ocupacion == "Primer oficial"


async def test_al_corregir_se_borra_la_ocupacion(cliente, agencia):
    naviera, puesto_id = agencia
    s = await _enviada_con_ocupacion(cliente, naviera, puesto_id)
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Revisar la documentación"},
                           headers=revisor.headers)
    assert r.status_code == 200, r.text

    t = s["tripulantes"][0]
    ficha = tripulante("Ana", "PAN", pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
    ficha["id"] = t["id"]
    correccion, _ = _datos(puesto_id, ficha)
    correccion.pop("codigo_tramite")
    correccion["asignaciones"] = []
    correccion["documentos_conservados"] = [d["id"] for d in s["documentos"]]
    r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["tripulantes"][0]["ocupacion"] is None


async def test_titulo_columna_rango():
    """La columna del PDF dice «Rango / Ocupación» solo si algún tripulante la tiene."""
    from app.informes.autorizacion_pdf import TripulantePdf, titulo_columna_rango

    def de_la_tabla(ocupacion: str | None) -> TripulantePdf:
        return TripulantePdf(nombre="Ana", apellido="Pérez", nacionalidad="Panamá", pasaporte="P1", libreta="",
                             rango="marino", ocupacion=ocupacion)

    assert titulo_columna_rango([de_la_tabla(None), de_la_tabla(None)]) == "Rango"
    assert titulo_columna_rango([de_la_tabla(None), de_la_tabla("Primer oficial")]) == "Rango / Ocupación"
    assert titulo_columna_rango([]) == "Rango"
