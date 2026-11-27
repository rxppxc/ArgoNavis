"""Boleta de recargo por atención fuera del horario laboral (2026-11-16).

Cuando UCVMM aprueba fuera del horario, la solicitud lleva un recargo. UCVMM, el
supervisor de sector y el puesto de control generan la boleta para cobrarlo, con
un número de oficio que escriben ellos: único entre todas las boletas, también
las anuladas, sin distinguir mayúsculas. Como en un talonario, una boleta mal
hecha se anula (con motivo) y se genera otra; hay una sola vigente por
solicitud. La agencia no la ve: la imprime el SNM y se la entrega.

Desde el 2026-11-26 el PDF sigue el modelo en papel de UCVMM (Formulario No. 4, «Autorización
fuera del horario laboral»), con el encabezado y el pie de los manuales, y lo firma el jefe
encargado del sector de UCVMM de la solicitud.
"""
import asyncio
import itertools
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
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
        numero_oficio="0716 SNM-UCVMM-2026", monto=Decimal("20.00"), numero_solicitud="AM-2026-000123",
        tipo_tramite="Embarque", agencia="Naviera del Istmo, S.A.", buque="MSC ARIES",
        puesto="Balboa", puesto_destino=None, sector=PACIFICO,
        aprobada_en=panama(2026, 11, 14, 16, 20), generada_en=panama(2026, 11, 15, 10, 5),
        anulada_en=None, motivo_anulacion=None,
        tipos_operacion=["Embarque", "Desembarque", "Cambio de Nave", "Urgencias o Atención Médica"],
    )


def _textos_del_pdf(monkeypatch, datos) -> str:
    """Los párrafos del PDF, tal como se escriben (en el archivo, el texto va cifrado con la fuente)."""
    from app.informes import boleta_recargo_pdf as modulo

    escritos: list[str] = []
    original = modulo.Paragraph

    def capturar(texto, *args, **kwargs):
        escritos.append(str(texto))
        return original(texto, *args, **kwargs)

    monkeypatch.setattr(modulo, "Paragraph", capturar)
    modulo.generar_pdf_boleta(datos)
    monkeypatch.undo()
    return " ".join(escritos)


async def test_casillas_operacion():
    """El tipo de operación va en casillas, como en papel (2026-11-16): los trámites del
    sistema, con la X en el de la solicitud. Debajo de la marcada, lo que eligió la agencia y el
    cambio de puerto, una línea cada uno (2026-11-27; antes, entre paréntesis y en una casilla
    «Cambio de Puerto» aparte)."""
    from app.informes.boleta_recargo_pdf import casillas_operacion

    tipos = ["Embarque", "Desembarque", "Cambio de Nave"]
    assert casillas_operacion(tipos, "Desembarque") == [
        ("Embarque", False, []), ("Desembarque", True, []), ("Cambio de Nave", False, []),
    ]
    # Un trámite que ya no está activo (Cambio de Puerto, 2026-11-13) se suma al final, marcado.
    assert casillas_operacion(tipos, "Cambio de Puerto") == [
        ("Embarque", False, []), ("Desembarque", False, []), ("Cambio de Nave", False, []),
        ("Cambio de Puerto", True, []),
    ]
    # La operación de Técnico o los días del sellado, bajo la marcada.
    assert casillas_operacion(["Embarque", "Técnico"], "Técnico", detalles=["Operación: Subir y bajar"]) == [
        ("Embarque", False, []), ("Técnico", True, ["Operación: Subir y bajar"]),
    ]
    # El cambio de puerto, bajo Embarque o Desembarque, de cuál a cuál: sin casilla aparte.
    assert casillas_operacion(tipos, "Embarque", cambio_de_puerto=("Amador", "Cristóbal")) == [
        ("Embarque", True, ["Cambio de puerto: de Amador a Cristóbal"]), ("Desembarque", False, []),
        ("Cambio de Nave", False, []),
    ]
    # Aunque «Cambio de Puerto» estuviera entre los activos, no se marca: va bajo su trámite.
    assert casillas_operacion(["Desembarque", "Cambio de Puerto"], "Desembarque",
                              cambio_de_puerto=("Amador", "Cristóbal")) == [
        ("Desembarque", True, ["Cambio de puerto: de Amador a Cristóbal"]), ("Cambio de Puerto", False, []),
    ]


async def test_pdf_de_la_boleta():
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    vigente = generar_pdf_boleta(_datos_pdf())
    assert vigente[:5] == b"%PDF-" and vigente.rstrip().endswith(b"%%EOF")
    assert b"Boleta de recargo AM-2026-000123" in vigente, "el título del documento"
    # El encabezado y el pie de los manuales (2026-11-26): dos imágenes.
    assert vigente.count(b"/Subtype /Image") >= 2
    anulada = generar_pdf_boleta(replace(_datos_pdf(), anulada_en=panama(2026, 11, 15, 11, 0),
                                         motivo_anulacion="El número de oficio estaba mal escrito."))
    assert anulada[:5] == b"%PDF-" and len(anulada) > len(vigente), "lleva el sello y la anulación"
    # Sin sector (no debería pasar: la revisó un sector), firma el jefe encargado del sector.
    sin_sector = generar_pdf_boleta(replace(_datos_pdf(), sector=None))
    assert sin_sector[:5] == b"%PDF-"


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page[^s]", pdf))


async def test_la_boleta_cabe_en_una_hoja():
    """Como el papel, una sola hoja, también en el caso más cargado: anulada, con cambio de puerto,
    el detalle de la operación, todos los trámites y una agencia de nombre largo."""
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    tramites = ["Embarque", "Desembarque", "Cambio de Nave", "Urgencias o Atención Médica", "Sellado de Shore Pass",
                "Autorización de Técnico, Superintendente o Supernumerario", "Renovación de Pasaporte"]
    cargada = replace(
        _datos_pdf(), agencia="Agencia Naviera Internacional del Istmo de Panamá y del Caribe, S.A. " * 2,
        tipo_tramite=tramites[5], tipos_operacion=tramites, detalles=["Operación: Subir y bajar"],
        puesto_destino="Cristóbal", anulada_en=panama(2026, 11, 15, 11, 0),
        motivo_anulacion="El número de oficio estaba mal escrito y se generó otra boleta con el correcto.",
    )
    assert _paginas(generar_pdf_boleta(_datos_pdf())) == 1
    assert _paginas(generar_pdf_boleta(cargada)) == 1


async def test_la_boleta_cabe_en_una_hoja_con_todo_al_tope():
    """Con cada texto libre en su largo máximo, también una hoja, con cualquier fuente: en la CI
    (DejaVu, más ancha que la Arial de Windows) el caso cargado pasaba a dos (2026-11-27)."""
    from app.domain.models.boleta import LARGO_MOTIVO_ANULACION
    from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
    from app.domain.models.solicitud import Solicitud
    from app.informes.boleta_recargo_pdf import generar_pdf_boleta

    def largo(columna) -> int:
        return columna.property.columns[0].type.length

    def texto(n: int) -> str:
        return ("Agencia Marítima del Istmo " * 40)[:n]

    al_tope = replace(
        _datos_pdf(), agencia=texto(largo(AgenciaNaviera.nombre)), buque=texto(largo(Solicitud.nombre_buque)),
        puesto=texto(largo(PuestoControl.nombre)), puesto_destino=texto(largo(PuestoControl.nombre)),
        tipo_tramite="Autorización de Técnico, Superintendente o Supernumerario",
        # Con el cambio de puerto (de los dos puestos al tope), en su línea bajo la casilla (2026-11-27).
        detalles=["Operación: Subir y bajar"],
        tipos_operacion=["Embarque", "Desembarque", "Cambio de Nave", "Urgencias o Atención Médica",
                         "Sellado de Shore Pass", "Autorización de Técnico, Superintendente o Supernumerario",
                         "Renovación de Pasaporte"],
        numero_oficio="0716-SNM-UCVMM-2026-PACÍFICO-BALBOA-0001"[:40],
        anulada_en=panama(2026, 11, 15, 11, 0), motivo_anulacion=texto(LARGO_MOTIVO_ANULACION),
    )
    assert _paginas(generar_pdf_boleta(al_tope)) == 1


async def test_la_boleta_sigue_el_formulario_4(monkeypatch):
    """El modelo en papel de UCVMM (pedido del usuario del 2026-11-26): el Formulario No. 4,
    con el oficio que escribe el funcionario y el número de la solicitud, los datos del cobro,
    las casillas y la firma del jefe encargado del sector de UCVMM de la solicitud."""
    texto = _textos_del_pdf(monkeypatch, _datos_pdf())
    for esperado in (
        "FORMULARIO No. 4.", "AUTORIZACIÓN FUERA DEL HORARIO LABORAL.",
        "Panamá, ", "15 de noviembre de 2026",
        "Oficio N.º", "0716 SNM-UCVMM-2026", "Autorización Marítima N.º", "AM-2026-000123",
        "Agencia Naviera solicitante del servicio:", "Naviera del Istmo, S.A.",
        "Respetado representante de Agencia Naviera:",
        "Por este medio le hacemos llegar a su despacho nota de cobro por servicio prestado de la siguiente unidad:",
        "A Favor de:", "SERVICIO NACIONAL DE MIGRACIÓN", "Moto Nave:", "MSC ARIES",
        "Fecha de la Atención:", "14/11/2026", "Hora:", "16:20", "Lugar:", "Balboa",
        "Pago por Servicio:", "B/.20.00",
        "(PAGO EN EFECTIVO, TARJETA O CHEQUE A FAVOR DEL SERVICIO NACIONAL DE MIGRACIÓN).",
        "Tipo de autorización y aprobación fuera de horario laboral. Marque con una",
        "EMBARQUE", "CAMBIO DE NAVE",
        "Sin más que agregar, de ustedes,", "Firma del Agente Naviero que Solicita la Atención.",
        "Nombre, apellido y firma del jefe encargado del Sector Pacífico (UCVMM)",
        "Esta autorización será únicamente válida, siempre que tenga nombre, firma y sello del jefe "
        "encargado del Sector Pacífico de UCVMM.",
    ):
        assert esperado in texto, esperado

    # Del Atlántico, firma el jefe de ese sector.
    texto = _textos_del_pdf(monkeypatch, replace(_datos_pdf(), sector=ATLANTICO))
    assert "firma del jefe encargado del Sector Atlántico (UCVMM)" in texto
    assert "sello del jefe encargado del Sector Atlántico de UCVMM." in texto and "Pacífico" not in texto

    # Con cambio de puerto, el lugar dice los dos y, bajo la casilla marcada, de cuál a cuál, en
    # azul (2026-11-27): sin casilla «Cambio de Puerto» aparte.
    texto = _textos_del_pdf(monkeypatch, replace(_datos_pdf(), puesto_destino="Cristóbal"))
    sin_marcas = re.sub(r"<[^>]+>", "", texto)   # el rótulo va en negrita
    assert "Balboa → Cristóbal" in texto and "Cambio de puerto: de Balboa a Cristóbal" in sin_marcas
    assert "CAMBIO DE PUERTO" not in texto
    texto = _textos_del_pdf(monkeypatch, _datos_pdf())
    assert "Cambio de puerto" not in texto, "sin cambio de puerto, nada"

    # Lo que eligió la agencia, con el mismo estilo, bajo la casilla marcada.
    texto = _textos_del_pdf(monkeypatch, replace(
        _datos_pdf(), tipo_tramite="Autorización de Técnico, Superintendente o Supernumerario",
        tipos_operacion=["Embarque", "Autorización de Técnico, Superintendente o Supernumerario"],
        detalles=["Operación: Subir y bajar"],
    ))
    assert "AUTORIZACIÓN DE TÉCNICO, SUPERINTENDENTE O SUPERNUMERARIO" in texto
    assert "Operación: Subir y bajar" in re.sub(r"<[^>]+>", "", texto) and "(operación" not in texto

    # Anulada: lo dice arriba, con el motivo, además del sello.
    texto = _textos_del_pdf(monkeypatch, replace(
        _datos_pdf(), anulada_en=panama(2026, 11, 15, 11, 0), motivo_anulacion="El oficio estaba mal escrito."))
    assert "BOLETA ANULADA EL" in texto and "El oficio estaba mal escrito." in texto


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
    revisor:      Actor   # el que aprueba las solicitudes de `_solicitud`
    revisor_atl:  Actor
    sup_sector:   Actor
    general:      Actor
    del_puesto:   Actor
    puesto_ajeno: Actor
    otro_revisor:   Actor   # UCVMM del mismo sector, que no la aprobó (2026-11-27)
    tercer_revisor: Actor


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
        otro_revisor=await crear_actor("UCVMM", prefijo="revisor"),
        tercer_revisor=await crear_actor("UCVMM", prefijo="revisor"),
    )


async def _solicitud(e: Escenario, *, recargo: bool = True, codigo: str = "F3-EMBARQUE",
                     operacion: str | None = None, dias_sellado: int | None = None,
                     aprobada_por: Actor | None = None) -> tuple[int, str]:
    """Una solicitud aprobada el último sábado a las 10:00 (fuera del horario) por
    `aprobada_por` (`e.revisor` si no se dice), con el recargo de B/.20.00 o sin él.
    Devuelve (id, número)."""
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
            aprobada_por_id=(aprobada_por or e.revisor).id,
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


async def _nombre(actor: Actor) -> str:
    from app.domain.models.user import Usuario

    async with SesionLocal() as s:
        return (await s.get(Usuario, actor.id)).full_name


async def test_genera_quien_la_aprobo(cliente, esc):
    """El número de oficio lo pone el analista de UCVMM que aprobó la solicitud fuera del horario
    (pedido del usuario del 2026-11-27)."""
    sid, _ = await _solicitud(esc)
    antes = (await cliente.get(f"/solicitudes/{sid}", headers=esc.revisor.headers)).json()
    assert antes["boletas"] == [] and antes["acciones"]["generar_boleta"] is True
    r = await _generar(cliente, esc.revisor, sid, f"  of-{esc.sufijo}   {sid} ")
    assert r.status_code == 201, r.text
    boleta = r.json()["boletas"][0]
    assert boleta["numero_oficio"] == f"of-{esc.sufijo} {sid}", "sin espacios de más"
    assert boleta["monto"] == "B/.20.00" and boleta["vigente"] is True and boleta["anulada_en"] is None
    assert boleta["generada_por"] and boleta["generada_por"].endswith("Prueba")
    assert r.json()["acciones"]["generar_boleta"] is False and r.json()["acciones"]["anular_boleta"] is True
    evento = next(ev for ev in r.json()["eventos"] if ev["tipo"] == "boleta_generada")
    assert evento["comentario"] == f"Oficio N.º of-{esc.sufijo} {sid}."
    [registro] = await _bitacora(AccionAuditoria.BOLETA_GENERADA, sid)
    assert registro["numero_oficio"] == f"of-{esc.sufijo} {sid}" and registro["boleta_id"] == boleta["id"]
    assert "en_lugar_de" not in registro


async def test_si_no_esta_quien_la_aprobo_la_genera_otro_de_ucvmm(cliente, esc, admin):
    """Si el analista que la aprobó no está, otro de UCVMM del sector pone el oficio, y queda
    auditado: la bitácora y el historial dicen en lugar de quién."""
    sid, _ = await _solicitud(esc)
    antes = (await cliente.get(f"/solicitudes/{sid}", headers=esc.otro_revisor.headers)).json()
    assert antes["acciones"]["generar_boleta"] is True
    r = await _generar(cliente, esc.otro_revisor, sid, f"OTRO-{esc.sufijo}")
    assert r.status_code == 201, r.text
    quien_aprobo = await _nombre(esc.revisor)
    evento = next(ev for ev in r.json()["eventos"] if ev["tipo"] == "boleta_generada")
    assert evento["comentario"] == f"Oficio N.º OTRO-{esc.sufijo}, en lugar de {quien_aprobo}, que la aprobó."
    [registro] = await _bitacora(AccionAuditoria.BOLETA_GENERADA, sid)
    assert registro["en_lugar_de"] == quien_aprobo


async def test_si_la_aprobo_el_administrador_la_genera_ucvmm(cliente, esc, admin):
    """El Administrador solo ve: aunque la haya aprobado él, el oficio lo pone UCVMM del sector."""
    sid, _ = await _solicitud(esc, aprobada_por=admin)
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=admin.headers)).json()
    assert detalle["acciones"]["generar_boleta"] is False
    assert (await _generar(cliente, admin, sid, f"ADM-{esc.sufijo}")).status_code == 403
    r = await _generar(cliente, esc.revisor, sid, f"ADM-UCVMM-{esc.sufijo}")
    assert r.status_code == 201, r.text
    [registro] = await _bitacora(AccionAuditoria.BOLETA_GENERADA, sid)
    assert registro["en_lugar_de"] == await _nombre(admin)


async def test_el_supervisor_de_sector_y_el_administrador_solo_ven_y_descargan(cliente, esc, admin):
    sid, _ = await _solicitud(esc)
    boleta_id = (await _generar(cliente, esc.revisor, sid, f"VER-{esc.sufijo}")).json()["boletas"][0]["id"]
    for actor in (esc.sup_sector, admin):
        detalle = (await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)).json()
        assert [b["id"] for b in detalle["boletas"]] == [boleta_id], actor.username
        assert detalle["acciones"]["generar_boleta"] is False and detalle["acciones"]["anular_boleta"] is False
        assert any(ev["tipo"] == "boleta_generada" for ev in detalle["eventos"])
        r = await cliente.get(f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf", headers=actor.headers)
        assert r.status_code == 200 and r.content[:5] == b"%PDF-", actor.username
        r = await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "No me toca"},
                               headers=actor.headers)
        assert r.status_code == 403, (actor.username, r.text)
    otra, _ = await _solicitud(esc)
    for actor in (esc.sup_sector, admin):
        assert (await _generar(cliente, actor, otra, f"NO-{esc.sufijo}-{actor.id}")).status_code == 403


async def test_anulan_quien_la_aprobo_y_quien_la_genero(cliente, esc):
    """Anular (con motivo) y poner otro número lo hace quien la aprobó; si la generó otro
    analista, también él. Nadie más toca una boleta que no puso."""
    async def anular(actor: Actor, sid: int, boleta_id: int):
        return await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular",
                                  json={"motivo": "Equivocación en el número"}, headers=actor.headers)

    # La generó otro analista: un tercero no la anula; él sí.
    sid, _ = await _solicitud(esc)
    boleta_id = (await _generar(cliente, esc.otro_revisor, sid, f"AN1-{esc.sufijo}")).json()["boletas"][0]["id"]
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.tercer_revisor.headers)).json()
    assert detalle["acciones"]["anular_boleta"] is False and detalle["acciones"]["generar_boleta"] is False
    assert (await anular(esc.tercer_revisor, sid, boleta_id)).status_code == 403
    assert (await anular(esc.otro_revisor, sid, boleta_id)).status_code == 200

    # La generó otro analista: quien la aprobó también la anula.
    sid, _ = await _solicitud(esc)
    boleta_id = (await _generar(cliente, esc.otro_revisor, sid, f"AN2-{esc.sufijo}")).json()["boletas"][0]["id"]
    assert (await anular(esc.revisor, sid, boleta_id)).status_code == 200

    # La generó quien la aprobó: otro analista no la anula.
    sid, _ = await _solicitud(esc)
    boleta_id = (await _generar(cliente, esc.revisor, sid, f"AN3-{esc.sufijo}")).json()["boletas"][0]["id"]
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=esc.otro_revisor.headers)).json()
    assert detalle["acciones"]["anular_boleta"] is False
    assert (await anular(esc.otro_revisor, sid, boleta_id)).status_code == 403


async def test_el_puesto_y_el_supervisor_general_no_ven_la_boleta(cliente, esc):
    """El puesto de control y el supervisor general no ven la boleta ni su historial, ni la
    descargan (2026-11-27; antes, el puesto la generaba y el general la descargaba)."""
    embarque, _ = await _solicitud(esc)
    tecnico, _ = await _solicitud(esc, codigo="F3-TECNICO")
    for actor, sid in ((esc.del_puesto, embarque), (esc.general, tecnico)):
        boleta_id = (await _generar(cliente, esc.revisor, sid, f"NV-{sid}-{esc.sufijo}")).json()["boletas"][0]["id"]
        detalle = (await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)).json()
        assert detalle["boletas"] is None, actor.username
        assert not [ev for ev in detalle["eventos"] if ev["tipo"].startswith("boleta_")], actor.username
        assert detalle["acciones"]["generar_boleta"] is False and detalle["acciones"]["anular_boleta"] is False
        r = await cliente.get(f"/solicitudes/{sid}/boletas/{boleta_id}/boleta.pdf", headers=actor.headers)
        assert r.status_code == 403, (actor.username, r.text)
        r = await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "No me toca"},
                               headers=actor.headers)
        assert r.status_code == 403, (actor.username, r.text)


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
                                _generar(cliente, esc.otro_revisor, sid, f"PAR-B-{esc.sufijo}"))
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

    # La descarga el supervisor de sector, que solo ve (2026-11-27; antes, el puesto de control).
    r = await cliente.get(ruta, headers=esc.sup_sector.headers)
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
    # Nada bajo la casilla; firma el jefe encargado del sector de la solicitud (2026-11-26).
    assert datos.detalles == [] and datos.sector == PACIFICO
    [registro] = await _bitacora(AccionAuditoria.BOLETA_DESCARGADA, sid)
    assert registro["numero_oficio"] == oficio and registro["anulada"] is False

    await cliente.post(f"/solicitudes/{sid}/boletas/{boleta_id}/anular", json={"motivo": "Prueba de anulada"},
                       headers=esc.revisor.headers)
    assert (await cliente.get(ruta, headers=esc.revisor.headers)).status_code == 200
    assert armados[-1].anulada_en is not None and armados[-1].motivo_anulacion == "Prueba de anulada"
    r = await cliente.get(f"/solicitudes/{sid}/boletas/999999/boleta.pdf", headers=esc.revisor.headers)
    assert r.status_code == 404


@pytest.mark.parametrize(("codigo", "elegido", "esperado"), [
    ("F3-TECNICO", {"operacion": "subir_y_bajar"}, ["Operación: Subir y bajar"]),
    ("F3-SHORE-PASS", {"dias_sellado": 15}, ["Sellado: 15 días"]),
])
async def test_la_boleta_lleva_la_operacion_y_los_dias(cliente, esc, monkeypatch, codigo, elegido, esperado):
    """La operación del trámite de Técnico y los días del sellado de Shore Pass (2026-11-18)
    van entre paréntesis junto a la casilla marcada (2026-11-26; antes, en casillas propias)."""
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
    assert datos.detalles == esperado
