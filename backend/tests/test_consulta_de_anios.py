"""Consultar las autorizaciones muchos años después (2026-11-22).

- «Autorizadas»: todas las que se aprobaron alguna vez (vigentes, finalizadas y vencidas
  sin finalizar). «Aprobadas» es el estado de hoy y dura unos días.
- La búsqueda no distingue tildes, admite las palabras en cualquier orden y usa índices:
  con 10 años de datos, buscar un pasaporte tardaba 12 segundos.
- El sector que revisó una solicitud la conserva, aunque el puesto cambie de sector.
- La consulta histórica es de UCVMM, del supervisor de sector y del Administrador.
- Los archivos se ven en cualquier estado, y el PDF de la que venció, para el SNM."""
import secrets
import zipfile
from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.dialects import postgresql

from app.domain.models.catalogo import AgenciaNaviera, usuarios_puestos
from app.domain.models.solicitud import DocumentoSolicitud, Solicitud, TripulanteSolicitud
from app.domain.models.tramite import TipoTramite
from app.domain.repositories.solicitud_repository import FiltrosBandeja, RepositorioSolicitud
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal, motor_bd
from ayudas import cabecera, enviar, panama, pdf, tripulante as ficha_tripulante, verificar_impedimentos
from conftest import ATLANTICO, PACIFICO, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

RUTA = "/solicitudes/historico"


async def _puesto(cliente, admin, nombre: str, sector: str) -> dict:
    r = await cliente.post("/admin/puestos", json={"nombre": nombre, "sector_id": await id_sector(sector)},
                           headers=admin.headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _solicitud(e: dict, clave: str, estado: str, *, aprobada: bool, puesto: dict | None = None,
                     cuando: datetime = panama(2026, 3, 10, 9), tripulante=("Juan", "Pérez", "PA1234567", None),
                     sector: str | None = PACIFICO, archivo: bytes | None = None, buque: str | None = None) -> int:
    """Una solicitud de hace años, ya en su estado, con un tripulante y (si se da) un documento."""
    puesto = puesto or e["puesto"]
    async with SesionLocal() as s:
        solicitud = Solicitud(
            numero=f"AN-{e['sufijo']}-{clave}", agencia_id=e["agencia_id"], agencia_nombre=e["agencia"],
            creada_por_id=e["naviera"].id, tipo_tramite_id=e["tipo"], puesto_control_id=puesto["id"],
            puesto_nombre=puesto["nombre"], titulo=f"Años {e['sufijo']}", nombre_buque=buque or f"BUQUE {clave}",
            fecha_operacion=cuando.date() + timedelta(days=2), cantidad_tripulantes=1, estado=estado, enviada_en=cuando,
            aprobada_en=cuando + timedelta(hours=3) if aprobada else None,
            # Una aprobada, vigente: si no, la expira la prueba de los vencimientos (test_flujo.py).
            vigente_hasta=((datetime.now(timezone.utc) if estado == "approved" else cuando) + timedelta(days=4)
                           if aprobada else None),
            codigo_verificacion=secrets.token_urlsafe(12) if aprobada else None,
            finalizada_en=cuando + timedelta(days=1) if estado == "finalized" else None,
            expirada_en=cuando + timedelta(days=4) if estado == "expired" else None,
            sector_revision_id=await id_sector(sector) if sector and estado != "review" else None,
        )
        s.add(solicitud)
        await s.flush()
        nombre, apellido, pasaporte, libreta = tripulante
        s.add(TripulanteSolicitud(
            solicitud_id=solicitud.id, orden=0, nombre=nombre, apellido=apellido, fecha_nacimiento=date(1985, 1, 1),
            pais_nacimiento="PAN", nacionalidad="PAN", sexo="M", pasaporte=pasaporte, pasaporte_expira=date(2035, 1, 1),
            libreta_marino=libreta, rango="marino",
        ))
        if archivo is not None:
            carpeta = almacenamiento.carpeta_solicitud(solicitud.id)
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / "doc.pdf").write_bytes(archivo)
            s.add(DocumentoSolicitud(
                solicitud_id=solicitud.id, nombre_original="Pasaporte de Juan.pdf", nombre_almacenado="doc.pdf",
                ruta=f"solicitud-{solicitud.id}/doc.pdf", tipo_mime="application/pdf", tamano=len(archivo),
            ))
        await s.commit()
        return solicitud.id


@pytest.fixture
async def e(cliente, admin):
    sufijo = secrets.token_hex(3)
    puesto = await _puesto(cliente, admin, f"Puesto Años {sufijo}", PACIFICO)
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia Años {sufijo}")
        s.add(agencia)
        await s.commit()
        tipo = (await s.execute(select(TipoTramite.id).where(TipoTramite.codigo == "F3-EMBARQUE"))).scalar_one()
    naviera = await crear_actor("Naviera", agencia_id=agencia.id, prefijo="naviera")
    return {"sufijo": sufijo, "puesto": puesto, "agencia_id": agencia.id, "agencia": agencia.nombre, "tipo": tipo,
            "naviera": naviera}


async def _buscar(cliente, actor, e: dict | None = None, **filtros) -> dict:
    if e is not None:
        filtros["texto"] = " ".join(filter(None, (e["sufijo"], filtros.get("texto"))))
    r = await cliente.post(RUTA, json={"por_pagina": 100, **filtros}, headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _ids(cliente, actor, e: dict | None = None, **filtros) -> set[int]:
    return {x["id"] for x in (await _buscar(cliente, actor, e, **filtros))["items"]}


# ── Autorizadas ───────────────────────────────────────────────────────────────

async def test_autorizadas_son_todas_las_que_se_aprobaron(cliente, admin, e):
    ids = {
        "finalizada": await _solicitud(e, "FIN", "finalized", aprobada=True),
        "vigente":    await _solicitud(e, "VIG", "approved", aprobada=True, cuando=datetime.now(timezone.utc)),
        "vencida":    await _solicitud(e, "VEN", "expired", aprobada=True),
        "sincorregir": await _solicitud(e, "SIN", "expired", aprobada=False),
        "denegada":   await _solicitud(e, "DEN", "denied", aprobada=False),
        "revision":   await _solicitud(e, "REV", "review", aprobada=False),
    }
    autorizadas = {ids["finalizada"], ids["vigente"], ids["vencida"]}
    assert await _ids(cliente, admin, e, autorizadas=True) == autorizadas
    # Con las fechas de hace años y el tripulante, como cualquier filtro.
    assert await _ids(cliente, admin, e, autorizadas=True, desde="2026-01-01", hasta="2026-06-30") == {
        ids["finalizada"], ids["vencida"]}
    # La pestaña lleva su cantidad, y las de los estados no cambian al elegirla.
    for filtros, total in (({}, 6), ({"autorizadas": True}, 3), ({"estado": "expired"}, 2),
                           ({"estado": "expired", "autorizadas": True}, 1)):
        pagina = await _buscar(cliente, admin, e, **filtros)
        assert (pagina["total"], len(pagina["items"])) == (total, total), filtros
        assert pagina["autorizadas"] == 3
        assert pagina["conteos"] == {"finalized": 1, "approved": 1, "expired": 2, "denied": 1, "review": 1}
    # Cada expirada dice si se llegó a aprobar.
    por_id = {x["id"]: x for x in (await _buscar(cliente, admin, e, estado="expired"))["items"]}
    assert por_id[ids["vencida"]]["aprobada_en"] and por_id[ids["sincorregir"]]["aprobada_en"] is None


def _textos(contenido: bytes) -> str:
    with zipfile.ZipFile(BytesIO(contenido)) as z:
        return z.read("xl/sharedStrings.xml").decode()


async def test_el_excel_de_las_autorizadas(cliente, admin, e):
    await _solicitud(e, "VEN", "expired", aprobada=True)
    await _solicitud(e, "SIN", "expired", aprobada=False)
    r = await cliente.post(f"{RUTA}/exportar", json={"texto": e["sufijo"]}, headers=admin.headers)
    textos = _textos(r.content)
    assert "Expirada (aprobada, sin finalizar)" in textos and "Expirada (sin corregir)" in textos
    r = await cliente.post(f"{RUTA}/exportar", json={"texto": e["sufijo"], "autorizadas": True}, headers=admin.headers)
    textos = _textos(r.content)
    assert "Solo autorizadas" in textos and f"AN-{e['sufijo']}-VEN" in textos and f"AN-{e['sufijo']}-SIN" not in textos


# ── La búsqueda ───────────────────────────────────────────────────────────────

async def test_sin_tildes_y_en_cualquier_orden(cliente, admin, e):
    nunez = await _solicitud(e, "NUN", "finalized", aprobada=True, tripulante=("José Ángel", "Núñez", "NZ 900-12", "SB-7788"))
    otro = await _solicitud(e, "OTR", "finalized", aprobada=True, tripulante=("Jose", "Mora", "LM400", None))
    for buscado in ("nunez", "NÚÑEZ", "jose angel nunez", "núñez josé", "NÚÑEZ, José Ángel",
                    "nz 900", "900-12", "sb-7788", "7788 nuñez"):
        assert await _ids(cliente, admin, e, pasajero=buscado) == {nunez}, buscado
    assert await _ids(cliente, admin, e, pasajero="jose") == {nunez, otro}
    assert await _ids(cliente, admin, e, pasajero="nunez mora") == set(), "las palabras tienen que ser del mismo tripulante"


async def test_lo_que_se_escribe_se_busca_tal_cual(cliente, admin, e):
    """«%», «_», «/» y «\\» son letras, no comodines ni escapes."""
    raro = await _solicitud(e, "RAR", "finalized", aprobada=True, tripulante=("Søren", "O'Neil", "A_9/B%1\\C", None))
    await _solicitud(e, "OTR", "finalized", aprobada=True, tripulante=("Sam", "Neil", "AX9-BZ1C", None))
    for buscado in ("a_9/b%1", "%1\\c", "/b%", "o'neil", "SØREN"):
        assert await _ids(cliente, admin, e, pasajero=buscado) == {raro}, buscado
    for buscado in ("a%1", "a_9-b", "a_9//b", "' or 1=1"):
        assert await _ids(cliente, admin, e, pasajero=buscado) == set(), buscado


async def test_el_texto_busca_en_varios_datos_a_la_vez(cliente, admin, e):
    aurora = await _solicitud(e, "AUR", "finalized", aprobada=True, buque="Nuestra Señora de la Aurora")
    await _solicitud(e, "OTR", "finalized", aprobada=True)
    for buscado in ("senora aurora", "AURORA anos", f"an-{e['sufijo']}-aur".upper(), "aurora agencia"):
        assert await _ids(cliente, admin, e, texto=buscado) == {aurora}, buscado


async def test_dice_que_tripulante_coincidio(cliente, admin, e):
    sid = await _solicitud(e, "ENC", "finalized", aprobada=True, tripulante=("José", "Núñez", "NZ900", None))
    async with SesionLocal() as s:
        s.add(TripulanteSolicitud(
            solicitud_id=sid, orden=1, nombre="Otro", apellido="Cualquiera", fecha_nacimiento=date(1985, 1, 1),
            pais_nacimiento="PAN", nacionalidad="PAN", sexo="M", pasaporte="ZZ1", pasaporte_expira=date(2035, 1, 1), rango="marino",
        ))
        await s.commit()
    [fila] = (await _buscar(cliente, admin, e, pasajero="nunez"))["items"]
    assert fila["tripulantes_encontrados"] == [{"nombre": "José Núñez", "pasaporte": "NZ900"}]
    [fila] = (await _buscar(cliente, admin, e))["items"]
    assert fila["tripulantes_encontrados"] is None, "sin buscar un tripulante, no hace falta"


@pytest.mark.parametrize(("filtros", "indice"), [
    (FiltrosBandeja(pasajero="Pérez Juan"), "ix_solicitud_tripulantes_busqueda"),
    (FiltrosBandeja(texto="AM-2026-000123"), "ix_solicitudes_busqueda"),
])
async def test_la_busqueda_usa_su_indice(cliente, filtros, indice):
    """Si la condición deja de coincidir con la columna del índice, PostgreSQL recorre la
    tabla entera: con 10 años de datos, 12 segundos por búsqueda."""
    consulta = select(Solicitud.id).where(*RepositorioSolicitud._condiciones(filtros, con_pestana=True))
    sql = str(consulta.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    async with motor_bd.connect() as cx:
        await cx.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(f[0] for f in await cx.execute(text("EXPLAIN " + sql.replace(":", "\\:"))))
    assert indice in plan, plan


# ── Quién la ve ───────────────────────────────────────────────────────────────

async def test_la_consulta_es_de_ucvmm_el_supervisor_de_sector_y_el_administrador(cliente, admin, e):
    sid = await _solicitud(e, "FIN", "finalized", aprobada=True)
    for rol in ("UCVMM", "Supervisor de sector"):
        assert sid in await _ids(cliente, await crear_actor(rol, prefijo="snm"), e), rol
    assert sid in await _ids(cliente, admin, e)

    puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    async with SesionLocal() as s:
        await s.execute(insert(usuarios_puestos).values(usuario_id=puesto.id, puesto_id=e["puesto"]["id"]))
        await s.commit()
    for metodo, ruta in (("POST", RUTA), ("GET", f"{RUTA}/opciones"), ("POST", f"{RUTA}/exportar")):
        r = await cliente.request(metodo, ruta, json={} if metodo == "POST" else None, headers=puesto.headers)
        assert r.status_code == 403 and "puesto" not in r.json()["detail"], ruta
    # El puesto la sigue viendo en su bandeja, y la abre.
    r = await cliente.get("/solicitudes/puerto", params={"texto": e["sufijo"]}, headers=puesto.headers)
    assert [x["id"] for x in r.json()["items"]] == [sid]
    assert (await cliente.get(f"/solicitudes/{sid}", headers=puesto.headers)).status_code == 200


# ── El sector que la revisó ───────────────────────────────────────────────────

async def _mover(cliente, admin, puesto: dict, sector: str) -> None:
    r = await cliente.patch(f"/admin/puestos/{puesto['id']}", json={"sector_id": await id_sector(sector)},
                            headers=admin.headers)
    assert r.status_code == 200, r.text


async def test_el_sector_que_la_reviso_la_conserva(cliente, admin, e):
    vieja = await _solicitud(e, "VIEJA", "finalized", aprobada=True, archivo=b"%PDF-1.4 viejo")
    en_revision = await _solicitud(e, "REV", "review", aprobada=False, cuando=datetime.now(timezone.utc))
    pac = await crear_actor("UCVMM", prefijo="pac")
    sup_pac = await crear_actor("Supervisor de sector", prefijo="suppac")
    atl = await crear_actor("UCVMM", prefijo="atl", sectores=(ATLANTICO,))
    await _mover(cliente, admin, e["puesto"], ATLANTICO)

    # La ya revisada se queda en el Pacífico, con sus archivos; la que está en revisión pasa al Atlántico.
    for actor in (pac, sup_pac):
        assert await _ids(cliente, actor, e) == {vieja}
        detalle = (await cliente.get(f"/solicitudes/{vieja}", headers=actor.headers)).json()
        assert detalle["sector_nombre"] == PACIFICO and detalle["sector_actual_nombre"] == ATLANTICO
        r = await cliente.get(f"/solicitudes/{vieja}/documentos/{detalle['documentos'][0]['id']}", headers=actor.headers)
        assert r.status_code == 200 and r.content == b"%PDF-1.4 viejo"
        assert (await cliente.get(f"/solicitudes/{en_revision}", headers=actor.headers)).status_code == 403
    assert await _ids(cliente, atl, e) == {en_revision}
    assert (await cliente.get(f"/solicitudes/{vieja}", headers=atl.headers)).status_code == 403
    detalle = (await cliente.get(f"/solicitudes/{en_revision}", headers=atl.headers)).json()
    assert detalle["sector_nombre"] == ATLANTICO and detalle["sector_actual_nombre"] is None
    assert detalle["acciones"]["revisar"] is True

    # Lo mismo en las bandejas.
    for actor, bandeja, esperado in ((pac, "revision", {vieja}), (sup_pac, "supervision", {vieja}), (atl, "revision", {en_revision})):
        r = await cliente.get(f"/solicitudes/{bandeja}", params={"texto": e["sufijo"], "por_pagina": 100}, headers=actor.headers)
        assert {x["id"] for x in r.json()["items"]} == esperado, (actor.username, bandeja)
    # El filtro por puesto la sigue ofreciendo, y dice de qué sector es hoy.
    opciones = (await cliente.get(f"{RUTA}/opciones", headers=pac.headers)).json()["puestos"]
    [puesto] = [p for p in opciones if p["id"] == e["puesto"]["id"]]
    assert puesto["nombre"] == f"{e['puesto']['nombre']} (hoy, {ATLANTICO})"
    assert await _ids(cliente, pac, e, puesto_id=e["puesto"]["id"]) == {vieja}
    # La agencia no trabaja con sectores.
    detalle = (await cliente.get(f"/solicitudes/{vieja}", headers=e["naviera"].headers)).json()
    assert detalle["sector_nombre"] is None and detalle["sector_actual_nombre"] is None
    # Y en el Excel, el sector que la revisó.
    r = await cliente.post(f"{RUTA}/exportar", json={"texto": e["sufijo"]}, headers=pac.headers)
    assert PACIFICO in _textos(r.content) and ATLANTICO not in _textos(r.content)


async def test_las_estadisticas_van_con_el_sector_que_la_reviso(cliente, admin, e):
    async def recibidas(sector: str) -> int:
        r = await cliente.get("/solicitudes/estadisticas", params={"sector_id": await id_sector(sector)}, headers=admin.headers)
        return r.json()["recibidas"]

    await _solicitud(e, "FIN", "finalized", aprobada=True, cuando=datetime.now(timezone.utc))
    antes = {s: await recibidas(s) for s in (PACIFICO, ATLANTICO)}
    await _mover(cliente, admin, e["puesto"], ATLANTICO)
    assert {s: await recibidas(s) for s in (PACIFICO, ATLANTICO)} == antes, "mover el puesto no cambia lo ya revisado"


async def test_cada_decision_guarda_el_sector(cliente, admin, e):
    """Aprobar, devolver y negar la dejan en el sector que decidió."""
    revisor = await crear_actor("UCVMM", prefijo="pac")
    sectores = {}
    for accion, cuerpo in (("aprobar", {}), ("devolver", {"motivo": "Falta un documento"}), ("negar", {"motivo": "No procede"})):
        sid = await _solicitud(e, accion[:3].upper(), "review", aprobada=False, cuando=datetime.now(timezone.utc))
        async with SesionLocal() as s:
            solicitud = await s.get(Solicitud, sid)
            solicitud.impedimentos_verificados = True
            for t in (await s.execute(select(TripulanteSolicitud).where(TripulanteSolicitud.solicitud_id == sid))).scalars():
                t.con_impedimento = False
            await s.commit()
        r = await cliente.post(f"/solicitudes/{sid}/{accion}", json=cuerpo, headers=revisor.headers)
        assert r.status_code == 200, r.text
        async with SesionLocal() as s:
            sectores[accion] = (await s.get(Solicitud, sid)).sector_revision_id
    assert set(sectores.values()) == {await id_sector(PACIFICO)}, sectores


async def test_al_corregirla_la_revisa_el_sector_que_tenga_el_puesto(cliente, admin, e):
    pac = await crear_actor("UCVMM", prefijo="pac")
    atl = await crear_actor("UCVMM", prefijo="atl", sectores=(ATLANTICO,))
    datos = cabecera("F3-EMBARQUE", e["puesto"]["id"], tripulantes=[ficha_tripulante("Luis")], asignaciones=[
        {"documento_codigo": c, "indice_tripulante": 0}
        for c in ("DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO")])
    r = await enviar(cliente, e["naviera"], datos, [pdf("visa"), pdf("pasaporte"), pdf("libreta")])
    assert r.status_code == 201, r.text
    enviada = r.json()
    ruta = f"/solicitudes/{enviada['id']}"

    async def ven() -> tuple[int, int]:
        return tuple([(await cliente.get(ruta, headers=a.headers)).status_code for a in (pac, atl)])

    r = await cliente.post(f"{ruta}/devolver", json={"motivo": "Falta una firma"}, headers=pac.headers)
    assert r.status_code == 200, r.text
    await _mover(cliente, admin, e["puesto"], ATLANTICO)
    assert await ven() == (200, 403), "devuelta: es del sector que la devolvió"

    [t] = enviada["tripulantes"]
    datos = cabecera(None, e["puesto"]["id"], asignaciones=[],
                     documentos_conservados=[d["id"] for d in enviada["documentos"]],
                     tripulantes=[ficha_tripulante("Luis", pasaporte=t["pasaporte"], id=t["id"])])
    r = await enviar(cliente, e["naviera"], datos, [], metodo="PUT", ruta=ruta)
    assert r.status_code == 200, r.text
    assert await ven() == (403, 200), "corregida: la revisa el sector de hoy del puesto"
    await verificar_impedimentos(cliente, atl, enviada["id"])
    assert (await cliente.post(f"{ruta}/aprobar", json={}, headers=atl.headers)).status_code == 200
    await _mover(cliente, admin, e["puesto"], PACIFICO)
    assert await ven() == (403, 200), "y aprobada, la conserva"


# ── Los archivos ──────────────────────────────────────────────────────────────

ESTADOS_FINALES = [("finalized", True), ("expired", True), ("expired", False), ("denied", False), ("returned", False), ("approved", True)]


@pytest.mark.parametrize(("estado", "aprobada"), ESTADOS_FINALES)
async def test_los_archivos_se_ven_en_cualquier_estado(cliente, admin, e, estado, aprobada):
    contenido = b"%PDF-1.4 pasaporte de hace anos"
    sid = await _solicitud(e, "DOC", estado, aprobada=aprobada, archivo=contenido, cuando=panama(2026, 1, 5, 9))
    otro_sector = await crear_actor("UCVMM", prefijo="atl", sectores=(ATLANTICO,))
    for actor in (await crear_actor("UCVMM", prefijo="pac"), await crear_actor("Supervisor de sector", prefijo="sup"),
                  admin, e["naviera"]):
        detalle = (await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)).json()
        [documento] = detalle["documentos"]
        ruta = f"/solicitudes/{sid}/documentos/{documento['id']}"
        for descargar in (False, True):
            r = await cliente.get(ruta, params={"descargar": descargar}, headers=actor.headers)
            assert r.status_code == 200 and r.content == contenido, (actor.username, estado)
            assert r.headers["content-type"] == "application/pdf"
            assert r.headers["content-disposition"].startswith("attachment" if descargar else "inline")
    assert (await cliente.get(ruta, headers=otro_sector.headers)).status_code == 403


async def test_un_archivo_que_falta_en_el_disco_se_dice(cliente, admin, e):
    sid = await _solicitud(e, "FALTA", "finalized", aprobada=True, archivo=b"%PDF-1.4 x")
    (almacenamiento.carpeta_solicitud(sid) / "doc.pdf").unlink()
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=admin.headers)).json()
    r = await cliente.get(f"/solicitudes/{sid}/documentos/{detalle['documentos'][0]['id']}", headers=admin.headers)
    assert r.status_code == 404 and "no está disponible" in r.json()["detail"]


async def test_el_pdf_de_la_que_vencio_es_para_el_snm(cliente, admin, e):
    """Se aprobó y nadie la finalizó: el SNM la puede ver, con su sello. La agencia, no."""
    from app.domain.repositories.user_repository import RepositorioUsuario
    from app.domain.services.solicitud_service import ServicioSolicitud

    vencida = await _solicitud(e, "VEN", "expired", aprobada=True)
    nunca = await _solicitud(e, "SIN", "expired", aprobada=False)
    revisor = await crear_actor("UCVMM", prefijo="pac")
    for actor in (revisor, await crear_actor("Supervisor de sector", prefijo="sup"), admin):
        detalle = (await cliente.get(f"/solicitudes/{vencida}", headers=actor.headers)).json()
        assert detalle["acciones"]["descargar_autorizacion"] is True
        r = await cliente.get(f"/solicitudes/{vencida}/autorizacion.pdf", headers=actor.headers)
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        detalle = (await cliente.get(f"/solicitudes/{nunca}", headers=actor.headers)).json()
        assert detalle["acciones"]["descargar_autorizacion"] is False, "nunca se aprobó: no hay autorización"
        assert (await cliente.get(f"/solicitudes/{nunca}/autorizacion.pdf", headers=actor.headers)).status_code == 409
    r = await cliente.get(f"/solicitudes/{vencida}/autorizacion.pdf", headers=e["naviera"].headers)
    assert r.status_code == 409
    detalle = (await cliente.get(f"/solicitudes/{vencida}", headers=e["naviera"].headers)).json()
    assert detalle["acciones"]["descargar_autorizacion"] is False

    async with SesionLocal() as s:
        svc = ServicioSolicitud(s)
        ctx = await svc.contexto(await RepositorioUsuario(s).buscar_por_id(revisor.id))
        datos = await svc.preparar_pdf(ctx, await svc.obtener(ctx, vencida))
    assert datos.estado == "expired" and datos.expirada_en is not None and datos.copia_interna
    # El QR de una vencida no da el PDF: lleva a la verificación.
    r = await cliente.get(f"/verificacion/{datos.codigo_verificacion}/autorizacion.pdf")
    assert r.status_code == 303


async def test_el_pdf_dice_que_vencio(monkeypatch):
    from app.informes import autorizacion_pdf
    from app.informes.autorizacion_pdf import DatosPdfAutorizacion, generar_pdf_autorizacion

    parrafos = []
    original = autorizacion_pdf.Paragraph
    monkeypatch.setattr(autorizacion_pdf, "Paragraph", lambda texto, *a, **k: (parrafos.append(texto), original(texto, *a, **k))[1])
    generar_pdf_autorizacion(DatosPdfAutorizacion(
        numero="AM-2026-000001", estado="expired", tipo_tramite="Embarque", nota_tramite=None, aviso_custodia=False,
        agencia_naviera="Agencia", nombre_buque="Aurora", imo=None, bandera=None, puesto_control="Balboa",
        fecha_operacion=date(2026, 3, 12), nombre_puerto=None, puerto_desembarque=None, clinica_hospital=None, motivo=None,
        fecha_solicitud=panama(2026, 3, 10, 9), aprobada_en=panama(2026, 3, 10, 12), aprobada_por="SNM",
        copia_interna=True, vigente_hasta=panama(2026, 3, 14, 23), finalizada_en=None, puesto_finalizacion=None,
        expirada_en=panama(2026, 3, 15, 0), url_verificacion="http://x/verificar/abc", codigo_verificacion="abc",
        tripulantes=[],
    ))
    todo = " ".join(parrafos)
    assert "EXPIRADA — NO SE FINALIZÓ ANTES DEL" in todo and "no autoriza la operación" in todo
    assert "VIGENTE" not in todo and "Esta autorización vale" not in todo
