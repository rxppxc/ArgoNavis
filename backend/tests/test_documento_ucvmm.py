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

Siete reglas van más allá de la lectura literal, por decisión del usuario:
  - Ningún documento vencido: la vigencia bloquea en los 8 trámites (la Nota
    de la pág. 9 la pedía solo en Embarque, Visita médica y Shore Pass). Desde el
    2026-11-13, el pasaporte con al menos 3 meses a partir de la operación, y el
    seamanbook vencido ya no bloquea: se señala.
  - La Libreta de Marino en Embarque se pide a todo tripulante de rango
    Marino, sin importar la nacionalidad (el Form. 3 dice "Panameños").
  - A los rangos distintos de Marino (militar, técnico, supernumerario y
    superintendente) se les piden solo las Generales de pasaporte y el boleto
    aéreo, en todos los trámites (reunión del 2026-10-30). Por eso el resto de
    los documentos por tripulante es solo del Marino, el boleto se agrega para
    los demás rangos y el trámite de Técnico ya no lleva la Carta Form. 7.
  - En Embarque y Desembarque, a los técnicos (técnico, supernumerario y
    superintendente) se les pedían la Carta de Responsabilidad, las Generales y
    el Contrato de Trabajo (pedido del 2026-11-11). Desde el 2026-11-13 esos dos
    trámites admiten solo Marino, Pasajero y Militar; sus filas se borraron el
    2026-11-14.
    El Pasajero presenta lo del Marino sin la Libreta, en todos los trámites salvo
    el de Técnico, y el cambio de puerto va solo en Embarque y Desembarque.
  - El Formulario No. 3 se adjunta en todos los trámites, uno por solicitud, con
    todos los pasajeros y para cualquier rango; convive con la Lista de
    Tripulantes. Y el Cambio de Puerto deja de ser un trámite: en cualquiera se
    indica el cambio y el nuevo puesto, del mismo sector (pedido del 2026-11-13).
  - A todo pasajero de nacionalidad restringida, en cualquier trámite y rango, se
    le pide la Visa (DOC-VISA); a los panameños no se les pide visa ni boleto aéreo
    en Embarque y Desembarque, ni la Visa Especial de Marino en Cambio de nave; y el
    Sellado de Shore Pass admite solo el rango Marino (pedido del 2026-11-14).
  - En Embarque y Desembarque, la agencia responde «¿Subir y bajar?»; con «Sí»,
    cada pasajero, de cualquier rango, adjunta la Carta de Responsabilidad
    (Form. No. 7), además de lo demás (condición `subir_y_bajar`, 2026-11-16).
"""
import secrets
from datetime import date, timedelta

import pytest

from app.domain.models.solicitud import vigencia_minima_pasaporte
from ayudas import HOY, MANANA, cabecera, enviar, pdf, tripulante, verificar_impedimentos
from conftest import Actor, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

# (código, alcance, condición, rangos a los que se pide: None = a todos)
# Las filas del Marino incluyen al Pasajero (2026-11-13): un Marino sin libreta.
MARINO = ("marino", "pasajero")
NO_MARINOS = ("militar", "superintendente", "supernumerario", "tecnico")
CUSTODIA = ("DOC-FORM6-CUSTODIA", "marino", "nacionalidad_restringida", MARINO)   # Form. 3: solo Desembarque
GENERALES = ("DOC-GENERALES-PASAPORTE", "marino", "siempre", None)
VISA = ("DOC-VISA-MARINO", "marino", "siempre", MARINO)
# 2026-11-14: la Visa Especial de Marino de Embarque y Cambio de nave, no a los panameños,
# y la Visa de las nacionalidades restringidas, en todos los trámites y para cualquier rango.
VISA_EXTRANJEROS = ("DOC-VISA-MARINO", "marino", "solo_extranjeros", MARINO)
VISA_RESTRINGIDOS = ("DOC-VISA", "marino", "nacionalidad_restringida", None)
LIBRETA = ("DOC-LIBRETA-MARINO", "marino", "siempre", None)           # solo el Marino: requiere_libreta
LISTA = ("DOC-LISTA-TRIPULANTES", "solicitud", "siempre", None)       # "debe subirse al trámite"
CARTA = ("DOC-FORM7-RESPONSABILIDAD", "marino", "siempre", MARINO)    # "para cada tripulante"
REPORTE = ("DOC-REPORTE-MEDICO", "marino", "siempre", MARINO)         # "para cada tripulante"
CITA = ("DOC-CITA-CONSULADO", "marino", "siempre", MARINO)
BOLETO = ("DOC-BOLETO-AEREO", "marino", "siempre", NO_MARINOS)        # reunión del 2026-10-30
FORM3 = ("DOC-FORMULARIO-3", "solicitud", "siempre", None)           # en todos (2026-11-13)
# 2026-11-16: en Embarque y Desembarque, con «Subir y bajar: Sí», la Carta Form. 7 de cada pasajero.
CARTA_SUBIR_BAJAR = ("DOC-FORM7-RESPONSABILIDAD", "marino", "subir_y_bajar", None)
# En Embarque el boleto es solo del militar (2026-11-11). Los técnicos van por su trámite
# desde el 2026-11-13; sus filas de Embarque y Desembarque se borraron el 2026-11-14.
TECNICOS = ("superintendente", "supernumerario", "tecnico")
BOLETO_MILITAR = ("DOC-BOLETO-AEREO", "marino", "solo_extranjeros", ("militar",))   # no a panameños (2026-11-14)
# (trámite, documento) → rangos para los que es opcional: hoy ninguno.
OPCIONAL: dict[tuple[str, str], tuple[str, ...]] = {}

# campos: los propios del trámite (además de la cabecera común del Formulario 3)
# vigencia: si el pasaporte y el seamanbook vencidos impiden enviar (Nota de la pág. 9)
# aviso_custodia: si el proceso pide avisar al aprobar que se tramite la custodia
DOCUMENTO = {
    "F3-EMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": False, "cambio_puerto": True, "subir_y_bajar": True,
        "rangos": {"marino", "pasajero", "militar"},   # 2026-11-13: los técnicos van por su trámite
        "documentos": {FORM3, VISA_EXTRANJEROS, GENERALES, LIBRETA, BOLETO_MILITAR, VISA_RESTRINGIDOS,
                       CARTA_SUBIR_BAJAR},
    },
    "F3-DESEMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": True, "cambio_puerto": True, "subir_y_bajar": True,
        "rangos": {"marino", "pasajero", "militar"},
        # El boleto aéreo lo pide el Form. 3 a todos (también al Marino), menos a los panameños (2026-11-14).
        "documentos": {FORM3, ("DOC-BOLETO-AEREO", "marino", "solo_extranjeros", None), GENERALES, LIBRETA, LISTA,
                       CUSTODIA, VISA_RESTRINGIDOS, CARTA_SUBIR_BAJAR},
    },
    "F3-URGENCIA-MEDICA": {
        "campos": ["puerto_desembarque", "clinica_hospital"], "vigencia": True, "aviso_custodia": True,
        "documentos": {FORM3, CARTA, REPORTE, GENERALES, LIBRETA, BOLETO, VISA_RESTRINGIDOS},
    },
    "F3-RENOV-PASAPORTE": {
        "campos": ["puerto_desembarque"], "vigencia": True, "aviso_custodia": True,
        "documentos": {FORM3, GENERALES, CARTA, LISTA, LIBRETA, CITA, BOLETO, VISA_RESTRINGIDOS},
    },
    "F3-SHORE-PASS": {
        "campos": ["motivo"], "vigencia": True, "aviso_custodia": True,
        "rangos": {"marino"},   # 2026-11-14: solo el rango Marino
        "documentos": {FORM3, GENERALES, LISTA, LIBRETA, BOLETO, VISA_RESTRINGIDOS},
    },
    "F3-TECNICO": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "rangos": {"tecnico", "superintendente", "supernumerario"},
        # El Form. 3 pide la Carta Form. 7; desde el 2026-10-30, estos rangos presentan Generales y boleto.
        "documentos": {FORM3, GENERALES, BOLETO, VISA_RESTRINGIDOS},
    },
    "F3-CAMBIO-NAVE": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "documentos": {FORM3, VISA_EXTRANJEROS, GENERALES, BOLETO, VISA_RESTRINGIDOS},
    },
    # F3-CAMBIO-PUERTO: desde el 2026-11-13 no es un trámite (test_cambio_de_puerto_ya_no_es_un_tramite).
}

VALORES = {
    "puerto_desembarque": "Puerto de Cristóbal", "motivo": "Compras", "clinica_hospital": "Hospital Punta Pacífica",
}
ETIQUETAS = {
    "puerto_desembarque": "Puerto de desembarque", "motivo": "Motivo", "clinica_hospital": "Clínica u hospital",
}
LIBRETA_DOCS = {"DOC-LIBRETA-MARINO"}   # solo a quien porta seamanbook (rango Marino)


def _aplica(documento: tuple, t: dict, subir_y_bajar: bool = False) -> bool:
    codigo, _, condicion, rangos = documento
    if rangos and t["rango"] not in rangos:
        return False
    if codigo in LIBRETA_DOCS and t["rango"] != "marino":
        return False
    if condicion == "solo_extranjeros":
        return t["nacionalidad"] != "PAN"
    if condicion == "nacionalidad_restringida":
        return t["nacionalidad"] == "CUB"
    if condicion == "subir_y_bajar":
        return subir_y_bajar
    return True


def _asignaciones(codigo_tramite: str, tripulantes: list[dict], *, sin: set[str] = frozenset(),
                  subir_y_bajar: bool = False):
    """Asignaciones y archivos que el documento exige para estos tripulantes."""
    asignaciones, archivos = [], []
    for documento in sorted(DOCUMENTO[codigo_tramite]["documentos"]):
        codigo, alcance, condicion, _ = documento
        if codigo in sin:
            continue
        if alcance == "solicitud":
            if condicion == "nacionalidad_restringida" and not any(t["nacionalidad"] == "CUB" for t in tripulantes):
                continue
            if condicion == "subir_y_bajar" and not subir_y_bajar:
                continue
            asignaciones.append({"documento_codigo": codigo})
            archivos.append(pdf(codigo))
            continue
        for i, t in enumerate(tripulantes):
            if _aplica(documento, t, subir_y_bajar):
                asignaciones.append({"documento_codigo": codigo, "indice_tripulante": i})
                archivos.append(pdf(f"{codigo}-{i}"))
    return asignaciones, archivos


def _rango(codigo_tramite: str) -> str:
    """Un rango que el trámite admite: Marino, salvo en el de Técnico."""
    rangos = DOCUMENTO[codigo_tramite].get("rangos")
    return "marino" if not rangos or "marino" in rangos else "tecnico"


def _datos(codigo_tramite: str, puesto_id: int, tripulantes: list[dict], **extra) -> tuple[dict, list]:
    campos = {c: VALORES[c] for c in DOCUMENTO[codigo_tramite]["campos"]}
    asignaciones, archivos = _asignaciones(codigo_tramite, tripulantes, sin=extra.pop("sin", frozenset()),
                                           subir_y_bajar=extra.get("subir_y_bajar", False))
    datos = cabecera(codigo_tramite, puesto_id, tripulantes=tripulantes, asignaciones=asignaciones, **campos)
    datos.update(extra)
    return datos, archivos


@pytest.fixture(scope="module")
async def agencia(cliente, admin) -> tuple[Actor, int]:
    """Un usuario de agencia y un puesto, más Cuba como nacionalidad restringida."""
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Documento {secrets.token_hex(2)}"}, headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Documento {secrets.token_hex(2)}",
                                                   "sector_id": await id_sector()}, headers=admin.headers)
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
        documentos = {(d["codigo"], d["alcance"], d["condicion"], tuple(sorted(d["rangos"])) if d["rangos"] else None)
                      for d in tipo["documentos"]}
        assert documentos == esperado["documentos"], codigo
        # El Formulario No. 3, primero entre los de la solicitud (2026-11-13).
        de_la_solicitud = [d["codigo"] for d in tipo["documentos"] if d["alcance"] == "solicitud"]
        assert de_la_solicitud[0] == "DOC-FORMULARIO-3", codigo
        opcionales = {(codigo, d["codigo"]): tuple(sorted(d["rangos_opcional"]))
                      for d in tipo["documentos"] if d["rangos_opcional"]}
        assert opcionales == {k: v for k, v in OPCIONAL.items() if k[0] == codigo}, codigo
        assert tipo["valida_vigencia"] == esperado["vigencia"], codigo
        assert tipo["requiere_buque"], codigo   # nombre, IMO y bandera en todos
        assert tipo["requiere_puerto"] == ("nombre_puerto" in esperado["campos"]), codigo
        assert tipo["requiere_puerto_desembarque"] == ("puerto_desembarque" in esperado["campos"]), codigo
        assert tipo["requiere_motivo"] == ("motivo" in esperado["campos"]), codigo
        assert tipo["requiere_clinica"] == ("clinica_hospital" in esperado["campos"]), codigo
        assert set(tipo["rangos_permitidos"] or []) == esperado.get("rangos", set()), codigo
        assert tipo["aviso_custodia"] == esperado["aviso_custodia"], codigo
        assert tipo["permite_cambio_puerto"] == esperado.get("cambio_puerto", False), codigo
        assert tipo["permite_subir_y_bajar"] == esperado.get("subir_y_bajar", False), codigo


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
async def test_pasaporte_con_tres_meses_de_vigencia(cliente, agencia, codigo):
    """El pasaporte tiene que vencer al menos 3 meses después de la operación
    (pedido del 2026-11-13), en todos los trámites y rangos: un día antes no se
    envía; justo a los 3 meses, sí."""
    naviera, puesto_id = agencia
    minimo = vigencia_minima_pasaporte(date.fromisoformat(MANANA))   # la operación de cabecera()
    tripulantes = [tripulante("Luis", "PHL", rango=_rango(codigo), pasaporte_expira=(minimo - timedelta(days=1)).isoformat())]
    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "al menos 3 meses de vigencia" in r.json()["detail"], (codigo, r.text)

    tripulantes = [tripulante("Luis", "PHL", rango=_rango(codigo), pasaporte_expira=minimo.isoformat())]
    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert r.json()["tripulantes_con_alerta"] == 0


@pytest.mark.parametrize("codigo", sorted(c for c in DOCUMENTO if _rango(c) == "marino"))
async def test_seamanbook_vencido_no_impide_enviar(cliente, agencia, codigo):
    """El seamanbook vencido a la fecha de la operación no bloquea el envío
    (2026-11-13): el expediente lo señala, para la revisión."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Luis", "PHL", libreta_expira=HOY.isoformat())]
    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert r.json()["tripulantes"][0]["libreta_vencida"]
    assert r.json()["tripulantes_con_alerta"] == 1


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
    # Desde el 2026-11-14 se señala en todos los trámites: a los restringidos se les pide la Visa.
    assert r.json()["tiene_nacionalidad_restringida"], codigo


async def test_aviso_de_custodia_al_aprobar(cliente, admin, monkeypatch):
    """Al aprobar, el aviso a la agencia dice que debe tramitar la custodia
    solo en los trámites cuyo proceso lo indica; en los demás no la menciona.
    Recorre el camino real: la cola de salida y el envío (con un SMTP falso)."""
    from app.core import email

    mensajes = []

    async def smtp_falso(mensaje, **_):
        mensajes.append(mensaje)

    monkeypatch.setattr(email.configuracion, "MAIL_HOST", "smtp.prueba.local")
    monkeypatch.setattr(email.aiosmtplib, "send", smtp_falso)

    sufijo = secrets.token_hex(2)
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Custodia {sufijo}", "correo": "custodia@prueba.pa"},
                           headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Custodia {sufijo}", "correo": "puesto@prueba.pa",
                                                   "sector_id": await id_sector()},
                           headers=admin.headers)
    puesto_id = r.json()["id"]
    revisor = await crear_actor("UCVMM", prefijo="revisor")
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

        mensajes.clear()
        r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)
        assert r.status_code == 200, (codigo, r.text)
        assert r.json()["tipo_tramite_aviso_custodia"] == esperado["aviso_custodia"], codigo
        a_la_agencia = next(m for m in mensajes if "custodia@prueba.pa" in m["To"])
        assert a_la_agencia["Subject"] == f"Autorizaciones Marítimas · {r.json()['numero']} · Aprobada"
        texto = a_la_agencia.get_body(preferencelist=("plain",)).get_content()
        assert ("solicitud de custodia" in texto) == esperado["aviso_custodia"], codigo
        assert any("puesto@prueba.pa" in m["To"] for m in mensajes), "el puerto recibe su aviso"


async def test_seamanbook_solo_rango_marino(cliente, agencia):
    """Nota 3: militares, técnicos, supernumerarios y superintendentes no
    portan seamanbook: no se les pide ni se valida, ni se exige la libreta."""
    naviera, puesto_id = agencia
    sin_libreta = tripulante("Pedro", "PAN", rango="militar")
    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, [sin_libreta])
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


@pytest.mark.parametrize("codigo", sorted(set(DOCUMENTO) - {"F3-EMBARQUE", "F3-DESEMBARQUE", "F3-SHORE-PASS"}))
async def test_rangos_no_marinos_generales_y_boleto(cliente, agencia, codigo):
    """Reunión del 2026-10-30: a un rango distinto de Marino solo se le piden
    las Generales de pasaporte y el boleto aéreo. Embarque y Desembarque, abajo;
    Shore Pass admite solo al Marino (2026-11-14)."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Hans", "DEU", rango="tecnico")]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-BOLETO-AEREO"})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Boleto" in r.json()["detail"], (codigo, r.text)

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    del_tripulante = {c["documento_codigo"] for c in r.json()["checklist"] if c["tripulante_id"] is not None}
    assert del_tripulante == {"DOC-GENERALES-PASAPORTE", "DOC-BOLETO-AEREO"}, codigo


@pytest.mark.parametrize("codigo", ["F3-EMBARQUE", "F3-DESEMBARQUE"])
@pytest.mark.parametrize("rango", TECNICOS)
async def test_tecnicos_van_por_su_tramite(cliente, agencia, codigo, rango):
    """2026-11-13: Embarque y Desembarque admiten solo Marino, Pasajero y Militar; los
    técnicos, supernumerarios y superintendentes van por el trámite de Técnico."""
    naviera, puesto_id = agencia
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Hans", "DEU", rango=rango)])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "rango debe ser Marino, Pasajero, Militar" in r.json()["detail"], r.text


async def test_embarque_segun_el_rango(cliente, agencia):
    """En Embarque, el Pasajero presenta lo del Marino sin la Libreta (2026-11-13) y el
    militar sigue con Generales y boleto (reunión del 2026-10-30)."""
    naviera, puesto_id = agencia
    esperado = {"marino": {"DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO"},
                "pasajero": {"DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE"},
                "militar": {"DOC-GENERALES-PASAPORTE", "DOC-BOLETO-AEREO"}}
    for rango, documentos in esperado.items():
        datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Hans", "DEU", rango=rango)])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (rango, r.text)
        del_tripulante = {c["documento_codigo"] for c in r.json()["checklist"] if c["tripulante_id"] is not None}
        assert del_tripulante == documentos, rango
        assert all(c["obligatoria"] for c in r.json()["checklist"]), rango


@pytest.mark.parametrize("codigo", sorted(set(DOCUMENTO) - {"F3-TECNICO", "F3-SHORE-PASS"}))
async def test_el_pasajero_presenta_lo_del_marino_sin_libreta(cliente, agencia, codigo):
    """2026-11-13: en todos los trámites (salvo el de Técnico y, desde el 2026-11-14,
    Shore Pass), al Pasajero se le piden los documentos del Marino, sin la Libreta ni
    el seamanbook."""
    naviera, puesto_id = agencia
    marino, pasajero = tripulante("Ana", "PHL"), tripulante("Beto", "PHL", rango="pasajero")
    datos, archivos = _datos(codigo, puesto_id, [marino, pasajero])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    s = r.json()
    por_tripulante = {t["id"]: {c["documento_codigo"] for c in s["checklist"] if c["tripulante_id"] == t["id"]}
                      for t in s["tripulantes"]}
    del_marino, del_pasajero = (por_tripulante[t["id"]] for t in s["tripulantes"])
    assert del_pasajero == del_marino - {"DOC-LIBRETA-MARINO"}, codigo
    assert s["tripulantes"][1]["rango"] == "pasajero" and s["tripulantes"][1]["libreta_marino"] is None


async def test_el_pasajero_no_va_en_el_tramite_de_tecnico(cliente, agencia):
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-TECNICO", puesto_id, [tripulante("Beto", "PHL", rango="pasajero")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "rango debe ser Técnico" in r.json()["detail"], r.text


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

    cambio = {"tramite": codigo, "reporte": "DOC-REPORTE-MEDICO", "nuevo": "DOC-CITA-CONSULADO"}
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

        revisor = await crear_actor("UCVMM", prefijo="revisor")
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
        assert r.status_code == 400 and "cita del Consulado" in r.json()["detail"], "al corregir rigen las reglas de hoy"

        correccion["asignaciones"] = [{"documento_codigo": "DOC-REPORTE-MEDICO"},
                                      {"documento_codigo": "DOC-CITA-CONSULADO", "indice_tripulante": 0}]
        r = await enviar(cliente, naviera, correccion, [pdf("reporte-solicitud"), pdf("cita-0")], metodo="PUT", ruta=ruta)
        assert r.status_code == 200, r.text
        corregida = r.json()
        codigos = {(c["documento_codigo"], c["tripulante_id"]) for c in corregida["checklist"]}
        assert ("DOC-CITA-CONSULADO", t["id"]) in codigos and ("DOC-REPORTE-MEDICO", None) in codigos
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


async def test_pdf_sin_nombres_para_la_agencia(cliente, agencia):
    """En el PDF de la agencia, "Aprobada por" dice la institución (sin unidades
    internas desde el 2026-11-11); el nombre de quien
    aprobó va solo en la copia interna del SNM (reunión del 2026-10-30)."""
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    codigo = "F3-CAMBIO-NAVE"
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Juan", "PHL", rango=_rango(codigo))])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    impedimentos = {"tripulantes": [{"tripulante_id": t["id"], "con_impedimento": False} for t in r.json()["tripulantes"]]}
    assert (await cliente.post(f"/solicitudes/{sid}/impedimentos", json=impedimentos, headers=revisor.headers)).status_code == 200
    assert (await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)).status_code == 200

    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        datos = {}
        for clave, actor in (("agencia", naviera), ("snm", revisor)):
            ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(actor.id))
            datos[clave] = await svc.preparar_pdf(ctx, await svc.obtener(ctx, sid))
    assert datos["agencia"].aprobada_por == "Servicio Nacional de Migración" and not datos["agencia"].copia_interna
    assert datos["snm"].aprobada_por == "Revisor Prueba (UCVMM)" and datos["snm"].copia_interna


@pytest.mark.parametrize("codigo", sorted(DOCUMENTO))
async def test_formulario_3_en_todos_los_tramites(cliente, agencia, codigo):
    """2026-11-13: el Formulario No. 3, uno por solicitud con todos los pasajeros y
    para cualquier rango, es obligatorio en todos los trámites."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Ana", "PHL", rango=_rango(codigo)), tripulante("Beto", "PHL", rango=_rango(codigo))]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-FORMULARIO-3"})
    r = await enviar(cliente, naviera, datos, archivos, formulario_3=False)
    assert r.status_code == 400 and "Formulario No. 3" in r.json()["detail"], (codigo, r.text)

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    formulario = [c for c in r.json()["checklist"] if c["documento_codigo"] == "DOC-FORMULARIO-3"]
    assert len(formulario) == 1 and formulario[0]["tripulante_id"] is None and formulario[0]["obligatoria"], codigo


async def test_cambio_de_puerto_ya_no_es_un_tramite(cliente, agencia):
    """2026-11-13: el Cambio de Puerto se indica dentro de cualquier trámite. El
    trámite queda desactivado (no se ofrece ni se puede enviar), pero sigue en el
    catálogo para las solicitudes que ya lo usan."""
    naviera, puesto_id = agencia
    r = await cliente.get("/tramites", headers=naviera.headers)
    assert "F3-CAMBIO-PUERTO" not in {t["codigo"] for t in r.json()}
    r = await cliente.get("/tramites/F3-CAMBIO-PUERTO", headers=naviera.headers)
    assert r.status_code == 200 and r.json()["activo"] is False
    assert {d["codigo"] for d in r.json()["documentos"]} >= {"DOC-FORMULARIO-3"}, "una devuelta lo pide al corregir"

    datos = cabecera("F3-CAMBIO-PUERTO", puesto_id, nombre_puerto="Puerto de Balboa",
                     tripulantes=[tripulante("Ana")], asignaciones=[])
    r = await enviar(cliente, naviera, datos, [])
    assert r.status_code == 404, r.text


# ── 2026-11-14: la Visa de los restringidos, los panameños y Shore Pass ──────

def _del_pasajero(salida: dict, indice: int = 0) -> set[str]:
    tid = salida["tripulantes"][indice]["id"]
    return {c["documento_codigo"] for c in salida["checklist"] if c["tripulante_id"] == tid}


@pytest.mark.parametrize("codigo", sorted(DOCUMENTO))
async def test_visa_a_los_restringidos_en_todos_los_tramites(cliente, agencia, codigo):
    """A un pasajero de nacionalidad restringida se le exige la Visa en cualquier
    trámite; a uno que no lo es, no."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Raúl", "CUB", rango=_rango(codigo)), tripulante("Ana", "PHL", rango=_rango(codigo))]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-VISA"})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Visa de Raúl" in r.json()["detail"], (codigo, r.text)
    assert "Visa de Ana" not in r.json()["detail"], codigo

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert "DOC-VISA" in _del_pasajero(r.json(), 0) and "DOC-VISA" not in _del_pasajero(r.json(), 1), codigo


@pytest.mark.parametrize("rango", ["marino", "pasajero", "militar", "tecnico"])
async def test_visa_a_los_restringidos_de_cualquier_rango(cliente, agencia, rango):
    """En Urgencia médica, que admite cualquier rango, la Visa se le pide a todos los restringidos."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, [tripulante("Raúl", "CUB", rango=rango)])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (rango, r.text)
    assert "DOC-VISA" in _del_pasajero(r.json()), rango


GEN, LIB, VEM, BOL = "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO", "DOC-VISA-MARINO", "DOC-BOLETO-AEREO"


@pytest.mark.parametrize("codigo, rango, panameno, extranjero", [
    ("F3-EMBARQUE", "marino", {GEN, LIB}, {VEM, GEN, LIB}),
    ("F3-EMBARQUE", "pasajero", {GEN}, {VEM, GEN}),
    ("F3-EMBARQUE", "militar", {GEN}, {GEN, BOL}),
    ("F3-DESEMBARQUE", "marino", {GEN, LIB}, {BOL, GEN, LIB}),
    ("F3-DESEMBARQUE", "pasajero", {GEN}, {BOL, GEN}),
    ("F3-DESEMBARQUE", "militar", {GEN}, {BOL, GEN}),
    # En Cambio de nave, sin la Visa Especial de Marino; el boleto del militar sigue.
    ("F3-CAMBIO-NAVE", "marino", {GEN}, {VEM, GEN}),
    ("F3-CAMBIO-NAVE", "militar", {GEN, BOL}, {GEN, BOL}),
])
async def test_panamenos_sin_visa_ni_boleto(cliente, agencia, codigo, rango, panameno, extranjero):
    """2026-11-14: al panameño no se le pide visa ni boleto aéreo en Embarque y
    Desembarque (el marino presenta Generales y Libreta), ni la Visa Especial de
    Marino en Cambio de nave. A un extranjero del mismo rango, como antes."""
    naviera, puesto_id = agencia
    for nombre, nacionalidad, esperado in (("Mario", "PAN", panameno), ("Liu", "CHN", extranjero)):
        datos, archivos = _datos(codigo, puesto_id, [tripulante(nombre, nacionalidad, rango=rango)])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (codigo, rango, nacionalidad, r.text)
        assert _del_pasajero(r.json()) == esperado, (codigo, rango, nacionalidad)


async def test_shore_pass_solo_marino(cliente, agencia):
    """2026-11-14: el Sellado de Shore Pass admite solo el rango Marino."""
    naviera, puesto_id = agencia
    for rango in ("pasajero", "militar", "tecnico"):
        datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Beto", "PHL", rango=rango)])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 400 and "rango debe ser Marino" in r.json()["detail"], (rango, r.text)
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Ana", "PHL")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text


# ── 2026-11-16: «¿Subir y bajar?» en Embarque y Desembarque ─────────────────

CARTA_FORM7 = "DOC-FORM7-RESPONSABILIDAD"


@pytest.mark.parametrize("codigo", ["F3-EMBARQUE", "F3-DESEMBARQUE"])
async def test_subir_y_bajar_pide_la_carta_por_pasajero(cliente, agencia, codigo):
    """Con «Subir y bajar: Sí», cada pasajero (marino, pasajero o militar) adjunta la
    Carta de Responsabilidad (Form. No. 7); lo demás del trámite se sigue pidiendo."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Ana", "PHL"), tripulante("Beto", "PHL", rango="pasajero"),
                   tripulante("Ciro", "PHL", rango="militar")]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, subir_y_bajar=True, sin={CARTA_FORM7})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400, (codigo, r.text)
    for nombre in ("Ana", "Beto", "Ciro"):
        assert f"Carta de Responsabilidad (Form. No. 7) de {nombre}" in r.json()["detail"], (codigo, nombre)

    datos, archivos = _datos(codigo, puesto_id, tripulantes, subir_y_bajar=True)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    s = r.json()
    assert s["subir_y_bajar"] is True and s["permite_subir_y_bajar"] is True
    assert all(CARTA_FORM7 in _del_pasajero(s, i) for i in range(3)), codigo
    assert all(c["cubierta"] and c["obligatoria"] for c in s["checklist"]), codigo


@pytest.mark.parametrize("codigo", ["F3-EMBARQUE", "F3-DESEMBARQUE"])
async def test_sin_subir_y_bajar_no_pide_la_carta(cliente, agencia, codigo):
    """Sin la respuesta (o con «No»), la Carta no se pide."""
    naviera, puesto_id = agencia
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Ana", "PHL")])
    assert "subir_y_bajar" not in datos
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert r.json()["subir_y_bajar"] is False and r.json()["permite_subir_y_bajar"] is True
    assert CARTA_FORM7 not in _del_pasajero(r.json()), codigo


async def test_subir_y_bajar_se_ignora_en_otros_tramites(cliente, agencia):
    """Un trámite que no hace la pregunta descarta la respuesta (resto de otro trámite
    elegido antes en el formulario), como el cambio de puerto."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-CAMBIO-NAVE", puesto_id, [tripulante("Ana", "PHL")], subir_y_bajar=True)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["subir_y_bajar"] is False and r.json()["permite_subir_y_bajar"] is False


async def test_corregir_a_no_quita_la_carta(cliente, agencia):
    """Una devuelta que se corrige con «No» ya no pide la Carta: la foto del checklist
    se vuelve a tomar con la respuesta nueva."""
    naviera, puesto_id = agencia
    codigo = "F3-EMBARQUE"
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Ana", "PHL")], subir_y_bajar=True)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    assert CARTA_FORM7 in {c["documento_codigo"] for c in s["checklist"]}
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Revisar la documentación"},
                           headers=revisor.headers)
    assert r.status_code == 200, r.text

    t = s["tripulantes"][0]
    ficha = tripulante("Ana", "PHL", pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
    ficha["id"] = t["id"]
    correccion, _ = _datos(codigo, puesto_id, [ficha])
    correccion.pop("codigo_tramite")
    correccion["asignaciones"] = []
    correccion["documentos_conservados"] = [d["id"] for d in s["documentos"] if d["documento_codigo"] != CARTA_FORM7]
    r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    corregida = r.json()
    assert corregida["subir_y_bajar"] is False
    assert CARTA_FORM7 not in {c["documento_codigo"] for c in corregida["checklist"]}
    assert all(c["cubierta"] for c in corregida["checklist"])


async def test_el_pdf_dice_subir_y_bajar(cliente, agencia):
    """El PDF de la autorización dice la respuesta en los trámites que hacen la
    pregunta; en los demás no la menciona (None)."""
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    esperado = {("F3-EMBARQUE", True): True, ("F3-DESEMBARQUE", False): False, ("F3-CAMBIO-NAVE", True): None}
    for (codigo, subir_y_bajar), en_el_pdf in esperado.items():
        datos, archivos = _datos(codigo, puesto_id, [tripulante("Ana", "PHL")], subir_y_bajar=subir_y_bajar)
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (codigo, r.text)
        sid = r.json()["id"]
        await verificar_impedimentos(cliente, revisor, sid)
        r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)
        assert r.status_code == 200, (codigo, r.text)
        async with SesionLocal() as sesion:
            svc = ServicioSolicitud(sesion)
            ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(naviera.id))
            armado = await svc.preparar_pdf(ctx, await svc.obtener(ctx, sid))
        assert armado.subir_y_bajar is en_el_pdf, codigo
