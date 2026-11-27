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

Ocho reglas van más allá de la lectura literal, por decisión del usuario:
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
    Desde el 2026-11-26 no hay boleto en Embarque ni en Renovación de pasaporte:
    ahí presentan solo las Generales.
  - En Embarque y Desembarque, a los técnicos (técnico, supernumerario y
    superintendente) se les pedían la Carta de Responsabilidad, las Generales y
    el Contrato de Trabajo (pedido del 2026-11-11). Desde el 2026-11-13 esos dos
    trámites admiten solo Marino, Pasajero y Militar; sus filas se borraron el
    2026-11-14.
    El Pasajero presenta lo del Marino sin la Libreta, en todos los trámites salvo
    el de Técnico, y el cambio de puerto va solo en Embarque y Desembarque.
  - El Formulario No. 3 se adjunta en todos los trámites, uno por solicitud, con
    todos los tripulantes y para cualquier rango; convive con la Lista de
    Tripulantes. Y el Cambio de Puerto deja de ser un trámite: en cualquiera se
    indica el cambio y el nuevo puesto, del mismo sector (pedido del 2026-11-13).
  - La «Visa» (DOC-VISA) de los restringidos va solo en el trámite de Técnico, a
    cualquiera de sus rangos (2026-11-26; del 14 al 18 en todos los trámites y del 18 al
    26 también al Militar de los demás); al Marino y al Pasajero restringidos de los
    demás trámites, la Visa Especial de Marino. A los panameños no se les pide visa ni
    boleto aéreo en Embarque y Desembarque, ni la Visa Especial de Marino en Cambio de
    nave; y el Sellado de Shore Pass admite solo el rango Marino (pedido del 2026-11-14).
  - «Subir y bajar» es solo una operación del trámite de Técnico (2026-11-18; desde el
    2026-11-26 ningún otro la ofrece): con ella se adjunta la Carta de Responsabilidad
    (Form. No. 7) (condición `subir_y_bajar`), una por solicitud desde el 2026-11-26
    (antes, una por tripulante), con un documento propio que lleva los tres rangos del
    trámite en el nombre.
  - Pedido del 2026-11-26: la copia del boleto aéreo es opcional en Desembarque y en
    el trámite de Técnico (en los demás se sigue exigiendo); en Urgencia médica, la
    Carta de Responsabilidad (Form. No. 7) va una por solicitud, con los documentos de
    la solicitud, el trámite pide la operación (Embarque o Desembarque: solo se
    registra) y la autorización vale 120 horas desde la aprobación.
"""
import secrets
from datetime import date, datetime, timedelta

import pytest

from app.domain.models.solicitud import vigencia_minima_pasaporte
from ayudas import HOY, MANANA, cabecera, enviar, panama, pdf, tripulante, verificar_impedimentos
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
# Fuera del trámite de Técnico no se pide la «Visa» (2026-11-26; del 18 al 26 se le pedía al Militar);
# al Marino y al Pasajero restringidos se les exige la Visa Especial de Marino.
VISA_MARINO_RESTRINGIDO = ("DOC-VISA-MARINO", "marino", "nacionalidad_restringida", MARINO)
LIBRETA = ("DOC-LIBRETA-MARINO", "marino", "siempre", None)           # solo el Marino: requiere_libreta
LISTA = ("DOC-LISTA-TRIPULANTES", "solicitud", "siempre", None)       # "debe subirse al trámite"
CARTA = ("DOC-FORM7-RESPONSABILIDAD", "marino", "siempre", MARINO)    # "para cada tripulante"
# En Urgencia médica, una por solicitud (2026-11-26), si hay algún Marino o Pasajero.
CARTA_DE_LA_SOLICITUD = ("DOC-FORM7-RESPONSABILIDAD", "solicitud", "siempre", MARINO)
REPORTE = ("DOC-REPORTE-MEDICO", "marino", "siempre", MARINO)         # "para cada tripulante"
CITA = ("DOC-CITA-CONSULADO", "marino", "siempre", MARINO)
BOLETO = ("DOC-BOLETO-AEREO", "marino", "siempre", NO_MARINOS)        # reunión del 2026-10-30
FORM3 = ("DOC-FORMULARIO-3", "solicitud", "siempre", None)           # en todos (2026-11-13)
# Con «Subir y bajar», la Carta Form. 7: en Embarque y Desembarque del 2026-11-16 al 18; desde
# entonces, solo en el trámite de Técnico (su operación «Subir y bajar»). Una por solicitud desde
# el 2026-11-26 (antes, una por tripulante), con un documento propio: la carta «de Técnico,
# Superintendente o Supernumerario», con los rangos del trámite en el nombre.
CARTA_SUBIR_BAJAR = ("DOC-FORM7-TECNICO", "solicitud", "subir_y_bajar", None)
# 2026-11-18, en el trámite de Técnico, una por solicitud: con Embarque o Desembarque, la carta de
# garantía de la agencia contratante o el contrato; con «Subir y bajar», la carta de garantía.
GARANTIA_O_CONTRATO = ("DOC-GARANTIA-O-CONTRATO", "solicitud", "embarque_o_desembarque", None)
CARTA_GARANTIA = ("DOC-CARTA-GARANTIA", "solicitud", "subir_y_bajar", None)
# Los técnicos van por su trámite desde el 2026-11-13; sus filas de Embarque y Desembarque se
# borraron el 2026-11-14. Embarque no pide boleto desde el 2026-11-26 (era solo del militar).
TECNICOS = ("superintendente", "supernumerario", "tecnico")
# (trámite, documento) → rangos para los que es opcional: el boleto aéreo en Desembarque y en el
# trámite de Técnico (2026-11-26).
OPCIONAL: dict[tuple[str, str], tuple[str, ...]] = {
    ("F3-DESEMBARQUE", "DOC-BOLETO-AEREO"): ("marino", "militar", "pasajero"),
    ("F3-TECNICO", "DOC-BOLETO-AEREO"): ("superintendente", "supernumerario", "tecnico"),
}

# campos: los propios del trámite (además de la cabecera común del Formulario 3)
# vigencia: si el pasaporte y el seamanbook vencidos impiden enviar (Nota de la pág. 9)
# aviso_custodia: si el proceso pide avisar al aprobar que se tramite la custodia
DOCUMENTO = {
    "F3-EMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": False, "cambio_puerto": True,
        "rangos": {"marino", "pasajero", "militar"},   # 2026-11-13: los técnicos van por su trámite
        # La Visa Especial de Marino de todo extranjero cubre al Marino y al Pasajero restringidos.
        "documentos": {FORM3, VISA_EXTRANJEROS, GENERALES, LIBRETA},
    },
    "F3-DESEMBARQUE": {
        "campos": [], "vigencia": True, "aviso_custodia": True, "cambio_puerto": True,
        "rangos": {"marino", "pasajero", "militar"},
        # El boleto aéreo lo pide el Form. 3 a todos (también al Marino), menos a los panameños (2026-11-14).
        "documentos": {FORM3, ("DOC-BOLETO-AEREO", "marino", "solo_extranjeros", None), GENERALES, LIBRETA, LISTA,
                       CUSTODIA, VISA_MARINO_RESTRINGIDO},
    },
    "F3-URGENCIA-MEDICA": {
        "campos": ["puerto_desembarque", "clinica_hospital"], "vigencia": True, "aviso_custodia": True,
        # 2026-11-26: la operación como en Técnico y la autorización vale 120 horas desde la aprobación.
        "operacion": True, "operaciones": ("embarque", "desembarque"), "horas_vigencia": 120,
        "documentos": {FORM3, CARTA_DE_LA_SOLICITUD, REPORTE, GENERALES, LIBRETA, BOLETO, VISA_MARINO_RESTRINGIDO},
    },
    "F3-RENOV-PASAPORTE": {
        "campos": ["puerto_desembarque"], "vigencia": True, "aviso_custodia": True,
        # Sin boleto desde el 2026-11-26: los rangos que no son Marino presentan solo las Generales.
        "documentos": {FORM3, GENERALES, CARTA, LISTA, LIBRETA, CITA, VISA_MARINO_RESTRINGIDO},
    },
    "F3-SHORE-PASS": {
        "campos": ["motivo"], "vigencia": True, "aviso_custodia": True, "dias_sellado": True,
        "rangos": {"marino"},   # 2026-11-14: solo el rango Marino
        # Solo el Marino: sin la «Visa» del Militar (2026-11-18).
        "documentos": {FORM3, GENERALES, LISTA, LIBRETA, BOLETO, VISA_MARINO_RESTRINGIDO},
    },
    "F3-TECNICO": {
        "campos": [], "vigencia": True, "aviso_custodia": False, "operacion": True,
        "operaciones": ("embarque", "desembarque", "subir_y_bajar"),
        "rangos": {"tecnico", "superintendente", "supernumerario"},
        # El Form. 3 pide la Carta Form. 7; desde el 2026-10-30, estos rangos presentan Generales y boleto.
        # La «Visa» de los restringidos, a cualquiera de sus rangos, y la Carta con «Subir y bajar».
        "documentos": {FORM3, GENERALES, BOLETO, VISA_RESTRINGIDOS, CARTA_SUBIR_BAJAR, GARANTIA_O_CONTRATO,
                       CARTA_GARANTIA},
    },
    "F3-CAMBIO-NAVE": {
        "campos": [], "vigencia": True, "aviso_custodia": False,
        "documentos": {FORM3, VISA_EXTRANJEROS, GENERALES, BOLETO},
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
                  subir_y_bajar: bool = False, operacion: str | None = None):
    """Asignaciones y archivos que el documento exige para estos tripulantes."""
    asignaciones, archivos = [], []
    for documento in sorted(DOCUMENTO[codigo_tramite]["documentos"]):
        codigo, alcance, condicion, _ = documento
        if codigo in sin:
            continue
        if alcance == "solicitud":
            rangos = documento[3]
            if rangos and not any(t["rango"] in rangos for t in tripulantes):
                continue
            if condicion == "nacionalidad_restringida" and not any(t["nacionalidad"] == "CUB" for t in tripulantes):
                continue
            if condicion == "subir_y_bajar" and not subir_y_bajar:
                continue
            if condicion == "embarque_o_desembarque" and operacion not in ("embarque", "desembarque"):
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
    subir_y_bajar = extra.get("subir_y_bajar", False) or extra.get("operacion") == "subir_y_bajar"
    operacion = extra.get("operacion", "embarque") if DOCUMENTO[codigo_tramite].get("operacion") else None
    asignaciones, archivos = _asignaciones(codigo_tramite, tripulantes, sin=extra.pop("sin", frozenset()),
                                           subir_y_bajar=subir_y_bajar, operacion=operacion)
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
        assert tipo["pide_operacion"] == esperado.get("operacion", False), codigo
        assert tipo["pide_dias_sellado"] == esperado.get("dias_sellado", False), codigo
        assert tipo["horas_vigencia"] == esperado.get("horas_vigencia"), codigo
        assert tuple(tipo["operaciones"] or ()) == esperado.get("operaciones", ()), codigo


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


# El rango al que cada trámite le pide el boleto aéreo (Shore Pass no: solo admite Marino).
# Embarque y Renovación de pasaporte no lo piden desde el 2026-11-26.
RANGO_CON_BOLETO = {"F3-DESEMBARQUE": "marino", "F3-URGENCIA-MEDICA": "militar", "F3-TECNICO": "tecnico",
                    "F3-CAMBIO-NAVE": "militar"}


@pytest.mark.parametrize("codigo", sorted(RANGO_CON_BOLETO))
async def test_boleto_opcional_solo_en_desembarque_y_tecnico(cliente, agencia, codigo):
    """La copia del boleto aéreo es opcional en Desembarque y en el trámite de Técnico: sin ella
    se envía y su casilla queda como opcional. En los demás trámites se sigue exigiendo
    (pedido del 2026-11-26)."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Ana", "PHL", rango=RANGO_CON_BOLETO[codigo])]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-BOLETO-AEREO"})
    r = await enviar(cliente, naviera, datos, archivos)
    if codigo in ("F3-DESEMBARQUE", "F3-TECNICO"):
        assert r.status_code == 201, (codigo, r.text)
        boleto = next(c for c in r.json()["checklist"] if c["documento_codigo"] == "DOC-BOLETO-AEREO")
        assert not boleto["obligatoria"] and not boleto["cubierta"], boleto
    else:
        assert r.status_code == 400 and "Boleto" in r.json()["detail"], (codigo, r.text)


async def test_urgencia_una_carta_form7_por_solicitud(cliente, agencia):
    """En Urgencia médica, la Carta de Responsabilidad (Form. No. 7) es una sola para toda la
    solicitud, con los documentos de la solicitud (pedido del 2026-11-26). Antes, una por tripulante."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, [tripulante("Ana", "PHL"), tripulante("Beto", "PHL")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    cartas = [c for c in r.json()["checklist"] if c["documento_codigo"] == "DOC-FORM7-RESPONSABILIDAD"]
    assert len(cartas) == 1 and cartas[0]["alcance"] == "solicitud" and cartas[0]["tripulante_id"] is None, cartas
    assert cartas[0]["documento_nombre"] == "Carta de Responsabilidad (Form. No. 7)", "la de siempre, sin rangos"
    assert cartas[0]["cubierta"]


async def test_urgencia_pide_la_operacion(cliente, agencia):
    """Urgencia médica pide la operación: Embarque o Desembarque (2026-11-26). Solo se registra.
    «Subir y bajar» es solo del trámite de Técnico: aquí se rechaza."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Ana", "PHL")]
    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, tripulantes)
    datos["operacion"] = None
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Operación" in r.json()["detail"], r.text

    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, tripulantes, operacion="subir_y_bajar")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Subir y bajar" in r.json()["detail"], r.text

    datos, archivos = _datos("F3-URGENCIA-MEDICA", puesto_id, tripulantes, operacion="desembarque")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["operacion"] == "desembarque"
    codigos = [c["documento_codigo"] for c in r.json()["checklist"]]
    assert codigos.count("DOC-FORM7-RESPONSABILIDAD") == 1 and "DOC-GARANTIA-O-CONTRATO" not in codigos


async def test_urgencia_vale_120_horas_desde_la_aprobacion(cliente, admin, monkeypatch):
    """La autorización de Urgencia médica vale exactamente 120 horas desde que se aprueba, y el
    correo de la agencia lo dice. Los demás trámites siguen valiendo hasta el final del día, dos
    días después de la operación (pedido del 2026-11-26)."""
    from app.core import email
    from app.domain.services.solicitud_service import fin_del_dia

    mensajes = []

    async def smtp_falso(mensaje, **_):
        mensajes.append(mensaje)

    monkeypatch.setattr(email.configuracion, "MAIL_HOST", "smtp.prueba.local")
    monkeypatch.setattr(email.aiosmtplib, "send", smtp_falso)
    sufijo = secrets.token_hex(2)
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Vigencia {sufijo}", "correo": "vigencia@prueba.pa"},
                           headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Vigencia {sufijo}", "sector_id": await id_sector()},
                           headers=admin.headers)
    puesto_id = r.json()["id"]
    revisor = await crear_actor("UCVMM", prefijo="revisor")

    for codigo in ("F3-URGENCIA-MEDICA", "F3-DESEMBARQUE"):
        datos, archivos = _datos(codigo, puesto_id, [tripulante("Ana", "PHL")])
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (codigo, r.text)
        sid = r.json()["id"]
        await verificar_impedimentos(cliente, revisor, sid)
        mensajes.clear()
        r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)
        assert r.status_code == 200, (codigo, r.text)
        s = r.json()
        vigente = datetime.fromisoformat(s["vigente_hasta"])
        texto = next(m for m in mensajes if "vigencia@prueba.pa" in m["To"]).get_body(preferencelist=("plain",)).get_content()
        if codigo == "F3-URGENCIA-MEDICA":
            assert vigente - datetime.fromisoformat(s["aprobada_en"]) == timedelta(hours=120), s
            assert "120 horas (5 días) desde la aprobación" in texto, texto
            assert s["horas_vigencia"] == 120   # el expediente lo dice junto a «Vigente hasta»
        else:
            assert vigente == fin_del_dia(date.fromisoformat(s["fecha_operacion"]) + timedelta(days=2)), s
            assert "desde la aprobación" not in texto, texto
            assert s["horas_vigencia"] is None


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

    # El número y el vencimiento del seamanbook son opcionales (decisión del usuario, 2026-11-23);
    # la Libreta de Marino, como documento, se sigue pidiendo según el catálogo.
    marino = tripulante("Pedro", "PHL", libreta_marino=None, libreta_expira=None)
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [marino])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    t = r.json()["tripulantes"][0]
    assert t["libreta_marino"] is None and t["libreta_expira"] is None and not t["libreta_vencida"]


def test_celda_del_seamanbook_en_el_pdf():
    """En el PDF: el número; «No indicado» al Marino que no lo dio (opcional desde el 2026-11-23)
    y «No aplica» a los rangos que no portan seamanbook."""
    from app.informes.autorizacion_pdf import TripulantePdf, celda_libreta
    base = {"nombre": "Ana", "apellido": "Ruiz", "nacionalidad": "Filipinas", "pasaporte": "P1"}
    assert celda_libreta(TripulantePdf(**base, rango="marino", libreta="SB-1", porta_libreta=True)) == "SB-1"
    assert celda_libreta(TripulantePdf(**base, rango="marino", libreta="", porta_libreta=True)) == "No indicado"
    assert celda_libreta(TripulantePdf(**base, rango="militar", libreta="", porta_libreta=False)) == "No aplica"


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


@pytest.mark.parametrize("codigo", sorted(set(DOCUMENTO) - {"F3-EMBARQUE", "F3-DESEMBARQUE", "F3-SHORE-PASS",
                                                          "F3-RENOV-PASAPORTE"}))
async def test_rangos_no_marinos_generales_y_boleto(cliente, agencia, codigo):
    """Reunión del 2026-10-30: a un rango distinto de Marino solo se le piden
    las Generales de pasaporte y el boleto aéreo. Embarque, Desembarque y Renovación de
    pasaporte, abajo; Shore Pass admite solo al Marino (2026-11-14). En el trámite de
    Técnico el boleto es opcional desde el 2026-11-26."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Hans", "DEU", rango="tecnico")]
    datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={"DOC-BOLETO-AEREO"})
    r = await enviar(cliente, naviera, datos, archivos)
    if codigo == "F3-TECNICO":
        assert r.status_code == 201, (codigo, r.text)
    else:
        assert r.status_code == 400 and "Boleto" in r.json()["detail"], (codigo, r.text)

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    del_tripulante = {c["documento_codigo"] for c in r.json()["checklist"] if c["tripulante_id"] is not None}
    assert del_tripulante == {"DOC-GENERALES-PASAPORTE", "DOC-BOLETO-AEREO"}, codigo


@pytest.mark.parametrize("rango", NO_MARINOS)
async def test_renovacion_solo_generales_a_los_no_marinos(cliente, agencia, rango):
    """Pedido del 2026-11-26: en Renovación de pasaporte, al técnico, al supernumerario, al
    superintendente y al militar se les piden solo las Generales de pasaporte. Sin boleto aéreo."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-RENOV-PASAPORTE", puesto_id, [tripulante("Hans", "DEU", rango=rango)])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (rango, r.text)
    assert _del_tripulante(r.json()) == {"DOC-GENERALES-PASAPORTE"}, rango
    assert "DOC-BOLETO-AEREO" not in {c["documento_codigo"] for c in r.json()["checklist"]}, rango


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
    militar, solo las Generales: sin boleto desde el 2026-11-26 (antes, Generales y boleto)."""
    naviera, puesto_id = agencia
    esperado = {"marino": {"DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO"},
                "pasajero": {"DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE"},
                "militar": {"DOC-GENERALES-PASAPORTE"}}
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
    """2026-11-13: el Formulario No. 3, uno por solicitud con todos los tripulantes y
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

def _del_tripulante(salida: dict, indice: int = 0) -> set[str]:
    tid = salida["tripulantes"][indice]["id"]
    return {c["documento_codigo"] for c in salida["checklist"] if c["tripulante_id"] == tid}


# 2026-11-18: la visa que se le exige al tripulante de nacionalidad restringida, según el trámite
# y el rango (None: ninguna; se le sigue señalando).
VISA, VEM_ = "DOC-VISA", "DOC-VISA-MARINO"
VISA_ESPERADA = {
    ("F3-TECNICO", "tecnico"): VISA, ("F3-TECNICO", "superintendente"): VISA,
    # Fuera del trámite de Técnico, el Militar restringido ya no lleva la «Visa» (2026-11-26).
    ("F3-EMBARQUE", "marino"): VEM_, ("F3-EMBARQUE", "pasajero"): VEM_, ("F3-EMBARQUE", "militar"): None,
    ("F3-DESEMBARQUE", "marino"): VEM_, ("F3-DESEMBARQUE", "pasajero"): VEM_, ("F3-DESEMBARQUE", "militar"): None,
    ("F3-URGENCIA-MEDICA", "marino"): VEM_, ("F3-URGENCIA-MEDICA", "militar"): None,
    ("F3-URGENCIA-MEDICA", "tecnico"): None,   # un técnico fuera de su trámite: sin visa
    ("F3-RENOV-PASAPORTE", "pasajero"): VEM_, ("F3-RENOV-PASAPORTE", "militar"): None,
    ("F3-SHORE-PASS", "marino"): VEM_,
    ("F3-CAMBIO-NAVE", "marino"): VEM_, ("F3-CAMBIO-NAVE", "militar"): None,
}
NOMBRE_VISA = {VISA: "Visa de Raúl", VEM_: "Visa Especial de Marino de Raúl"}


@pytest.mark.parametrize(("codigo", "rango"), sorted(VISA_ESPERADA))
async def test_la_visa_de_los_restringidos(cliente, agencia, codigo, rango):
    """La «Visa» de los restringidos va solo en el trámite de Técnico (pedido del usuario del
    2026-11-26; del 18 al 26 también se le pedía al Militar de los demás); al Marino y al Pasajero
    restringidos de los demás trámites, la Visa Especial de Marino."""
    naviera, puesto_id = agencia
    visa = VISA_ESPERADA[(codigo, rango)]
    tripulantes = [tripulante("Raúl", "CUB", rango=rango), tripulante("Ana", "DEU", rango=rango)]
    if visa:
        datos, archivos = _datos(codigo, puesto_id, tripulantes, sin={visa})
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 400 and NOMBRE_VISA[visa] in r.json()["detail"], (codigo, rango, r.text)

    datos, archivos = _datos(codigo, puesto_id, tripulantes)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, rango, r.text)
    del_restringido, del_otro = _del_tripulante(r.json(), 0), _del_tripulante(r.json(), 1)
    otras = {VISA, VEM_} - {visa}
    assert (visa is None or visa in del_restringido) and not (otras - (del_otro & otras)) & del_restringido, (
        codigo, rango, del_restringido)
    assert VISA not in del_otro, "a quien no es restringido no se le pide la «Visa»"
    assert r.json()["tiene_nacionalidad_restringida"] is True, "se le sigue señalando"


GEN, LIB, VEM, BOL = "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO", "DOC-VISA-MARINO", "DOC-BOLETO-AEREO"


@pytest.mark.parametrize("codigo, rango, panameno, extranjero", [
    ("F3-EMBARQUE", "marino", {GEN, LIB}, {VEM, GEN, LIB}),
    ("F3-EMBARQUE", "pasajero", {GEN}, {VEM, GEN}),
    ("F3-EMBARQUE", "militar", {GEN}, {GEN}),   # sin boleto en Embarque desde el 2026-11-26
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
        assert _del_tripulante(r.json()) == esperado, (codigo, rango, nacionalidad)


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


# ── «Subir y bajar»: del 2026-11-16 al 18, en Embarque y Desembarque; desde entonces, solo
#    en el trámite de Técnico, como una de sus operaciones ────────────────────────────────

CARTA_FORM7 = "DOC-FORM7-RESPONSABILIDAD"
# La del trámite de Técnico (2026-11-26): un documento propio, con sus tres rangos en el nombre.
CARTA_TECNICO = "DOC-FORM7-TECNICO"
NOMBRE_CARTA_TECNICO = "Carta de Responsabilidad (Form. No. 7) de Técnico, Superintendente o Supernumerario"


async def test_subir_y_bajar_del_tecnico_pide_una_carta_por_solicitud(cliente, agencia):
    """Con la operación «Subir y bajar» se adjunta la Carta de Responsabilidad (Form. No. 7),
    además de lo demás del trámite (pedido del usuario del 2026-11-18): una sola para toda la
    solicitud desde el 2026-11-26 (antes, una por tripulante), con los tres rangos del trámite en su
    nombre. Con Embarque o Desembarque, no."""
    naviera, puesto_id = agencia
    tripulantes = [tripulante("Hans", "DEU", rango="tecnico"), tripulante("Ivo", "DEU", rango="superintendente")]
    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion="subir_y_bajar", sin={CARTA_TECNICO})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400, r.text
    assert NOMBRE_CARTA_TECNICO in r.json()["detail"], r.text
    assert "Hans" not in r.json()["detail"] and "Ivo" not in r.json()["detail"], "no es de un tripulante"

    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion="subir_y_bajar")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    cartas = [c for c in s["checklist"] if c["documento_codigo"] in (CARTA_TECNICO, CARTA_FORM7)]
    assert len(cartas) == 1 and cartas[0]["documento_codigo"] == CARTA_TECNICO, cartas
    assert cartas[0]["alcance"] == "solicitud" and cartas[0]["tripulante_id"] is None, cartas
    assert all(c["cubierta"] for c in s["checklist"])
    # Todo obligatorio salvo el boleto aéreo, opcional en este trámite desde el 2026-11-26.
    assert all(c["obligatoria"] == (c["documento_codigo"] != "DOC-BOLETO-AEREO") for c in s["checklist"])
    # Es la operación, no la pregunta de antes: el expediente no dice «Subir y bajar: Sí».
    assert s["operacion"] == "subir_y_bajar" and s["subir_y_bajar"] is False

    for operacion in ("embarque", "desembarque"):
        datos, archivos = _datos("F3-TECNICO", puesto_id, [tripulante("Hans", "DEU", rango="tecnico")],
                                 operacion=operacion)
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (operacion, r.text)
        assert not {CARTA_TECNICO, CARTA_FORM7} & {c["documento_codigo"] for c in r.json()["checklist"]}, operacion


@pytest.mark.parametrize("codigo", ["F3-EMBARQUE", "F3-DESEMBARQUE", "F3-CAMBIO-NAVE"])
async def test_los_demas_tramites_no_preguntan_subir_y_bajar(cliente, agencia, codigo):
    """Ningún otro trámite lo pregunta: una respuesta que llegue (un navegador con la versión
    anterior) se descarta, y la Carta no se pide."""
    naviera, puesto_id = agencia
    datos, archivos = _datos(codigo, puesto_id, [tripulante("Ana", "PHL")], subir_y_bajar=True)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, (codigo, r.text)
    assert r.json()["subir_y_bajar"] is False and r.json()["permite_subir_y_bajar"] is False
    assert not {CARTA_TECNICO, CARTA_FORM7} & {c["documento_codigo"] for c in r.json()["checklist"]}, codigo


async def test_corregir_a_otra_operacion_quita_la_carta(cliente, agencia):
    """Una devuelta que se corrige con Embarque ya no pide la Carta: la foto del checklist
    se vuelve a tomar con la operación nueva."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-TECNICO", puesto_id, [tripulante("Hans", "DEU", rango="tecnico")],
                             operacion="subir_y_bajar")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    assert CARTA_TECNICO in {c["documento_codigo"] for c in s["checklist"]}
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Revisar la operación"},
                           headers=revisor.headers)
    assert r.status_code == 200, r.text

    t = s["tripulantes"][0]
    ficha = tripulante("Hans", "DEU", rango="tecnico", pasaporte=t["pasaporte"])
    ficha["id"] = t["id"]
    correccion, _ = _datos("F3-TECNICO", puesto_id, [ficha], operacion="embarque")
    correccion.pop("codigo_tramite")
    correccion["asignaciones"] = []
    # Con Embarque se pide la garantía o el contrato en lugar de la carta de garantía (2026-11-18).
    correccion["asignaciones"] = [{"documento_codigo": "DOC-GARANTIA-O-CONTRATO"}]
    correccion["documentos_conservados"] = [d["id"] for d in s["documentos"]
                                            if d["documento_codigo"] not in (CARTA_TECNICO, "DOC-CARTA-GARANTIA")]
    r = await enviar(cliente, naviera, correccion, [pdf("garantia-o-contrato")], metodo="PUT",
                     ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    corregida = r.json()
    assert corregida["operacion"] == "embarque"
    assert CARTA_TECNICO not in {c["documento_codigo"] for c in corregida["checklist"]}
    assert all(c["cubierta"] for c in corregida["checklist"])


async def test_el_pdf_dice_subir_y_bajar_solo_en_las_de_antes(cliente, agencia):
    """Ningún trámite pregunta ya «¿Subir y bajar?»: el PDF lo dice solo en las de Embarque y
    Desembarque que respondieron «Sí» del 2026-11-16 al 18."""
    from sqlalchemy import update

    from app.domain.models.solicitud import Solicitud
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Ana", "PHL")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    await verificar_impedimentos(cliente, revisor, sid)
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=revisor.headers)
    assert r.status_code == 200, r.text

    async def armar():
        async with SesionLocal() as sesion:
            svc = ServicioSolicitud(sesion)
            ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(naviera.id))
            return await svc.preparar_pdf(ctx, await svc.obtener(ctx, sid))

    assert (await armar()).subir_y_bajar is None
    async with SesionLocal() as sesion:   # como una de antes que respondió «Sí»
        await sesion.execute(update(Solicitud).where(Solicitud.id == sid).values(subir_y_bajar=True))
        await sesion.commit()
    assert (await armar()).subir_y_bajar is True
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=naviera.headers)).json()
    assert detalle["subir_y_bajar"] is True and detalle["permite_subir_y_bajar"] is False


# ── 2026-11-18: la operación del trámite de Técnico ─────────────────────────

OPERACIONES = ("embarque", "desembarque", "subir_y_bajar")


def _tecnico(nombre: str = "Hans", **extra) -> dict:
    return tripulante(nombre, "DEU", rango="tecnico", **extra)


async def test_el_tramite_de_tecnico_pide_la_operacion(cliente, agencia):
    """Embarque, Desembarque o Subir y bajar (pedido del usuario del 2026-11-18): es
    obligatoria. Embarque y Desembarque piden lo mismo; Subir y bajar suma la Carta Form. 7
    de cada tripulante (test_subir_y_bajar_del_tecnico_pide_la_carta_por_tripulante)."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-TECNICO", puesto_id, [_tecnico()], operacion=None)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Operación" in r.json()["detail"], r.text

    checklists = set()
    for operacion in OPERACIONES:
        datos, archivos = _datos("F3-TECNICO", puesto_id, [_tecnico()], operacion=operacion)
        if operacion == "subir_y_bajar":
            r = await enviar(cliente, naviera, datos, archivos)
            assert r.status_code == 201 and r.json()["operacion"] == operacion, r.text
            continue
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (operacion, r.text)
        s = r.json()
        assert s["operacion"] == operacion and s["pide_operacion"] is True, operacion
        checklists.add(frozenset((c["documento_codigo"], c["tripulante_id"] is None) for c in s["checklist"]))
    assert len(checklists) == 1, "Embarque y Desembarque piden los mismos documentos"


async def test_una_operacion_que_no_existe(cliente, agencia):
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-TECNICO", puesto_id, [_tecnico()], operacion="transbordo")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 422 and "operación" in r.json()["detail"], r.text


async def test_la_operacion_se_ignora_en_otros_tramites(cliente, agencia):
    """Un trámite que no la pide la descarta (resto de otro trámite elegido antes), como
    «¿Subir y bajar?» y el cambio de puerto."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Ana", "PHL")], operacion="desembarque")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["operacion"] is None and r.json()["pide_operacion"] is False


async def test_la_operacion_en_la_bandeja_la_correccion_y_el_pdf(cliente, agencia):
    """Se ve en la tarjeta de la bandeja; una devuelta se corrige con otra; y el PDF de la
    autorización la dice."""
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-TECNICO", puesto_id, [_tecnico()], operacion="embarque")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    r = await cliente.get("/solicitudes/agencia", params={"texto": s["numero"]}, headers=naviera.headers)
    [fila] = [f for f in r.json()["items"] if f["id"] == s["id"]]
    assert fila["operacion"] == "embarque"

    revisor = await crear_actor("UCVMM", prefijo="revisor")
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Revisar la operación"},
                           headers=revisor.headers)
    assert r.status_code == 200, r.text
    t = s["tripulantes"][0]
    ficha = _tecnico(pasaporte=t["pasaporte"])
    ficha["id"] = t["id"]
    correccion, _ = _datos("F3-TECNICO", puesto_id, [ficha], operacion=None)
    correccion.pop("codigo_tramite")
    correccion["asignaciones"] = []
    correccion["documentos_conservados"] = [d["id"] for d in s["documentos"]]
    ruta = f"/solicitudes/{s['id']}"
    r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=ruta)
    assert r.status_code == 400 and "Operación" in r.json()["detail"], r.text
    correccion["operacion"] = "desembarque"
    r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=ruta)
    assert r.status_code == 200, r.text
    assert r.json()["operacion"] == "desembarque"

    await verificar_impedimentos(cliente, revisor, s["id"])
    r = await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(naviera.id))
        armado = await svc.preparar_pdf(ctx, await svc.obtener(ctx, s["id"]))
    assert armado.operacion == "Desembarque" and armado.subir_y_bajar is None


# ── 2026-11-18: los días del sellado de Shore Pass ──────────────────────────

async def test_shore_pass_pide_los_dias_del_sellado(cliente, agencia):
    """5 o 15 días (pedido del usuario del 2026-11-18): obligatorio y solo se registra:
    no cambia los documentos ni la vigencia de la autorización (decisión del usuario)."""
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Ana", "PHL")], dias_sellado=None)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Días del sellado" in r.json()["detail"], r.text

    checklists = set()
    for dias in (5, 15):
        datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Ana", "PHL")], dias_sellado=dias)
        r = await enviar(cliente, naviera, datos, archivos)
        assert r.status_code == 201, (dias, r.text)
        s = r.json()
        assert s["dias_sellado"] == dias and s["pide_dias_sellado"] is True, dias
        checklists.add(frozenset((c["documento_codigo"], c["tripulante_id"] is None) for c in s["checklist"]))
    assert len(checklists) == 1, "los mismos documentos con 5 y con 15"


async def test_dias_del_sellado_que_no_existen(cliente, agencia):
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Ana", "PHL")], dias_sellado=10)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 422 and "días del sellado" in r.json()["detail"], r.text


async def test_los_dias_del_sellado_se_ignoran_en_otros_tramites(cliente, agencia):
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Ana", "PHL")], dias_sellado=15)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert r.json()["dias_sellado"] is None and r.json()["pide_dias_sellado"] is False


async def test_los_dias_del_sellado_en_la_bandeja_la_correccion_y_el_pdf(cliente, agencia):
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud
    from app.infrastructure.database import SesionLocal

    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-SHORE-PASS", puesto_id, [tripulante("Ana", "PHL")], dias_sellado=5)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    r = await cliente.get("/solicitudes/agencia", params={"texto": s["numero"]}, headers=naviera.headers)
    [fila] = [f for f in r.json()["items"] if f["id"] == s["id"]]
    assert fila["dias_sellado"] == 5

    revisor = await crear_actor("UCVMM", prefijo="revisor")
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "Son 15 días"}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    t = s["tripulantes"][0]
    ficha = tripulante("Ana", "PHL", pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
    ficha["id"] = t["id"]
    correccion, _ = _datos("F3-SHORE-PASS", puesto_id, [ficha], dias_sellado=15)
    correccion.pop("codigo_tramite")
    correccion["asignaciones"] = []
    correccion["documentos_conservados"] = [d["id"] for d in s["documentos"]]
    r = await enviar(cliente, naviera, correccion, [], metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["dias_sellado"] == 15

    await verificar_impedimentos(cliente, revisor, s["id"])
    r = await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(naviera.id))
        armado = await svc.preparar_pdf(ctx, await svc.obtener(ctx, s["id"]))
    assert armado.dias_sellado == "15 días" and armado.operacion is None


# ── 2026-11-18: la carta de garantía del trámite de Técnico, según la operación ──

GARANTIA_O_CONTRATO_ = "DOC-GARANTIA-O-CONTRATO"
CARTA_GARANTIA_ = "DOC-CARTA-GARANTIA"


def _de_la_solicitud(salida: dict) -> set[str]:
    return {c["documento_codigo"] for c in salida["checklist"] if c["tripulante_id"] is None}


@pytest.mark.parametrize("operacion", ["embarque", "desembarque"])
async def test_embarque_o_desembarque_pide_garantia_o_contrato(cliente, agencia, operacion):
    """Pedido del usuario del 2026-11-18: con Embarque o Desembarque, una por solicitud, la carta
    de garantía de la agencia contratante o el contrato (cualquiera de los dos, en una casilla)."""
    naviera, puesto_id = agencia
    tripulantes = [_tecnico("Hans"), tripulante("Ivo", "DEU", rango="superintendente")]
    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion=operacion, sin={GARANTIA_O_CONTRATO_})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400, r.text
    assert "Carta de garantía de la agencia contratante o contrato" in r.json()["detail"], r.text

    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion=operacion)
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    assert _de_la_solicitud(r.json()) == {"DOC-FORMULARIO-3", GARANTIA_O_CONTRATO_}, "una sola, para todos"
    assert not {CARTA_TECNICO, CARTA_FORM7} & {c["documento_codigo"] for c in r.json()["checklist"]}


async def test_subir_y_bajar_pide_la_carta_de_garantia_y_la_form7(cliente, agencia):
    """Con «Subir y bajar», la carta de garantía y la Carta de Responsabilidad (Form. No. 7): se
    piden las dos (decisión del usuario del 2026-11-18), una por solicitud cada una (la Form. 7,
    desde el 2026-11-26)."""
    naviera, puesto_id = agencia
    tripulantes = [_tecnico("Hans"), tripulante("Ivo", "DEU", rango="superintendente")]
    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion="subir_y_bajar", sin={CARTA_GARANTIA_})
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 400 and "Carta de garantía de la agencia contratante" in r.json()["detail"], r.text
    assert "o contrato" not in r.json()["detail"], "con «Subir y bajar», solo la carta"

    datos, archivos = _datos("F3-TECNICO", puesto_id, tripulantes, operacion="subir_y_bajar")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    assert _de_la_solicitud(s) == {"DOC-FORMULARIO-3", CARTA_GARANTIA_, CARTA_TECNICO}
    assert all(not {CARTA_TECNICO, CARTA_FORM7} & _del_tripulante(s, i) for i in range(2))


async def test_la_garantia_no_se_pide_en_otros_tramites(cliente, agencia):
    naviera, puesto_id = agencia
    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Ana", "PHL")], operacion="embarque")
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    codigos = {c["documento_codigo"] for c in r.json()["checklist"]}
    assert not codigos & {GARANTIA_O_CONTRATO_, CARTA_GARANTIA_}


async def test_el_pdf_de_urgencia_dice_su_vigencia(monkeypatch):
    """El PDF de una autorización de Urgencia médica dice hasta qué hora vale y que son 120 horas
    desde la aprobación (2026-11-26); el de los demás trámites, solo el día."""
    from app.informes import autorizacion_pdf
    from app.informes.autorizacion_pdf import DatosPdfAutorizacion, generar_pdf_autorizacion

    parrafos: list[str] = []
    original = autorizacion_pdf.Paragraph
    monkeypatch.setattr(autorizacion_pdf, "Paragraph", lambda texto, *a, **k: (parrafos.append(texto), original(texto, *a, **k))[1])

    def datos(**cambios) -> DatosPdfAutorizacion:
        return DatosPdfAutorizacion(**{
            "numero": "AM-2026-000001", "estado": "approved", "tipo_tramite": "Urgencia médica", "nota_tramite": None,
            "aviso_custodia": False, "agencia_naviera": "Agencia", "nombre_buque": "Aurora", "imo": None, "bandera": None,
            "puesto_control": "Balboa", "fecha_operacion": date(2026, 11, 27), "nombre_puerto": None,
            "puerto_desembarque": None, "clinica_hospital": None, "motivo": None,
            "fecha_solicitud": panama(2026, 11, 26, 9), "aprobada_en": panama(2026, 11, 26, 10), "aprobada_por": "SNM",
            "copia_interna": False, "vigente_hasta": panama(2026, 12, 1, 10), "finalizada_en": None,
            "puesto_finalizacion": None, "expirada_en": None, "url_verificacion": "http://x/verificar/abc",
            "codigo_verificacion": "abc", "tripulantes": [], **cambios,
        })

    generar_pdf_autorizacion(datos(horas_vigencia=120))
    todo = " ".join(parrafos)
    assert "VIGENTE HASTA EL 01/12/2026 10:00 AM" in todo and "120 HORAS (5 DÍAS) DESDE LA APROBACIÓN" in todo, todo

    parrafos.clear()
    generar_pdf_autorizacion(datos(tipo_tramite="Desembarque", vigente_hasta=panama(2026, 11, 29, 23, 59)))
    todo = " ".join(parrafos)
    assert "VIGENTE HASTA EL 29/11/2026" in todo and "DESDE LA APROBACIÓN" not in todo and "11:59" not in todo, todo


async def test_las_aprobadas_antes_de_la_regla_no_dicen_las_120_horas():
    """Las horas se miran en la solicitud, no solo en el catálogo: una Urgencia médica aprobada antes
    del 2026-11-26 vale hasta el final del día y su PDF no dice «120 horas»."""
    from types import SimpleNamespace

    from app.domain.services.solicitud_service import ServicioSolicitud

    tipo = SimpleNamespace(horas_vigencia=120)
    aprobada = panama(2026, 11, 20, 10)
    nueva = SimpleNamespace(tipo_tramite=tipo, aprobada_en=aprobada, vigente_hasta=aprobada + timedelta(hours=120))
    antes = SimpleNamespace(tipo_tramite=tipo, aprobada_en=aprobada, vigente_hasta=panama(2026, 11, 23, 23, 59, 59))
    assert ServicioSolicitud.horas_vigencia(nueva) == 120
    assert ServicioSolicitud.horas_vigencia(antes) is None


async def test_al_devolver_la_agencia_ve_quien_tiene_impedimento(cliente, admin, monkeypatch):
    """Pedido del usuario del 2026-11-26: al devolverse una solicitud, la agencia ve qué
    tripulantes tienen impedimento según la revisión y que la solicitud no puede avanzar con
    ellos (en el expediente, el historial y el correo). Al corregir tiene que quitarlos: si va
    otra persona, la agrega como tripulante nuevo. Antes la verificación era solo interna, y
    lo sigue siendo en los demás estados."""
    from app.core import email

    mensajes = []

    async def smtp_falso(mensaje, **_):
        mensajes.append(mensaje)

    monkeypatch.setattr(email.configuracion, "MAIL_HOST", "smtp.prueba.local")
    monkeypatch.setattr(email.aiosmtplib, "send", smtp_falso)
    sufijo = secrets.token_hex(2)
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Impedimento {sufijo}", "correo": "impedimento@prueba.pa"},
                           headers=admin.headers)
    naviera = await crear_actor("Naviera", agencia_id=r.json()["id"], prefijo="naviera")
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Impedimento {sufijo}", "sector_id": await id_sector()},
                           headers=admin.headers)
    puesto_id = r.json()["id"]
    revisor = await crear_actor("UCVMM", prefijo="revisor")

    datos, archivos = _datos("F3-EMBARQUE", puesto_id, [tripulante("Ana", "PHL"), tripulante("Beto", "PHL")])
    r = await enviar(cliente, naviera, datos, archivos)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    await verificar_impedimentos(cliente, revisor, sid, con_impedimento={"Beto"})
    vista = (await cliente.get(f"/solicitudes/{sid}", headers=naviera.headers)).json()
    assert all(tr["con_impedimento"] is None for tr in vista["tripulantes"]), "en revisión sigue siendo interna"

    mensajes.clear()
    r = await cliente.post(f"/solicitudes/{sid}/devolver", json={"motivo": "Revisar la tripulación"}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    vista = (await cliente.get(f"/solicitudes/{sid}", headers=naviera.headers)).json()
    ana, beto = vista["tripulantes"]
    assert beto["con_impedimento"] is True and ana["con_impedimento"] is None, vista["tripulantes"]
    assert vista["tripulantes_con_impedimento"] == ["Beto Pérez"]
    devuelta = next(ev for ev in vista["eventos"] if ev["tipo"] == "devuelta")
    assert "Revisar la tripulación" in devuelta["comentario"] and "Beto Pérez" in devuelta["comentario"], devuelta
    correo = next(m for m in mensajes if "impedimento@prueba.pa" in m["To"]).get_body(preferencelist=("plain",)).get_content()
    assert "Beto Pérez" in correo and "no puede avanzar" in correo, correo
    assert vista["comentario_impedimentos"] is None, "el comentario de la verificación sigue siendo interno"

    def ficha(t: dict, nombre: str) -> dict:
        datos_ficha = tripulante(nombre, "PHL", pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
        datos_ficha["id"] = t["id"]
        return datos_ficha

    def correccion(fichas: list[dict], asignaciones: list[dict], conservar: set[int | None]) -> dict:
        datos_corr, _ = _datos("F3-EMBARQUE", puesto_id, fichas)
        datos_corr.pop("codigo_tramite")
        datos_corr["documentos_conservados"] = [d["id"] for d in vista["documentos"] if d["tripulante_id"] in conservar]
        datos_corr["asignaciones"] = asignaciones
        return datos_corr

    ruta = f"/solicitudes/{sid}"
    r = await enviar(cliente, naviera, correccion([ficha(ana, "Ana"), ficha(beto, "Beto")], [], {None, ana["id"], beto["id"]}),
                     [], metodo="PUT", ruta=ruta)
    assert r.status_code == 400 and "Beto Pérez tiene impedimento" in r.json()["detail"], r.text

    nueva = [{"documento_codigo": c, "indice_tripulante": 1}
             for c in ("DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO")]
    r = await enviar(cliente, naviera, correccion([ficha(ana, "Ana"), tripulante("Carla", "PHL")], nueva, {None, ana["id"]}),
                     [pdf("visa-carla"), pdf("generales-carla"), pdf("libreta-carla")], metodo="PUT", ruta=ruta)
    assert r.status_code == 200, r.text
    corregida = r.json()
    assert [tr["nombre"] for tr in corregida["tripulantes"]] == ["Ana", "Carla"]
    assert all(tr["con_impedimento"] is None for tr in corregida["tripulantes"]) and corregida["tripulantes_con_impedimento"] == []
