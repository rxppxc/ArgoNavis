"""Cambio de puerto dentro de la solicitud (pedido del usuario del 2026-11-13).

El trámite «Cambio de Puerto» dejó de existir: en Embarque y Desembarque la agencia
indica el nuevo puesto de control, que tiene que ser del mismo sector que el
primero (si no, presenta otra solicitud y esta vence sola). La revisa UCVMM del
sector del primer puesto; la ve en su bandeja, recibe el aviso y la finaliza el
puesto nuevo; el primero solo la consulta (el expediente y la consulta histórica).
"""
import secrets

import pytest

from app.core.pdf_autorizacion import generar_pdf_autorizacion
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.services.notificacion_service import ServicioNotificacion
from app.domain.services.solicitud_service import ServicioSolicitud
from app.infrastructure.database import SesionLocal
from ayudas import cabecera, enviar, pdf, tripulante
from conftest import ATLANTICO, PACIFICO, Actor, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def verificar_impedimentos(cliente, actor: Actor, solicitud_id: int, ruta: str = "impedimentos") -> None:
    """Todos sin impedimento: la de UCVMM (`impedimentos`) o la del puesto (`impedimentos-puesto`)."""
    detalle = (await cliente.get(f"/solicitudes/{solicitud_id}", headers=actor.headers)).json()
    cuerpo = {"tripulantes": [{"tripulante_id": t["id"], "con_impedimento": False} for t in detalle["tripulantes"]]}
    r = await cliente.post(f"/solicitudes/{solicitud_id}/{ruta}", json=cuerpo, headers=actor.headers)
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def e(cliente, admin) -> dict:
    """Dos puestos del Pacífico (con su funcionario cada uno), uno del Atlántico y una agencia."""
    sufijo = secrets.token_hex(2)

    async def crear(ruta: str, cuerpo: dict) -> dict:
        r = await cliente.post(ruta, json=cuerpo, headers=admin.headers)
        assert r.status_code == 201, r.text
        return r.json()

    origen = await crear("/admin/puestos", {"nombre": f"Puerto de Balboa CP {sufijo}", "sector_id": await id_sector(PACIFICO)})
    destino = await crear("/admin/puestos", {"nombre": f"Puerto de Rodman CP {sufijo}", "correo": "rodman@prueba.pa",
                                             "sector_id": await id_sector(PACIFICO)})
    otro_sector = await crear("/admin/puestos", {"nombre": f"Puerto de Cristóbal CP {sufijo}",
                                                 "sector_id": await id_sector(ATLANTICO)})
    agencia = await crear("/admin/agencias", {"nombre": f"Agencia Cambio de Puerto {sufijo}"})
    naviera = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    del_origen = await crear_actor("Puesto de Control", correo="balboa.cp@prueba.pa", prefijo="puerto")
    del_destino = await crear_actor("Puesto de Control", correo="rodman.cp@prueba.pa", prefijo="puerto")
    for puesto, actor in ((origen, del_origen), (destino, del_destino)):
        r = await cliente.put(f"/admin/puestos/{puesto['id']}/usuarios", json={"usuario_ids": [actor.id]},
                              headers=admin.headers)
        assert r.status_code == 200, r.text
    return {"origen": origen, "destino": destino, "otro_sector": otro_sector, "naviera": naviera,
            "del_origen": del_origen, "del_destino": del_destino, "revisor": await crear_actor("UCVMM", prefijo="revisor")}


async def _enviar(cliente, e: dict, puesto_destino_id: int | None, codigo: str = "F3-EMBARQUE"):
    """Un Embarque (o un Cambio de nave) con un marino: visa, pasaporte y, en Embarque, la libreta."""
    asignaciones = [{"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
                    {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0}]
    archivos = [pdf("visa"), pdf("pasaporte")]
    if codigo == "F3-EMBARQUE":
        asignaciones.append({"documento_codigo": "DOC-LIBRETA-MARINO", "indice_tripulante": 0})
        archivos.append(pdf("libreta"))
    datos = cabecera(codigo, e["origen"]["id"], puesto_destino_id=puesto_destino_id,
                     tripulantes=[tripulante("Luis")], asignaciones=asignaciones)
    return await enviar(cliente, e["naviera"], datos, archivos)


async def test_el_formulario_recibe_el_sector_de_cada_puesto(cliente, e):
    r = await cliente.get("/catalogos/puestos", headers=e["naviera"].headers)
    sectores = {p["id"]: p["sector_id"] for p in r.json()}
    assert sectores[e["origen"]["id"]] == sectores[e["destino"]["id"]] != sectores[e["otro_sector"]["id"]]
    assert all("sector_nombre" not in p for p in r.json()), "a la agencia no se le nombran los sectores"


async def test_solo_a_otro_puesto_del_mismo_sector(cliente, e, admin):
    r = await _enviar(cliente, e, e["otro_sector"]["id"])
    assert r.status_code == 400 and "nueva solicitud" in r.json()["detail"], r.text
    assert "Sector" not in r.json()["detail"] and "UCVMM" not in r.json()["detail"], "lo lee la agencia"

    r = await _enviar(cliente, e, e["origen"]["id"])
    assert r.status_code == 400 and "otro puesto" in r.json()["detail"], r.text

    r = await _enviar(cliente, e, 999_999)
    assert r.status_code == 400 and "no existe o no está activo" in r.json()["detail"], r.text

    sufijo = secrets.token_hex(2)
    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto inactivo CP {sufijo}",
                                                   "sector_id": await id_sector(PACIFICO)}, headers=admin.headers)
    inactivo = r.json()["id"]
    r = await cliente.patch(f"/admin/puestos/{inactivo}", json={"activo": False}, headers=admin.headers)
    assert r.status_code == 200, r.text
    r = await _enviar(cliente, e, inactivo)
    assert r.status_code == 400 and "no existe o no está activo" in r.json()["detail"], r.text


async def test_la_finaliza_el_puesto_nuevo(cliente, e, admin):
    r = await _enviar(cliente, e, e["destino"]["id"])
    assert r.status_code == 201, r.text
    s = r.json()
    sid = s["id"]
    assert s["puesto_destino_id"] == e["destino"]["id"]
    assert s["puesto_destino_nombre"] == e["destino"]["nombre"] and s["puesto_nombre"] == e["origen"]["nombre"]

    # La revisa UCVMM del sector del primer puesto (el mismo del nuevo).
    await verificar_impedimentos(cliente, e["revisor"], sid)
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e["revisor"].headers)
    assert r.status_code == 200, r.text

    # El aviso de aprobación va al puesto nuevo, no al primero.
    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(admin.id))
        avisos = await ServicioNotificacion(sesion).aprobada(await svc.obtener(ctx, sid))
    al_puesto = next(a for a in avisos if a.titulo.startswith("Autorización aprobada para tu puesto"))
    assert set(al_puesto.destinatarios) == {"rodman@prueba.pa", "rodman.cp@prueba.pa"}
    assert "Cambio de puerto:" in (al_puesto.destacado or "")

    # El puesto nuevo la tiene en su bandeja y en la campana; el primero, no.
    async def en_bandeja(actor) -> bool:
        r = await cliente.get("/solicitudes/puerto", params={"por_pagina": 100}, headers=actor.headers)
        assert r.status_code == 200, r.text
        return sid in {x["id"] for x in r.json()["items"]}

    assert await en_bandeja(e["del_destino"]) and not await en_bandeja(e["del_origen"])
    r = await cliente.get("/pendientes", headers=e["del_destino"].headers)
    assert next(p for p in r.json()["pendientes"] if p["clave"] == "por_finalizar")["cantidad"] >= 1
    r = await cliente.get("/pendientes", headers=e["del_origen"].headers)
    assert next(p for p in r.json()["pendientes"] if p["clave"] == "por_finalizar")["cantidad"] == 0

    # El primero la consulta, pero no la finaliza.
    r = await cliente.get(f"/solicitudes/{sid}", headers=e["del_origen"].headers)
    assert r.status_code == 200 and r.json()["acciones"]["finalizar"] is False
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos-puesto",
                           json={"tripulantes": [{"tripulante_id": t["id"], "con_impedimento": False}
                                                 for t in r.json()["tripulantes"]]},
                           headers=e["del_origen"].headers)
    assert r.status_code == 403 and e["destino"]["nombre"] in r.json()["detail"], r.text
    r = await cliente.get("/solicitudes/historico", params={"texto": s["numero"]}, headers=e["del_origen"].headers)
    assert [x["id"] for x in r.json()["items"]] == [sid], "y la encuentra en la consulta histórica"

    # El PDF y la verificación del QR dicen el cambio.
    async with SesionLocal() as sesion:
        svc = ServicioSolicitud(sesion)
        ctx = await svc.contexto(await RepositorioUsuario(sesion).buscar_por_id(e["naviera"].id))
        datos_pdf = await svc.preparar_pdf(ctx, await svc.obtener(ctx, sid))
    assert datos_pdf.puesto_destino == e["destino"]["nombre"]
    assert generar_pdf_autorizacion(datos_pdf).startswith(b"%PDF")
    codigo = datos_pdf.codigo_verificacion
    r = await cliente.get(f"/verificacion/{codigo}")
    assert r.status_code == 200 and r.json()["puesto_destino_nombre"] == e["destino"]["nombre"]

    # El nuevo verifica los impedimentos y la finaliza.
    r = await cliente.get(f"/solicitudes/{sid}", headers=e["del_destino"].headers)
    assert r.json()["acciones"]["finalizar"] is True
    await verificar_impedimentos(cliente, e["del_destino"], sid, ruta="impedimentos-puesto")
    r = await cliente.post(f"/solicitudes/{sid}/finalizar", json={"comentario": "Embarcó en Rodman"},
                           headers=e["del_destino"].headers)
    assert r.status_code == 200, r.text
    assert r.json()["puesto_finalizacion_nombre"] == e["destino"]["nombre"]

    # La consulta histórica la encuentra por cualquiera de los dos puestos.
    for puesto in (e["origen"], e["destino"]):
        r = await cliente.get("/solicitudes/historico", params={"puesto_id": puesto["id"]}, headers=admin.headers)
        assert sid in {x["id"] for x in r.json()["items"]}, puesto["nombre"]


async def test_solo_en_embarque_y_desembarque(cliente, e):
    """2026-11-13: los demás trámites no ofrecen el cambio de puerto. Un nuevo puesto que
    llegue igual (resto de otro trámite elegido antes) se descarta, como los campos que
    el trámite no usa."""
    r = await cliente.get("/tramites", headers=e["naviera"].headers)
    con_cambio = {t["codigo"] for t in r.json() if t["permite_cambio_puerto"]}
    assert con_cambio == {"F3-EMBARQUE", "F3-DESEMBARQUE"}

    r = await _enviar(cliente, e, e["destino"]["id"], codigo="F3-CAMBIO-NAVE")
    assert r.status_code == 201, r.text
    assert r.json()["puesto_destino_id"] is None and r.json()["puesto_destino_nombre"] is None


async def test_al_corregir_se_puede_quitar_el_cambio(cliente, e):
    r = await _enviar(cliente, e, e["destino"]["id"])
    assert r.status_code == 201, r.text
    s = r.json()
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "El buque no cambia de puerto"},
                           headers=e["revisor"].headers)
    assert r.status_code == 200, r.text

    t = s["tripulantes"][0]
    ficha = tripulante("Luis", pasaporte=t["pasaporte"], libreta_marino=t["libreta_marino"])
    ficha["id"] = t["id"]
    correccion = cabecera(None, e["origen"]["id"], puesto_destino_id=None, tripulantes=[ficha], asignaciones=[],
                          documentos_conservados=[d["id"] for d in s["documentos"]])
    r = await enviar(cliente, e["naviera"], correccion, [], metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["puesto_destino_id"] is None and r.json()["puesto_destino_nombre"] is None
