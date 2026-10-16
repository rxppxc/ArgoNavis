"""El Formulario No. 3 oficial (con su instructivo) y el documento de UCVMM
"Documentación requerida para las autorizaciones marítimas", trámite por
trámite, contra el sistema.

La tabla DOCUMENTO es la lectura literal de los documentos, sin criterio
propio; si el catálogo o las reglas se apartan de ella, estas pruebas fallan:

  - Qué documentos: los del recuadro del trámite en el Form. 3 (coinciden con
    los adjuntos del proceso; el Form. 3 además trae Generales en Desembarque).
  - Por tripulante: cada proceso dice "para cada tripulante el agente naviero
    debe subir…"; la Lista de Tripulantes es la excepción: "debe subirse al
    trámite" (pág. 9).
  - Custodia: el Form. No. 6 se adjunta solo en Desembarque ("cuando
    aplique"); los procesos de Desembarque, Urgencias, Renovación y Shore Pass
    piden avisar al aprobar que se debe tramitar la custodia.

Dos reglas van más allá de la lectura literal, por decisión del usuario:
  - Ningún documento vencido: la vigencia bloquea en los 8 trámites (la Nota
    de la pág. 9 la pedía solo en Embarque, Visita médica y Shore Pass).
  - La Libreta de Marino en Embarque se pide a todo tripulante de rango
    Marino, sin importar la nacionalidad (el Form. 3 dice "Panameños").
"""
import secrets

import pytest

from ayudas import HOY, cabecera, enviar, pdf, tripulante
from conftest import Actor, crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")

CUSTODIA = ("DOC-FORM6-CUSTODIA", "marino", "nacionalidad_restringida")   # Form. 3: solo Desembarque
GENERALES = ("DOC-GENERALES-PASAPORTE", "marino", "siempre")
VISA = ("DOC-VISA-MARINO", "marino", "siempre")
LIBRETA = ("DOC-LIBRETA-MARINO", "marino", "siempre")
LISTA = ("DOC-LISTA-TRIPULANTES", "solicitud", "siempre")            # "debe subirse al trámite"
CARTA = ("DOC-FORM7-RESPONSABILIDAD", "marino", "siempre")            # "para cada tripulante"
REPORTE = ("DOC-REPORTE-MEDICO", "marino", "siempre")                 # "para cada tripulante"

# campos: los propios del trámite (además de la cabecera común del Formulario 3)
# vigencia: si el pasaporte y el seamanbook vencidos impiden enviar (Nota de la pág. 9)
# aviso_custodia: si el proceso pide avisar al aprobar que se tramite la custodia
DOCUMENTO = {
    "F3-EMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "documentos": {VISA, GENERALES, LIBRETA},
    },
    "F3-DESEMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": True,
        "documentos": {("DOC-BOLETO-AEREO", "marino", "siempre"), GENERALES, LIBRETA, LISTA, CUSTODIA},
    },
    "F3-URGENCIA-MEDICA": {
        "campos": ["puerto_desembarque", "clinica_hospital"], "vigencia": True, "aviso_custodia": True,
        "documentos": {CARTA, REPORTE, GENERALES, LIBRETA},
    },
    "F3-RENOV-PASAPORTE": {
        "campos": ["puerto_desembarque"], "vigencia": True, "aviso_custodia": True,
        "documentos": {GENERALES, CARTA, LISTA, LIBRETA, ("DOC-CITA-CONSULADO", "marino", "siempre")},
    },
    "F3-SHORE-PASS": {
        "campos": ["motivo"], "vigencia": True, "aviso_custodia": True,
        "documentos": {GENERALES, LISTA, LIBRETA},
    },
    "F3-TECNICO": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "rangos": {"tecnico", "superintendente", "supernumerario"},
        "documentos": {CARTA, GENERALES},
    },
    "F3-CAMBIO-NAVE": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "documentos": {VISA, GENERALES},
    },
    "F3-CAMBIO-PUERTO": {
        "campos": ["nombre_puerto"], "vigencia": True, "aviso_custodia": False,
        "documentos": {VISA, GENERALES},
    },
}

VALORES = {
    "nombre_puerto": "Puerto de Balboa", "puerto_desembarque": "Puerto de Cristóbal",
    "motivo": "Compras", "clinica_hospital": "Hospital Punta Pacífica",
}
ETIQUETAS = {
    "nombre_puerto": "Nombre del puerto", "puerto_desembarque": "Puerto de desembarque",
    "motivo": "Motivo", "clinica_hospital": "Clínica u hospital",
}
LIBRETA_DOCS = {"DOC-LIBRETA-MARINO"}   # solo a quien porta seamanbook (rango Marino)


def _aplica(documento: tuple[str, str, str], t: dict) -> bool:
    codigo, _, condicion = documento
    if codigo in LIBRETA_DOCS and t["rango"] != "marino":
        return False
    if condicion == "solo_panamenos":
        return t["nacionalidad"] == "PAN"
    if condicion == "nacionalidad_restringida":
        return t["nacionalidad"] == "CUB"
    return True


def _asignaciones(codigo_tramite: str, tripulantes: list[dict], *, sin: set[str] = frozenset()):
    """Asignaciones y archivos que el documento exige para estos tripulantes."""
    asignaciones, archivos = [], []
    for documento in sorted(DOCUMENTO[codigo_tramite]["documentos"]):
        codigo, alcance, condicion = documento
        if codigo in sin:
            continue
        if alcance == "solicitud":
            if condicion == "nacionalidad_restringida" and not any(t["nacionalidad"] == "CUB" for t in tripulantes):
                continue
            asignaciones.append({"documento_codigo": codigo})
            archivos.append(pdf(codigo))
            continue
        for i, t in enumerate(tripulantes):
            if _aplica(documento, t):
                asignaciones.append({"documento_codigo": codigo, "indice_tripulante": i})
                archivos.append(pdf(f"{codigo}-{i}"))
    return asignaciones, archivos


def _rango(codigo_tramite: str) -> str:
    return "tecnico" if "rangos" in DOCUMENTO[codigo_tramite] else "marino"


def _datos(codigo_tramite: str, puesto_id: int, tripulantes: list[dict], **extra) -> tuple[dict, list]:
    campos = {c: VALORES[c] for c in DOCUMENTO[codigo_tramite]["campos"]}
    asignaciones, archivos = _asignaciones(codigo_tramite, tripulantes, sin=extra.pop("sin", frozenset()))
    datos = cabecera(codigo_tramite, puesto_id, tripulantes=tripulantes, asignaciones=asignaciones, **campos)
    datos.update(extra)
    return datos, archivos


@pytest.fixture(scope="module")
async def agencia(cliente, admin) -> tuple[Actor, int]:
    """Un usuario de agencia y un puesto, más Cuba como nacionalidad restringida."""
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Documento {secrets.token_hex(2)}"}, headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Documento {secrets.token_hex(2)}"}, headers=admin.headers)
    puesto_id = r.json()["id"]
    r = await cliente.patch("/admin/paises/CUB", json={"nacionalidad_restringida": True}, headers=admin.headers)
    assert r.status_code == 200
    return naviera, puesto_id


async def test_catalogo_igual_al_documento(cliente, agencia):
    naviera, _ = agencia
    r = await cliente.get("/tramites", headers=naviera.headers)
    tipos = {t["codigo"]: t for t in r.json()}
    assert set(tipos) == set(DOCUMENTO), "los 8 trámites del documento"
    for codigo, esperado in DOCUMENTO.items():
        tipo = tipos[codigo]
        documentos = {(d["codigo"], d["alcance"], d["condicion"]) for d in tipo["documentos"]}
        assert documentos == esperado["documentos"], codigo
        assert tipo["valida_vigencia"] == esperado["vigencia"], codigo
        assert tipo["requiere_buque"], codigo   # nombre, IMO y bandera en todos
        assert tipo["requiere_puerto"] == ("nombre_puerto" in esperado["campos"]), codigo
        assert tipo["requiere_puerto_desembarque"] == ("puerto_desembarque" in esperado["campos"]), codigo
        assert tipo["requiere_motivo"] == ("motivo" in esperado["campos"]), codigo
        assert tipo["requiere_clinica"] == ("clinica_hospital" in esperado["campos"]), codigo
        assert set(tipo["rangos_permitidos"] or []) == esperado.get("rangos", set()), codigo
        assert tipo["aviso_custodia"] == esperado["aviso_custodia"], codigo


@pytest.mark.parametrize("codigo", sorted(DOCUMENTO))
async def test_cada_tramite_con_sus_campos(cliente, agencia, codigo):
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Ana", "PHL", rango=_rango(codigo))]

    for campo in DOCUMENTO[codigo]["campos"]:
        datos, archivos = _datos(codigo, puesto_id, tripulantes)
        datos[campo] = None
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 400 and ETIQUETAS[campo] in r.json()["detail"], (codigo, campo, r.text)

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    s = r.json()
    assert all(c["cubierta"] for c in s["checklist"])
    assert s["cantidad_tripulantes"] == 1


@pytest.mark.parametrize("codigo", sorted(DOCUMENTO))
async def test_vigencia_del_pasaporte(cliente, agencia, codigo):
    """Vence antes de la operación: no se puede enviar en ningún trámite."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Luis", "PHL", rango=_rango(codigo), pasaporte_expira=HOY.isoformat())]
    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    if DOCUMENTO[codigo]["vigencia"]:
        assert r.status_code == 400 and "pasaporte vence" in r.json()["detail"], (codigo, r.text)
    else:
        assert r.status_code == 201, (codigo, r.text)
        assert r.json()["tripulantes_con_alerta"] == 1
        assert r.json()["tripulantes"][0]["pasaporte_vencido"]


@pytest.mark.parametrize("codigo", sorted(DOCUMENTO))
async def test_custodia_segun_el_formulario(cliente, agencia, codigo):
    """Un tripulante de nacionalidad restringida sin Form. No. 6: solo
    Desembarque lo exige para enviar; en los demás trámites se envía."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Raúl", "CUB", rango=_rango(codigo))]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-FORM6-CUSTODIA"})
    r = await enviar(cliente, naviera, datos, archivos)
    if CUSTODIA in DOCUMENTO[codigo]["documentos"]:
        assert codigo == "F3-DESEMBARQUE"
        assert r.status_code == 400 and "Formulario No. 6" in r.json()["detail"], (codigo, r.text)
        datos, archivos = _datos(codigo, puesto_id, tripulantes)
        r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert r.json()["tiene_nacionalidad_restringida"] == DOCUMENTO[codigo]["aviso_custodia"], codigo


async def test_aviso_de_custodia_al_aprobar(cliente, admin, monkeypatch):
    """Al aprobar, el aviso a la agencia dice que debe tramitar la custodia
    solo en los trámites cuyo proceso lo indica; en los demás no la menciona."""
    import app.api.v1.solicitudes as rutas_solicitudes

    avisos = []

    async def capturar(aviso):
        avisos.append(aviso)

    monkeypatch.setattr(rutas_solicitudes, "enviar_aviso", capturar)

    sufijo = secrets.token_hex(2)
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Custodia {sufijo}", "correo": "custodia@prueba.pa"},
                           headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Custodia {sufijo}", "correo": "puesto@prueba.pa"},
                           headers=admin.headers)
    puesto_id = r.json()["id"]
    revisor = await crear_actor("Sector Pacífico", prefijo="revisor")
    r = await cliente.patch("/admin/paises/CUB", json={"nacionalidad_restringida": True}, headers=admin.headers)
    assert r.status_code == 200

    for codigo, esperado in DOCUMENTO.items():
        datos, archivos = _datos(codigo, puesto_id, [tripulante("Raúl", "CUB", rango=_rango(codigo))])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (codigo, r.text)
        sid = r.json()["id"]
        impedimentos = {"tripulantes": [{"tripulante_id": tr["id"], "con_impedimento": False} for tr in r.json()["tripulantes"]],
                        "comentario": "Sin impedimentos"}
        r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=impedimentos, headers=revisor.headers)
        assert r.status_code == 200, r.text

        avisos.clear()
        r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)
        assert r.status_code == 200, (codigo, r.text)
        assert r.json()["tipo_tramite_aviso_custodia"] == esperado["aviso_custodia"], codigo
        a_la_agencia = next(a for a in avisos if "custodia@prueba.pa" in a.destinatarios)
        assert a_la_agencia.asunto == f"Autorizaciones Marítimas · {r.json()['numero']} · Aprobada"
        assert ("solicitud de custodia" in (a_la_agencia.destacado or "")) == esperado["aviso_custodia"], codigo
        assert any("puesto@prueba.pa" in a.destinatarios for a in avisos), "el puerto recibe su aviso"


async def test_seamanbook_solo_rango_marino(cliente, agencia):
    """Nota 3: militares, técnicos, supernumerarios y superintendentes no
    portan seamanbook: no se les pide ni se valida, ni se exige la libreta."""
    naviera, puesto_id = agencia
    sin_libreta = tripulante("Pedro", "PAN", rango="militar")
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [sin_libreta])
    assert not any(a.get("documento_codigo") == "DOC-LIBRETA-MARINO" for a in datos["asignaciones"])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text

    marino = tripulante("Pedro", "PHL", libreta_marino=None, libreta_expira=None)
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [marino])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "seamanbook" in r.json()["detail"]


async def test_libreta_en_embarque_todos_los_marinos(cliente, agencia):
    """La Libreta de Marino en Embarque se exige a cualquier nacionalidad (rango Marino)."""
    naviera, puesto_id = agencia
    for nombre, nacionalidad in (("Mario", "PAN"), ("Liu", "CHN")):
        marino = tripulante(nombre, nacionalidad)
        datos, archivos = _datos("F3-EMBARQUE", puesto_id, [marino], sin={"DOC-LIBRETA-MARINO"})
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 400 and "Libreta de Marino" in r.json()["detail"], nacionalidad
        datos, archivos = _datos("F3-EMBARQUE", puesto_id, [marino])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (nacionalidad, r.text)

    sin_libreta = tripulante("Pedro", "CHN", rango="militar")
    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [sin_libreta])
    assert not any(a.get("documento_codigo") == "DOC-LIBRETA-MARINO" for a in datos["asignaciones"])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, "quien no porta seamanbook no presenta libreta"


async def test_tramite_tecnico_solo_sus_rangos(cliente, agencia):
    naviera, puesto_id = agencia
    for rango in ("tecnico", "superintendente", "supernumerario"):
        datos, archivos = _datos("F3-TECNICO", puesto_id, [tripulante("Hans", "DEU", rango=rango)])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (rango, r.text)
    datos, archivos = _datos("F3-TECNICO", puesto_id, [tripulante("Hans", "DEU", rango="marino")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "rango debe ser Técnico, Superintendente, Supernumerario" in r.json()["detail"]


async def test_cambio_de_catalogo_no_altera_solicitudes_enviadas(cliente, agencia):
    """El expediente se juzga con el checklist con el que se envió la solicitud:
    si después el catálogo cambia (un documento pasa a ser "por solicitud" y se
    exige uno nuevo), la solicitud no queda incompleta. Al corregir, en cambio,
    rigen las reglas del día y la foto se vuelve a tomar."""
    from sqlalchemy import text

    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    codigo = "F3-URGENCIA-MEDICA"
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Arjun", "IND", rango=_rango(codigo))])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    antes = {(c["documento_codigo"], c["tripulante_id"]) for c in s["checklist"]}
    assert antes and all(c["cubierta"] for c in s["checklist"])

    cambio = {"tramite": codigo, "reporte": "DOC-REPORTE-MEDICO", "nuevo": "DOC-BOLETO-AEREO"}
    sql_ids = ("(SELECT id FROM tipos_tramite WHERE codigo = :tramite)",
               "(SELECT id FROM documentos_requeridos WHERE codigo = :reporte)",
               "(SELECT id FROM documentos_requeridos WHERE codigo = :nuevo)")
    async with SesionLocal() as sesion:
        await sesion.execute(text(f"UPDATE tramite_documentos SET alcance = 'solicitud' "
                                  f"WHERE tipo_tramite_id = {sql_ids[0]} AND documento_id = {sql_ids[1]}"), cambio)
        await sesion.execute(text(f"INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden) "
                                  f"VALUES ({sql_ids[0]}, {sql_ids[2]}, 'marino', 'siempre', 99)"), cambio)
        await sesion.commit()
    try:
        r = await cliente.get(f"/solicitudes/{s['id']}", headers=naviera.headers)
        detalle = r.json()
        assert {(c["documento_codigo"], c["tripulante_id"]) for c in detalle["checklist"]} == antes
        assert all(c["cubierta"] for c in detalle["checklist"]), "sigue completa: se juzga con las reglas con que se envió"

        revisor = await crear_actor("Sector Pacífico", prefijo="revisor")
        r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Revisar la documentación"},
                               headers=revisor.headers)
        assert r.status_code == 200, r.text

        t = detalle["tripulantes"][0]
        ficha = tripulante("Arjun", "IND", rango=_rango(codigo), pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
        ficha["id"] = t["id"]
        correccion, _ = _datos(codigo, puesto_id, [ficha])
        correccion.pop("codigo_tramite")
        correccion["documentos_conservados"] = [d["id"] for d in detalle["documentos"]]
        correccion["asignaciones"] = []
        ruta = f"/solicitudes/{s['id']}"
        r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=ruta)
        assert r.status_code == 400 and "Boleto" in r.json()["detail"], "al corregir rigen las reglas de hoy"

        correccion["asignaciones"] = [{"documento_codigo": "DOC-REPORTE-MEDICO"},
                                      {"documento_codigo": "DOC-BOLETO-AEREO", "indice_tripulante": 0}]
        r = await enviar(cliente, naviera, correccion, [pdf("reporte-solicitud"), pdf("boleto-0")], metodo="PUT", ruta=ruta)
        assert r.status_code == 200, r.text
        corregida = r.json()
        codigos = {(c["documento_codigo"], c["tripulante_id"]) for c in corregida["checklist"]}
        assert ("DOC-BOLETO-AEREO", t["id"]) in codigos and ("DOC-REPORTE-MEDICO", None) in codigos
        assert all(c["cubierta"] for c in corregida["checklist"]), "la foto nueva sale de las reglas de hoy"
    finally:
        async with SesionLocal() as sesion:
            await sesion.execute(text(f"DELETE FROM tramite_documentos "
                                      f"WHERE tipo_tramite_id = {sql_ids[0]} AND documento_id = {sql_ids[2]}"), cambio)
            await sesion.execute(text(f"UPDATE tramite_documentos SET alcance = 'marino' "
                                      f"WHERE tipo_tramite_id = {sql_ids[0]} AND documento_id = {sql_ids[1]}"), cambio)
            await sesion.commit()


async def test_word_y_excel_ademas_de_pdf(cliente, agencia):
    """Las casillas del checklist aceptan Word y Excel además de PDF."""
    from ayudas import MIME_DOCX, MIME_XLSX, docx, xlsx

    naviera, puesto_id = agencia
    codigo = "F3-CAMBIO-NAVE"
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Juan", "PHL", rango=_rango(codigo))])
    archivos[0], archivos[1] = docx("visa"), xlsx("generales")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert {MIME_DOCX, MIME_XLSX} <= {d["tipo_mime"] for d in r.json()["documentos"]}
    assert all(c["cubierta"] for c in r.json()["checklist"])


async def test_pdf_sin_nombres_de_funcionarios(cliente, agencia):
    """El PDF lo recibe la agencia: "Aprobada por" dice UCVMM, no el nombre de quien aprobó."""
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    codigo = "F3-CAMBIO-NAVE"
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Juan", "PHL", rango=_rango(codigo))])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    revisor = await crear_actor("Sector Pacífico", prefijo="revisor")
    impedimentos = {"tripulantes": [{"tripulante_id": t["id"], "con_impedimento": False} for t in r.json()["tripulantes"]]}
    assert (await cliente.post(f"/solicitudes/{sid}/impedimentos", json=impedimentos, headers=revisor.headers)).status_code == 200
    assert (await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)).status_code == 200

    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(naviera.id))
        pdf_datos = await svc.preparar_pdf(ctx, await svc.obtener(ctx, sid))
    assert pdf_datos.aprobada_por == "UCVMM"
