"""El historial completo de una solicitud (2026-11-22), para que sirva de prueba años después:

- al corregir una devuelta se conserva lo que se había enviado (una foto) y los documentos
  reemplazados, que antes se borraban para siempre;
- cada archivo lleva su huella (SHA-256), que se comprueba al abrirlo;
- el PDF de la autorización se guarda tal como se emitió, al aprobar y al finalizar, y es el
  que reciben la agencia y quien escanea el QR."""
import asyncio
import hashlib
import logging
import secrets
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, insert, select, update

from app.api.v1 import solicitudes as api_solicitudes
from app.domain.models.catalogo import usuarios_puestos
from app.domain.models.solicitud import DocumentoEmitido, DocumentoSolicitud, Solicitud, VersionSolicitud
from app.domain.models.tramite import TipoTramite
from app.domain.services.version_expediente import comparar
from app.infrastructure import almacenamiento, emision, huellas
from app.infrastructure.database import SesionLocal
from ayudas import cabecera, enviar, pdf, tripulante, verificar_impedimentos
from conftest import ATLANTICO, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

DOCS = ("DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO")


@pytest.fixture(scope="module")
async def e(cliente, admin):
    sufijo = secrets.token_hex(3)
    puesto = (await cliente.post("/admin/puestos", json={"nombre": f"Puesto Historial {sufijo}", "sector_id": await id_sector()},
                                 headers=admin.headers)).json()
    agencia = (await cliente.post("/admin/agencias", json={"nombre": f"Agencia Historial {sufijo}"}, headers=admin.headers)).json()
    del_puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    async with SesionLocal() as s:
        await s.execute(insert(usuarios_puestos).values(usuario_id=del_puesto.id, puesto_id=puesto["id"]))
        await s.commit()
    return {
        "puesto": puesto, "agencia": agencia, "del_puesto": del_puesto,
        "naviera": await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera"),
        "revisor": await crear_actor("UCVMM", prefijo="revisor"),
        "supervisor": await crear_actor("Supervisor de sector", prefijo="supervisor"),
        "otro_sector": await crear_actor("UCVMM", prefijo="atl", sectores=(ATLANTICO,)),
        "general": await crear_actor("Supervisor general", prefijo="general"),
    }


async def _enviada(cliente, e, *nombres: str) -> dict:
    """Un Embarque con esos marinos, cada uno con su visa, su pasaporte y su libreta."""
    asignaciones = [{"documento_codigo": c, "indice_tripulante": i} for i in range(len(nombres)) for c in DOCS]
    archivos = [pdf(f"{c.lower()}-{n}") for n in nombres for c in DOCS]
    datos = cabecera("F3-EMBARQUE", e["puesto"]["id"], tripulantes=[tripulante(n) for n in nombres], asignaciones=asignaciones)
    r = await enviar(cliente, e["naviera"], datos, archivos)
    assert r.status_code == 201, r.text
    return r.json()


async def _devolver(cliente, e, sid: int, motivo: str) -> None:
    r = await cliente.post(f"/solicitudes/{sid}/devolver", json={"motivo": motivo}, headers=e["revisor"].headers)
    assert r.status_code == 200, r.text


async def _corregir(cliente, e, s: dict, quedan: list[str], *, libreta_nueva: str | None = None, **cambios) -> dict:
    """La agencia reenvía con los tripulantes `quedan` y, si se pide, otra libreta para el primero de ellos."""
    fichas, conservados, asignaciones, archivos = [], [], [], []
    for t in (t for t in s["tripulantes"] if t["nombre"] in quedan):
        ficha = tripulante(t["nombre"], t["nacionalidad"], pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
        fichas.append({**ficha, "id": t["id"]})
    for d in s["documentos"]:
        dueno = next((t for t in s["tripulantes"] if t["id"] == d["tripulante_id"]), None)
        reemplazada = libreta_nueva and d["documento_codigo"] == "DOC-LIBRETA-MARINO" and dueno["nombre"] == quedan[0]
        if (dueno is None or dueno["nombre"] in quedan) and not reemplazada:
            conservados.append(d["id"])
    if libreta_nueva:
        asignaciones, archivos = [{"documento_codigo": "DOC-LIBRETA-MARINO", "indice_tripulante": 0}], [pdf(libreta_nueva)]
    datos = cabecera(None, e["puesto"]["id"], tripulantes=fichas, documentos_conservados=conservados,
                     asignaciones=asignaciones, **cambios)
    r = await enviar(cliente, e["naviera"], datos, archivos, metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    return r.json()


async def _registro(cliente, actor, sid: int) -> dict:
    r = await cliente.get(f"/solicitudes/{sid}/registro", headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _aprobada(cliente, e, nombre: str = "Luis") -> dict:
    s = await _enviada(cliente, e, nombre)
    await verificar_impedimentos(cliente, e["revisor"], s["id"])
    r = await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={}, headers=e["revisor"].headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _finalizar(cliente, e, sid: int) -> None:
    await verificar_impedimentos(cliente, e["del_puesto"], sid, ruta="impedimentos-puesto")
    r = await cliente.post(f"/solicitudes/{sid}/finalizar", json={"comentario": "Sin novedad"}, headers=e["del_puesto"].headers)
    assert r.status_code == 200, r.text


# ── Lo que se envió antes de corregir ─────────────────────────────────────────

async def test_al_corregir_se_conserva_lo_enviado(cliente, e):
    s = await _enviada(cliente, e, "Luis", "Raúl")
    sid, carpeta = s["id"], almacenamiento.carpeta_solicitud(s["id"])
    en_disco = {a.name: a.read_bytes() for a in carpeta.iterdir()}
    assert len(en_disco) == 7   # tres por marino y el Formulario No. 3
    await verificar_impedimentos(cliente, e["revisor"], sid, con_impedimento={"Luis"})
    await _devolver(cliente, e, sid, "La libreta de Raúl está ilegible")
    corregida = await _corregir(cliente, e, s, ["Raúl"], libreta_nueva="libreta-nueva", nombre_buque="AURORA II")

    # El expediente es el corregido; lo anterior no se mezcla con él.
    assert len(corregida["documentos"]) == 4 and [t["nombre"] for t in corregida["tripulantes"]] == ["Raúl"]
    assert len(list(carpeta.iterdir())) == 8, "ningún archivo se borra: los siete de antes y la libreta nueva"
    assert all((carpeta / n).read_bytes() == c for n, c in en_disco.items())

    registro = await _registro(cliente, e["revisor"], sid)
    [version] = registro["versiones"]
    assert version["numero"] == 1 and version["motivo"] == "La libreta de Raúl está ilegible"
    assert (version["enviada_por"], version["devuelta_por"], version["corregida_por"]) == (
        "Naviera Prueba", "Revisor Prueba", "Naviera Prueba")
    assert version["enviada_en"] < version["devuelta_en"] < version["corregida_en"]
    datos = dict(version["datos"])
    assert datos["Buque"] == "MSC AURORA" and datos["Trámite"] == "Embarque" and datos["Bandera"] == "Panamá"
    luis, raul = version["tripulantes"]
    assert luis["nombre"] == "Luis Pérez" and dict(luis["datos"])["Pasaporte"] == s["tripulantes"][0]["pasaporte"]
    assert dict(luis["datos"])["Verificación de UCVMM"] == "Con impedimento"
    assert dict(raul["datos"])["Verificación de UCVMM"] == "Sin impedimento"
    assert {d["id"] for d in version["documentos"]} == {d["id"] for d in s["documentos"]}
    cambios = version["cambios"]
    assert "Buque: MSC AURORA → AURORA II" in cambios and "Tripulante quitado: Luis Pérez" in cambios
    assert sum(c.startswith("Documento retirado: ") for c in cambios) == 4   # los tres de Luis y la libreta de Raúl
    assert any(c.startswith("Documento agregado: ") and "libreta-nueva.pdf" in c for c in cambios)
    assert not any("Verificación" in c for c in cambios), "la verificación se reinicia: no la cambió la agencia"

    # Los retirados, con su dueño, y se abren.
    retirados = {a["id"]: a for a in registro["archivos"] if a["retirado_en"]}
    assert len(retirados) == 4 and len(registro["archivos"]) == 8
    assert {a["tripulante"] for a in retirados.values()} == {"Luis Pérez", "Raúl Pérez"}
    for a in retirados.values():
        r = await cliente.get(f"/solicitudes/{sid}/documentos/{a['id']}", headers=e["revisor"].headers)
        assert r.status_code == 200 and hashlib.sha256(r.content).hexdigest() == a["sha256"]


async def test_dos_correcciones_son_dos_versiones(cliente, e):
    s = await _enviada(cliente, e, "Luis")
    for n, buque in enumerate(("SEGUNDO", "TERCERO"), start=1):
        await _devolver(cliente, e, s["id"], f"Motivo {n}")
        s = await _corregir(cliente, e, s, ["Luis"], nombre_buque=buque)
    versiones = (await _registro(cliente, e["revisor"], s["id"]))["versiones"]
    assert [(v["numero"], v["motivo"], dict(v["datos"])["Buque"]) for v in versiones] == [
        (1, "Motivo 1", "MSC AURORA"), (2, "Motivo 2", "SEGUNDO")]
    assert [v["cambios"] for v in versiones] == [["Buque: MSC AURORA → SEGUNDO"], ["Buque: SEGUNDO → TERCERO"]]


async def test_las_corregidas_antes_dicen_que_no_hay_version(cliente, e):
    """Hasta el 2026-11-22 no se guardaban: se devolvió una vez y no hay versión."""
    s = await _enviada(cliente, e, "Luis")
    assert (await _registro(cliente, e["revisor"], s["id"]))["sin_version"] == 0
    async with SesionLocal() as sesion:
        await sesion.execute(update(Solicitud).where(Solicitud.id == s["id"]).values(veces_devuelta=1))
        await sesion.commit()
    assert (await _registro(cliente, e["revisor"], s["id"]))["sin_version"] == 1
    # Devuelta y todavía sin corregir no cuenta: la versión se guarda al corregir.
    otra = await _enviada(cliente, e, "Luis")
    await _devolver(cliente, e, otra["id"], "Falta una firma")
    assert (await _registro(cliente, e["revisor"], otra["id"]))["sin_version"] == 0


async def test_quien_ve_el_registro(cliente, e, admin):
    """El SNM que ve la solicitud antes de aprobarse: UCVMM y el supervisor de su sector y el
    Administrador. La agencia, el puesto y el otro sector, no: tampoco los retirados."""
    s = await _enviada(cliente, e, "Luis")
    await _devolver(cliente, e, s["id"], "Falta una firma")
    s = await _corregir(cliente, e, s, ["Luis"], libreta_nueva="otra")
    [retirado] = [a for a in (await _registro(cliente, admin, s["id"]))["archivos"] if a["retirado_en"]]
    await verificar_impedimentos(cliente, e["revisor"], s["id"])
    assert (await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={}, headers=e["revisor"].headers)).status_code == 200
    ruta = f"/solicitudes/{s['id']}"
    for actor, lo_ve in ((e["revisor"], True), (e["supervisor"], True), (admin, True), (e["naviera"], False),
                         (e["del_puesto"], False), (e["otro_sector"], False), (e["general"], False)):
        detalle = await cliente.get(ruta, headers=actor.headers)
        if detalle.status_code == 200:
            assert detalle.json()["acciones"]["ver_registro"] is lo_ve, actor.username
            assert retirado["id"] not in {d["id"] for d in detalle.json()["documentos"]}
        assert (await cliente.get(f"{ruta}/registro", headers=actor.headers)).status_code == (200 if lo_ve else 403), actor.username
        r = await cliente.get(f"{ruta}/documentos/{retirado['id']}", headers=actor.headers)
        assert (r.status_code == 200) is lo_ve, actor.username
    # Por otra solicitud, tampoco quien lo ve.
    otra = await _enviada(cliente, e, "Luis")
    r = await cliente.get(f"/solicitudes/{otra['id']}/documentos/{retirado['id']}", headers=e["revisor"].headers)
    assert r.status_code == 404


async def test_un_tecnico_lo_ve_el_supervisor_general(cliente, e):
    """Es de un trámite que supervisa: lo ve todo, también el registro."""
    async with SesionLocal() as s:
        tipo = (await s.execute(select(TipoTramite.id).where(TipoTramite.codigo == "F3-TECNICO"))).scalar_one()
        solicitud = Solicitud(
            numero=f"HC-{secrets.token_hex(3)}", agencia_id=e["agencia"]["id"], agencia_nombre=e["agencia"]["nombre"],
            creada_por_id=e["naviera"].id, tipo_tramite_id=tipo, puesto_control_id=e["puesto"]["id"],
            puesto_nombre=e["puesto"]["nombre"], titulo="Técnico", fecha_operacion=date.today() + timedelta(days=3),
            cantidad_tripulantes=0, enviada_en=datetime.now(timezone.utc),
        )
        s.add(solicitud)
        await s.commit()
    assert (await _registro(cliente, e["general"], solicitud.id)) == {"versiones": [], "sin_version": 0, "archivos": []}


async def test_comparar_dos_versiones():
    antes = {"datos": [["Buque", "A"], ["Puerto", "Balboa"]],
             "tripulantes": [{"id": 1, "nombre": "Ana Ríos", "datos": [["Pasaporte", "P1"], ["Verificación de UCVMM", "Sin impedimento"]]},
                             {"id": 2, "nombre": "Beto Cruz", "datos": []}],
             "documentos": [{"id": 1, "documento": "Libreta", "tripulante": "Ana Ríos", "nombre": "a.pdf"}]}
    despues = {"datos": [["Buque", "B"], ["Motivo", "Cambio"]],
               "tripulantes": [{"id": 1, "nombre": "Ana María Ríos", "datos": [["Pasaporte", "P2"]]},
                               {"id": 3, "nombre": "Carla Díaz", "datos": []}],
               "documentos": [{"id": 1, "documento": "Libreta", "tripulante": "Ana María Ríos", "nombre": "a.pdf"},
                              {"id": 2, "documento": None, "tripulante": None, "nombre": "carta.pdf"}]}
    assert comparar(antes, despues) == [
        "Buque: A → B", "Puerto: Balboa → (vacío)", "Motivo: (vacío) → Cambio",
        "Tripulante quitado: Beto Cruz", "Ana Ríos, nombre: Ana Ríos → Ana María Ríos", "Ana Ríos, pasaporte: P1 → P2",
        "Tripulante agregado: Carla Díaz", "Documento agregado: Documento adicional (carta.pdf)"]
    assert comparar(antes, antes) == []


# ── La huella ─────────────────────────────────────────────────────────────────

async def test_cada_documento_guarda_su_huella(cliente, e):
    s = await _enviada(cliente, e, "Luis")
    async with SesionLocal() as sesion:
        documentos = (await sesion.execute(select(DocumentoSolicitud).where(DocumentoSolicitud.solicitud_id == s["id"]))).scalars().all()
    assert len(documentos) == 4
    for d in documentos:
        contenido = (almacenamiento.raiz_documentos() / d.ruta).read_bytes()
        assert d.sha256 == hashlib.sha256(contenido).hexdigest() and d.tamano == len(contenido)


async def test_un_archivo_alterado_no_se_muestra(cliente, e, caplog):
    s = await _enviada(cliente, e, "Luis")
    documento = s["documentos"][0]
    async with SesionLocal() as sesion:
        ruta = almacenamiento.raiz_documentos() / (await sesion.get(DocumentoSolicitud, documento["id"])).ruta
    original = ruta.read_bytes()
    ruta.write_bytes(original.replace(b"trailer", b"TRAILER"))   # mide lo mismo
    pedir = f"/solicitudes/{s['id']}/documentos/{documento['id']}"
    with caplog.at_level(logging.ERROR):
        r = await cliente.get(pedir, headers=e["revisor"].headers)
    assert r.status_code == 409 and "no coincide" in r.json()["detail"]
    assert any("no coincide con su huella" in m for m in caplog.messages), "queda en el log, que lo ve la vigilancia"
    ruta.write_bytes(original)
    assert (await cliente.get(pedir, headers=e["revisor"].headers)).status_code == 200


async def test_las_huellas_de_los_de_antes(cliente, e):
    """Los documentos subidos antes no la tienen: se les calcula una vez. El que falta en el disco, no."""
    s = await _enviada(cliente, e, "Luis")
    ids = [d["id"] for d in s["documentos"]]
    async with SesionLocal() as sesion:
        await sesion.execute(update(DocumentoSolicitud).where(DocumentoSolicitud.id.in_(ids)).values(sha256=None))
        rutas = dict((await sesion.execute(select(DocumentoSolicitud.id, DocumentoSolicitud.ruta).where(DocumentoSolicitud.id.in_(ids)))).all())
        await sesion.commit()
    falta = almacenamiento.raiz_documentos() / rutas[ids[0]]
    falta.unlink()
    assert (await cliente.get(f"/solicitudes/{s['id']}/documentos/{ids[1]}", headers=e["revisor"].headers)).status_code == 200, \
        "sin huella se muestra igual"
    assert await huellas.completar_huellas() >= 3
    async with SesionLocal() as sesion:
        puestas = dict((await sesion.execute(select(DocumentoSolicitud.id, DocumentoSolicitud.sha256).where(DocumentoSolicitud.id.in_(ids)))).all())
    assert puestas[ids[0]] is None
    for i in ids[1:]:
        assert puestas[i] == hashlib.sha256((almacenamiento.raiz_documentos() / rutas[i]).read_bytes()).hexdigest()


# ── El PDF tal como se emitió ─────────────────────────────────────────────────

async def _emitidos(sid: int) -> dict[str, DocumentoEmitido]:
    async with SesionLocal() as sesion:
        filas = (await sesion.execute(select(DocumentoEmitido).where(DocumentoEmitido.solicitud_id == sid))).scalars().all()
    return {f.tipo: f for f in filas}


async def test_la_autorizacion_se_guarda_tal_como_se_emitio(cliente, e, monkeypatch):
    s = await _aprobada(cliente, e)
    sid = s["id"]
    emitido = (await _emitidos(sid))["aprobada"]
    guardado = (almacenamiento.raiz_documentos() / emitido.ruta).read_bytes()
    assert guardado.startswith(b"%PDF") and (emitido.sha256, emitido.tamano) == (hashlib.sha256(guardado).hexdigest(), len(guardado))

    # Aunque mañana cambie el formato, la agencia y el QR reciben la que se emitió.
    for modulo in (emision, api_solicitudes):
        monkeypatch.setattr(modulo, "generar_pdf_autorizacion", lambda datos: b"%PDF-otro formato")
    async with SesionLocal() as sesion:
        codigo = (await sesion.execute(select(Solicitud.codigo_verificacion).where(Solicitud.id == sid))).scalar_one()
    for r in (await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e["naviera"].headers),
              await cliente.get(f"/verificacion/{codigo}/autorizacion.pdf")):
        assert r.status_code == 200 and r.content == guardado and r.headers["content-type"] == "application/pdf"
    # La copia interna del SNM no se emite: se arma con los nombres.
    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e["revisor"].headers)
    assert r.content == b"%PDF-otro formato" and "-interna" in r.headers["content-disposition"]

    # Al finalizar se emite otra; la primera se conserva, y el registro muestra las dos.
    monkeypatch.undo()
    await _finalizar(cliente, e, sid)
    emitidos = await _emitidos(sid)
    assert set(emitidos) == {"aprobada", "finalizada"} and emitidos["aprobada"].sha256 == emitido.sha256
    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e["naviera"].headers)
    assert hashlib.sha256(r.content).hexdigest() == emitidos["finalizada"].sha256 != emitido.sha256
    archivos = [a for a in (await _registro(cliente, e["supervisor"], sid))["archivos"] if a["clase"] == "emitido"]
    assert [(a["documento"], a["sha256"]) for a in archivos] == [
        ("Autorización aprobada", emitido.sha256), ("Autorización finalizada", emitidos["finalizada"].sha256)]
    for a in archivos:
        ruta = f"/solicitudes/{sid}/emitidos/{a['id']}"
        r = await cliente.get(ruta, headers=e["supervisor"].headers)
        assert r.status_code == 200 and hashlib.sha256(r.content).hexdigest() == a["sha256"]
        for actor in (e["naviera"], e["del_puesto"], e["otro_sector"]):
            assert (await cliente.get(ruta, headers=actor.headers)).status_code == 403, actor.username
    assert (await cliente.get(f"/solicitudes/{sid}/emitidos/999999", headers=e["supervisor"].headers)).status_code == 404
    otra = await _aprobada(cliente, e)
    r = await cliente.get(f"/solicitudes/{otra['id']}/emitidos/{archivos[0]['id']}", headers=e["supervisor"].headers)
    assert r.status_code == 404, "es de otra solicitud"


async def test_una_emitida_que_falta_o_se_altera_se_dice_y_no_frena_a_la_agencia(cliente, e, caplog):
    s = await _aprobada(cliente, e)
    emitido = (await _emitidos(s["id"]))["aprobada"]
    ruta = almacenamiento.raiz_documentos() / emitido.ruta
    for romper in (lambda: ruta.write_bytes(b"%PDF-" + b"x" * (emitido.tamano - 5)), ruta.unlink):
        romper()
        caplog.clear()
        with caplog.at_level(logging.ERROR):
            r = await cliente.get(f"/solicitudes/{s['id']}/autorizacion.pdf", headers=e["naviera"].headers)
        assert r.status_code == 200 and r.content.startswith(b"%PDF") and b"xxxxx" not in r.content, "se arma de nuevo"
        assert any("autorización emitida" in m for m in caplog.messages)
        r = await cliente.get(f"/solicitudes/{s['id']}/emitidos/{emitido.id}", headers=e["revisor"].headers)
        assert r.status_code in (404, 409), "pero el registro no muestra otra cosa que la emitida"


async def test_se_emite_una_sola_vez(cliente, e, monkeypatch):
    """La respuesta, la tarea de fondo y la primera descarga pueden emitirla a la vez: vale una."""
    s = await _aprobada(cliente, e)
    async with SesionLocal() as sesion:
        await sesion.execute(DocumentoEmitido.__table__.delete().where(DocumentoEmitido.solicitud_id == s["id"]))
        await sesion.commit()
    armados = []

    def despacio(datos):
        armados.append(b"%PDF-" + secrets.token_bytes(8))   # cada uno, distinto
        time.sleep(0.6)   # las demás ya miraron que no había ninguna
        return armados[-1]

    monkeypatch.setattr(emision, "generar_pdf_autorizacion", despacio)
    carpeta = almacenamiento.carpeta_solicitud(s["id"])
    antes = set(carpeta.glob("autorizacion-*"))
    emitidos = await asyncio.gather(*(emision.asegurar_emision(s["id"]) for _ in range(4)))
    assert len(armados) > 1 and len({x.id for x in emitidos}) == 1
    [archivo] = set(carpeta.glob("autorizacion-*")) - antes   # los que sobran no quedan en el disco
    assert hashlib.sha256(archivo.read_bytes()).hexdigest() == emitidos[0].sha256


async def test_las_que_faltan_se_emiten_solas(cliente, e, monkeypatch):
    """Si el proceso se cae entre aprobar y emitir, o la solicitud es de antes: las completa la
    tarea de fondo. Una que falla no frena a las demás."""
    buena, mala = await _aprobada(cliente, e), await _aprobada(cliente, e)
    nunca = await _enviada(cliente, e, "Luis")
    async with SesionLocal() as sesion:
        for tabla in (DocumentoEmitido,):
            await sesion.execute(tabla.__table__.delete().where(tabla.solicitud_id.in_((buena["id"], mala["id"]))))
        await sesion.commit()
    original = emision.generar_pdf_autorizacion

    def generar(datos):
        if datos.numero == mala["numero"]:
            raise RuntimeError("sin fuentes")
        return original(datos)

    monkeypatch.setattr(emision, "generar_pdf_autorizacion", generar)
    await emision.emitir_pendientes()
    assert set(await _emitidos(buena["id"])) == {"aprobada"} and await _emitidos(mala["id"]) == {}
    monkeypatch.undo()
    assert await emision.emitir_pendientes() >= 1
    assert set(await _emitidos(mala["id"])) == {"aprobada"} and await _emitidos(nunca["id"]) == {}
    assert await emision.emitir_pendientes() == 0, "ya no falta ninguna"


async def test_la_vencida_no_emite(cliente, e):
    s = await _aprobada(cliente, e)
    async with SesionLocal() as sesion:
        await sesion.execute(update(Solicitud).where(Solicitud.id == s["id"]).values(estado="expired", expirada_en=func.now()))
        await sesion.commit()
    assert await emision.asegurar_emision(s["id"]) is None
    assert set(await _emitidos(s["id"])) == {"aprobada"}, "se conserva la que se emitió al aprobar"
    archivos = (await _registro(cliente, e["revisor"], s["id"]))["archivos"]
    assert [a["documento"] for a in archivos if a["clase"] == "emitido"] == ["Autorización aprobada"]


async def test_la_version_y_lo_emitido_no_se_tocan(cliente, e):
    """En la base, solo se agregan: lo prueba test_permisos_bd.py con la cuenta de la aplicación."""
    async with SesionLocal() as sesion:
        assert (await sesion.execute(select(func.count()).select_from(VersionSolicitud))).scalar() >= 1
    from app.infrastructure.permisos_bd import TABLAS_SIN_BORRAR, TABLAS_SOLO_AGREGAR

    assert {"solicitud_versiones", "documentos_emitidos"} <= set(TABLAS_SOLO_AGREGAR)
    assert "solicitud_documentos" in TABLAS_SIN_BORRAR
