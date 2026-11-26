"""Boleta de recargo por atención fuera del horario laboral (2026-11-16).

Cuando UCVMM aprueba fuera del horario, la solicitud lleva un recargo. UCVMM, el
supervisor de sector y el puesto de control generan la boleta para cobrarlo, con
un número de oficio que escriben ellos: único entre todas las boletas, también
las anuladas, sin distinguir mayúsculas. Como en un talonario, una boleta mal
hecha se anula (con motivo) y se genera otra; hay una sola vigente por
solicitud. La agencia no la ve: la imprime el SNM y se la entrega.
"""
import asyncio
import itertools
import secrets
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import insert, select

from app.core.horario import ZONA_PANAMA
from app.core.texto import slug
from app.domain.models.audit_log import AccionAuditoria, RegistroAuditoria
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl, usuarios_puestos
from app.domain.models.solicitud import Solicitud
from app.domain.models.tramite import TipoTramite
from app.infrastructure.database import SesionLocal
from ayudas import panama
from conftest import ATLANTICO, PACIFICO, Actor, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

_contador = itertools.count(1)


# ── El PDF ───────────────────────────────────────────────────────────────────

def _datos_pdf():
    from app.informes.boleta_recargo_pdf import DatosPdfBoleta

    return DatosPdfBoleta(
        numero_oficio="UCVMM-045-2026", monto=Decimal("20.00"), numero_solicitud="AM-2026-000123",
        tipo_tramite="Embarque", agencia="Naviera del Istmo, S.A.", buque="MSC ARIES", imo="9074729",
        puesto="Balboa", puesto_destino=None, fecha_operacion=date(2026, 11, 20), cantidad_tripulantes=3,
        aprobada_en=panama(2026, 11, 14, 16, 20), generada_en=panama(2026, 11, 15, 10, 5),
        anulada_en=None, motivo_anulacion=None,
        tipos_operacion=["Embarque", "Desembarque", "Cambio de Nave", "Urgencias o Atención Médica"],
        subir_y_bajar=True,
    )


async def test_casillas_operacion():
    """El tipo de operación va en casillas, como en papel (2026-11-16): todos los
    trámites, con la X en el de la solicitud."""
    from app.informes.boleta_recargo_pdf import casillas_operacion

    tipos = ["Embarque", "Desembarque", "Cambio de Nave"]
    assert casillas_operacion(tipos, "Desembarque") == [
        ("Embarque", False), ("Desembarque", True), ("Cambio de Nave", False),
    ]
    # Un trámite que ya no está activo (Cambio de Puerto, 2026-11-13) se suma al final, marcado.
    assert casillas_operacion(tipos, "Cambio de Puerto") == [
        ("Embarque", False), ("Desembarque", False), ("Cambio de Nave", False), ("Cambio de Puerto", True),
    ]


async def test_pdf_de_la_boleta():
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    vigente = generar_pdf_boleta(_datos_pdf())
    assert vigente[:5] == b"%PDF-" and vigente.rstrip().endswith(b"%%EOF")
    assert b"Boleta de recargo AM-2026-000123" in vigente, "el título del documento"
    anulada = generar_pdf_boleta(replace(_datos_pdf(), anulada_en=panama(2026, 11, 15, 11, 0),
                                         motivo_anulacion="El número de oficio estaba mal escrito."))
    assert anulada[:5] == b"%PDF-" and len(anulada) > len(vigente), "lleva el sello y la anulación"
    # Un trámite que no pregunta «¿Subir y bajar?» va sin esa línea.
    sin_pregunta = generar_pdf_boleta(replace(_datos_pdf(), tipo_tramite="Cambio de Nave", subir_y_bajar=None))
    assert sin_pregunta[:5] == b"%PDF-" and len(sin_pregunta) < len(vigente)
    # El de Técnico lleva la operación en casillas (2026-11-18) en lugar de «¿Subir y bajar?».
    con_operacion = generar_pdf_boleta(replace(
        _datos_pdf(), tipo_tramite="Autorización de Técnico, Superintendente o Supernumerario", subir_y_bajar=None,
        elecciones=[("OPERACIÓN", ("Embarque", "Desembarque", "Subir y bajar"), "Subir y bajar")],
    ))
    assert con_operacion[:5] == b"%PDF-" and len(con_operacion) > len(sin_pregunta)


# ── Reglas, rutas y bitácora ─────────────────────────────────────────────────

def _ultimo_sabado_a_las_10() -> datetime:
    dia = datetime.now(ZONA_PANAMA).date() - timedelta(days=1)
    while dia.weekday() != 5:
        dia -= timedelta(days=1)
    return datetime.combine(dia, time(10, 0), ZONA_PANAMA)


@dataclass
class Escenario:
    sufijo:       str
    agencia_id:   int
    agencia:      str
    puesto_id:    int
    puesto:       str
    naviera:      Actor
    revisor:      Actor
    revisor_atl:  Actor
    sup_sector:   Actor
    general:      Actor
    del_puesto:   Actor
    puesto_ajeno: Actor


@pytest.fixture(scope="module")
async def esc(cliente) -> Escenario:
    """Una agencia, un puesto en cada sector y los actores de la boleta."""
    sufijo = secrets.token_hex(3)
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia Boletas {sufijo}")
        puesto = PuestoControl(nombre=f"Puesto Boletas {sufijo}", sector_id=await id_sector(PACIFICO))
        puesto_atl = PuestoControl(nombre=f"Puesto Boletas Atl {sufijo}", sector_id=await id_sector(ATLANTICO))
        s.add_all([agencia, puesto, puesto_atl])
        await s.commit()
    del_puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    puesto_ajeno = await crear_actor("Puesto de Control", prefijo="puesto")
    async with SesionLocal() as s:
        await s.execute(insert(usuarios_puestos).values(usuario_id=del_puesto.id, puesto_id=puesto.id))
        await s.execute(insert(usuarios_puestos).values(usuario_id=puesto_ajeno.id, puesto_id=puesto_atl.id))
        await s.commit()
    return Escenario(
        sufijo=sufijo, agencia_id=agencia.id, agencia=agencia.nombre, puesto_id=puesto.id, puesto=puesto.nombre,
        naviera=await crear_actor("Naviera", agencia_id=agencia.id, prefijo="naviera"),
        revisor=await crear_actor("UCVMM", prefijo="revisor"),
        revisor_atl=await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,)),
        sup_sector=await crear_actor("Supervisor de sector", prefijo="supervisor"),
        general=await crear_actor("Supervisor general", prefijo="general"),
        del_puesto=del_puesto, puesto_ajeno=puesto_ajeno,
    )


async def _solicitud(e: Escenario, *, recargo: bool = True, codigo: str = "F3-EMBARQUE",
                     operacion: str | None = None, dias_sellado: int | None = None) -> tuple[int, str]:
    """Una solicitud aprobada el último sábado a las 10:00 (fuera del horario), con el
    recargo de B/.20.00 o sin él. Devuelve (id, número)."""
    aprobada = _ultimo_sabado_a_las_10()
    numero = f"BR-{e.sufijo}-{next(_contador)}"
    async with SesionLocal() as s:
        tipo_id = (await s.execute(select(TipoTramite.id).where(TipoTramite.codigo == codigo))).scalar_one()
        solicitud = Solicitud(
            numero=numero, agencia_id=e.agencia_id, agencia_nombre=e.agencia, creada_por_id=e.naviera.id,
            tipo_tramite_id=tipo_id, puesto_control_id=e.puesto_id, puesto_nombre=e.puesto,
            titulo=f"Boleta {e.sufijo}", nombre_buque="MSC PRUEBA", imo="9074729",
            fecha_operacion=datetime.now(ZONA_PANAMA).date() + timedelta(days=5), cantidad_tripulantes=0,
            estado="approved", enviada_en=aprobada - timedelta(days=1), aprobada_en=aprobada,
            costo_fuera_de_horario=Decimal("20.00") if recargo else None, operacion=operacion,
            dias_sellado=dias_sellado,
            vigente_hasta=datetime.now(ZONA_PANAMA) + timedelta(days=10),
            codigo_verificacion=secrets.token_urlsafe(24),
        )
        s.add(solicitud)
        await s.commit()
        return solicitud.id, numero


async def _bitacora(accion: AccionAuditoria, solicitud_id: int) -> list[dict]:
    async with SesionLocal() as s:
        filas = (await s.execute(
            select(RegistroAuditoria).where(RegistroAuditoria.accion == accion).order_by(RegistroAuditoria.id)
        )).scalars()
        return [f.detalle for f in filas if f.detalle and f.detalle.get("solicitud_id") == solicitud_id]


async def _generar(cliente, actor: Actor, sid: int, numero_oficio: str):
    return await cliente.post(f"/solicitudes/{sid}/boletas", json={"numero_oficio": numero_oficio},
                              headers=actor.headers)


async def test_generan_ucvmm_sector_puesto_y_admin(cliente, esc, admin):
    for actor in (esc.revisor, esc.sup_sector, esc.del_puesto, admin):
        sid, _ = await _solicitud(esc)
        antes = (await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)).json()
        assert antes["boletas"] == [] and antes["acciones"]["generar_boleta"] is True, actor.username
        r = await _generar(cliente, actor, sid, f"  of-{esc.sufijo}   {sid} ")
        assert r.status_code == 201, (actor.username, r.text)
        boleta = r.json()["boletas"][0]
        assert boleta["numero_oficio"] == f"of-{esc.sufijo} {sid}", "sin espacios de más"
        assert boleta["monto"] == "B/.20.00" and boleta["vigente"] is True and boleta["anulada_en"] is None
        assert boleta["generada_por"] and boleta["generada_por"].endswith("Prueba")
        assert r.json()["acciones"]["generar_boleta"] is False and r.json()["acciones"]["anular_boleta"] is True
        evento = next(ev for ev in r.json()["eventos"] if ev["tipo"] == "boleta_generada")
        assert f"Oficio N.º of-{esc.sufijo} {sid}" in evento["comentario"]
        [registro] = await _bitacora(AccionAuditoria.BOLETA_GENERADA, sid)
        assert registro["numero_oficio"] == f"of-{esc.sufijo} {sid}" and registro["boleta_id"] == boleta["id"]


async def test_no_generan_agencia_general_ni_ajenos(cliente, esc):
    sid, _ = await _solicitud(esc)
    for actor in (esc.naviera, esc.general, esc.revisor_atl, esc.puesto_ajeno):
        r = await _generar(cliente, actor, sid, f"NO-{esc.sufijo}-{actor.id}")
        assert r.status_code == 403, (actor.username, r.text)
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.revisor.headers)).json()
    assert detalle["boletas"] == []


async def test_sin_recargo_no_hay_boleta(cliente, esc):
    sid, _ = await _solicitud(esc, recargo=False)
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.revisor.headers)).json()
    assert detalle["acciones"]["generar_boleta"] is False
    r = await _generar(cliente, esc.revisor, sid, f"SIN-{esc.sufijo}")
    assert r.status_code == 409 and "no lleva recargo" in r.json()["detail"]


async def test_una_vigente_y_talonario(cliente, esc):
    sid, _ = await _solicitud(esc)
    primero, segundo, tercero = (f"T{n}-{esc.sufijo}" for n in (1, 2, 3))
    boleta_id = (await _generar(cliente, esc.revisor, sid, primero)).json()["boletas"][0]["id"]

    r = await _generar(cliente, esc.revisor, sid, segundo)
    assert r.status_code == 409 and "ya tiene una boleta vigente" in r.json()["detail"]

    ruta = f"/solicitudes/{sid}/boletas/{boleta_id}/anular"
    assert (await cliente.post(ruta, json={"motivo": ""}, headers=esc.revisor.headers)).status_code == 422
    r = await cliente.post(ruta, json={"motivo": "Número de oficio mal escrito"}, headers=esc.revisor.headers)
    assert r.status_code == 200, r.text
    anulada = r.json()["boletas"][0]
    assert anulada["vigente"] is False and anulada["anulada_en"] and anulada["anulada_por"]
    assert anulada["motivo_anulacion"] == "Número de oficio mal escrito"
    assert r.json()["acciones"]["generar_boleta"] is True and r.json()["acciones"]["anular_boleta"] is False
    evento = next(ev for ev in r.json()["eventos"] if ev["tipo"] == "boleta_anulada")
    assert evento["comentario"] == f"Oficio N.º {primero}. Motivo: Número de oficio mal escrito."
    assert len(await _bitacora(AccionAuditoria.BOLETA_ANULADA, sid)) == 1
    r = await cliente.post(ruta, json={"motivo": "Otra vez"}, headers=esc.revisor.headers)
    assert r.status_code == 409 and "ya está anulada" in r.json()["detail"]

    r = await _generar(cliente, esc.revisor, sid, primero)
    assert r.status_code == 409, "el número de una anulada no se vuelve a usar"
    r = await _generar(cliente, esc.revisor, sid, tercero)
    assert r.status_code == 201
    boletas = r.json()["boletas"]
    assert [b["numero_oficio"] for b in boletas] == [primero, tercero]
    assert [b["vigente"] for b in boletas] == [False, True]


async def test_numero_repetido_sin_distinguir_mayusculas(cliente, esc):
    (sid_1, numero_1), (sid_2, _) = await _solicitud(esc), await _solicitud(esc)
    assert (await _generar(cliente, esc.revisor, sid_1, f" rep-{esc.sufijo} ")).status_code == 201
    r = await _generar(cliente, esc.revisor, sid_2, f"REP-{esc.sufijo.upper()}")
    assert r.status_code == 409 and numero_1 in r.json()["detail"]


async def test_numero_de_oficio_invalido(cliente, esc):
    sid, _ = await _solicitud(esc)
    for numero in ("", "   ", "x" * 41, "linea\nnueva"):
        r = await _generar(cliente, esc.revisor, sid, numero)
        assert r.status_code == 422, (numero, r.text)


async def test_dos_generaciones_a_la_vez(cliente, esc, monkeypatch):
    """Una pausa después de bloquear la solicitud asegura que las dos se crucen: la
    segunda espera el bloqueo y ve la vigente de la primera."""
    from app.domain.services.solicitud_service import ServicioSolicitud

    sid, _ = await _solicitud(esc)
    original = ServicioSolicitud._para_boleta

    async def con_pausa(self, ctx, solicitud_id):
        solicitud = await original(self, ctx, solicitud_id)
        await asyncio.sleep(0.3)
        return solicitud

    monkeypatch.setattr(ServicioSolicitud, "_para_boleta", con_pausa)
    a, b = await asyncio.gather(_generar(cliente, esc.revisor, sid, f"PAR-A-{esc.sufijo}"),
                                _generar(cliente, esc.sup_sector, sid, f"PAR-B-{esc.sufijo}"))
    assert sorted([a.status_code, b.status_code]) == [201, 409]
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.revisor.headers)).json()
    assert len(detalle["boletas"]) == 1


async def test_la_agencia_no_ve_boletas(cliente, esc):
    sid, _ = await _solicitud(esc)
    boleta_id = (await _generar(cliente, esc.revisor, sid, f"AG-{esc.sufijo}")).json()["boletas"][0]["id"]
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.naviera.headers)).json()
    assert detalle["boletas"] is None
    assert not [ev for ev in detalle["eventos"] if ev["tipo"].startswith("boleta_")]
    assert detalle["acciones"]["generar_boleta"] is False and detalle["acciones"]["anular_boleta"] is False
    assert detalle["costo_fuera_de_horario"] == "B/.20.00", "el recargo sí lo ve, como antes"
    r = await cliente.get(f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf", headers=esc.naviera.headers)
    assert r.status_code == 403
    r = await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "No me corresponde"},
                           headers=esc.naviera.headers)
    assert r.status_code == 403


async def test_el_supervisor_general_descarga_las_de_tecnico(cliente, esc):
    """La ve y la descarga en las solicitudes del trámite de Técnico (lo que ve desde
    el 2026-11-16), sin generar ni anular."""
    sid, _ = await _solicitud(esc, codigo="F3-TECNICO")
    boleta_id = (await _generar(cliente, esc.revisor, sid, f"GEN-{esc.sufijo}")).json()["boletas"][0]["id"]
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.general.headers)).json()
    assert [b["id"] for b in detalle["boletas"]] == [boleta_id]
    assert detalle["acciones"]["generar_boleta"] is False and detalle["acciones"]["anular_boleta"] is False
    r = await cliente.get(f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf", headers=esc.general.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    r = await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "No me corresponde"},
                           headers=esc.general.headers)
    assert r.status_code == 403
    embarque, _ = await _solicitud(esc)
    assert (await cliente.get(f"/solicitudes/{embarque}", headers=esc.general.headers)).status_code == 403


async def test_pdf_de_la_boleta_por_la_api(cliente, esc, monkeypatch):
    from app.api.v1 import solicitudes as rutas
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    armados = []

    def capturar(datos):
        armados.append(datos)
        return generar_pdf_boleta(datos)

    monkeypatch.setattr(rutas, "generar_pdf_boleta", capturar)
    sid, numero = await _solicitud(esc)
    oficio = f"PDF {esc.sufijo}/1"
    boleta_id = (await _generar(cliente, esc.revisor, sid, oficio)).json()["boletas"][0]["id"]
    ruta = f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf"

    r = await cliente.get(ruta, headers=esc.del_puesto.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert r.headers["content-disposition"] == f'attachment; filename="Boleta-recargo-{numero}-{slug(oficio)}.pdf"'
    datos = armados[-1]
    assert (datos.numero_oficio, datos.monto, datos.numero_solicitud) == (oficio, Decimal("20.00"), numero)
    assert datos.agencia == esc.agencia and datos.puesto == esc.puesto and datos.anulada_en is None
    # El tipo de operación en casillas, como en papel (2026-11-16): los trámites activos, en su
    # orden, con la X en el de la solicitud. Embarque ya no pregunta «Subir y bajar» (2026-11-18).
    async with SesionLocal() as sesion:
        activos = (await sesion.execute(select(TipoTramite.nombre).where(TipoTramite.activo.is_(True))
                                        .order_by(TipoTramite.orden, TipoTramite.nombre))).scalars().all()
    assert datos.tipos_operacion == list(activos) and datos.tipo_tramite == "Embarque"
    assert datos.subir_y_bajar is None and datos.elecciones == []
    [registro] = await _bitacora(AccionAuditoria.BOLETA_DESCARGADA, sid)
    assert registro["numero_oficio"] == oficio and registro["anulada"] is False

    await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "Prueba de anulada"},
                       headers=esc.revisor.headers)
    assert (await cliente.get(ruta, headers=esc.revisor.headers)).status_code == 200
    assert armados[-1].anulada_en is not None and armados[-1].motivo_anulacion == "Prueba de anulada"
    r = await cliente.get(f"/solicitudes/{sid}/boletas/999999/boleta.pdf", headers=esc.revisor.headers)
    assert r.status_code == 404


@pytest.mark.parametrize(("codigo", "elegido", "esperado"), [
    ("F3-TECNICO", {"operacion": "subir_y_bajar"},
     ("OPERACIÓN", ("Embarque", "Desembarque", "Subir y bajar"), "Subir y bajar")),
    ("F3-SHORE-PASS", {"dias_sellado": 15}, ("DÍAS DEL SELLADO", ("5 días", "15 días"), "15 días")),
])
async def test_la_boleta_lleva_la_operacion_y_los_dias(cliente, esc, monkeypatch, codigo, elegido, esperado):
    """La operación del trámite de Técnico y los días del sellado de Shore Pass (2026-11-18)
    van en casillas, con la X en la elegida; esos trámites no preguntan «¿Subir y bajar?»."""
    from app.api.v1 import solicitudes as rutas
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    armados = []

    def capturar(datos):
        armados.append(datos)
        return generar_pdf_boleta(datos)

    monkeypatch.setattr(rutas, "generar_pdf_boleta", capturar)
    sid, _ = await _solicitud(esc, codigo=codigo, **elegido)
    boleta_id = (await _generar(cliente, esc.revisor, sid, f"OP-{codigo}-{esc.sufijo}")).json()["boletas"][0]["id"]
    r = await cliente.get(f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf", headers=esc.revisor.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    datos = armados[-1]
    assert datos.elecciones == [esperado] and datos.subir_y_bajar is None


async def test_la_boleta_dice_los_metodos_de_pago(monkeypatch):
    """Pedido del usuario del 2026-11-18: efectivo, tarjeta o cheque a favor del Servicio
    Nacional de Migración. Los párrafos del PDF, tal como se escriben (su texto va cifrado
    con la fuente)."""
    from app.informes import boleta_recargo_pdf as modulo

    escritos: list[str] = []
    original = modulo.Paragraph

    def capturar(texto, *args, **kwargs):
        escritos.append(str(texto))
        return original(texto, *args, **kwargs)

    monkeypatch.setattr(modulo, "Paragraph", capturar)
    for datos in (_datos_pdf(), replace(_datos_pdf(), anulada_en=panama(2026, 11, 15, 11, 0), motivo_anulacion="Mal")):
        escritos.clear()
        modulo.generar_pdf_boleta(datos)
        texto = " ".join(escritos)
        assert "MÉTODOS DE PAGO" in texto
        assert "Efectivo, tarjeta o cheque a favor del Servicio Nacional de Migración" in texto
