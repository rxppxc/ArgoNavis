"""Sectores de UCVMM y supervisión de solo lectura (2026-11-10).

Cada puesto es del Sector Pacífico o del Atlántico. UCVMM y el supervisor de
sector ven (y UCVMM revisa) solo las solicitudes de los puestos de sus
sectores; el supervisor general y el Administrador, las de los dos. Los
supervisores no deciden nada. El aviso de cada solicitud nueva va al buzón de
su sector.
"""
import secrets
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.models.catalogo import AgenciaNaviera
from app.domain.models.solicitud import Solicitud
from app.domain.models.tramite import TipoTramite
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.domain.services.notificacion_service import ServicioNotificacion
from app.infrastructure.database import SesionLocal
from conftest import ATLANTICO, PACIFICO, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _escenario(cliente, admin) -> dict:
    """Una agencia, un puesto en cada sector y una solicitud en revisión en cada uno."""
    sufijo = secrets.token_hex(3)
    puestos = {}
    for nombre in (PACIFICO, ATLANTICO):
        r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto {nombre} {sufijo}",
                                                       "sector_id": await id_sector(nombre)}, headers=admin.headers)
        assert r.status_code == 201, r.text
        assert r.json()["sector_nombre"] == nombre
        puestos[nombre] = r.json()
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia Sectores {sufijo}")
        s.add(agencia)
        await s.commit()
    naviera = await crear_actor("Naviera", agencia_id=agencia.id, prefijo="naviera")
    ids = {}
    async with SesionLocal() as s:
        tipo_id = (await s.execute(select(TipoTramite.id).limit(1))).scalar_one()
        for nombre, puesto in puestos.items():
            solicitud = Solicitud(
                agencia_id=agencia.id, agencia_nombre=agencia.nombre, creada_por_id=naviera.id,
                tipo_tramite_id=tipo_id, puesto_control_id=puesto["id"], puesto_nombre=puesto["nombre"],
                titulo=f"Prueba de sectores {sufijo}", fecha_operacion=date.today() + timedelta(days=5),
                cantidad_tripulantes=0, estado="review", enviada_en=datetime.now(timezone.utc),
            )
            s.add(solicitud)
            await s.flush()
            ids[nombre] = solicitud.id
        await s.commit()
    return {"sufijo": sufijo, "puestos": puestos, "ids": ids, "naviera": naviera}


async def _ids_en(cliente, actor, bandeja: str, sufijo: str) -> set[int]:
    r = await cliente.get(f"/solicitudes/{bandeja}", params={"texto": sufijo, "por_pagina": 100}, headers=actor.headers)
    assert r.status_code == 200, (bandeja, r.text)
    return {x["id"] for x in r.json()["items"]}


async def test_cada_sector_ve_y_revisa_solo_lo_suyo(cliente, admin):
    e = await _escenario(cliente, admin)
    pac, atl = e["ids"][PACIFICO], e["ids"][ATLANTICO]
    revisor_pac = await crear_actor("UCVMM", prefijo="revisor")
    revisor_atl = await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,))
    revisor_ambos = await crear_actor("UCVMM", prefijo="revisor", sectores=(PACIFICO, ATLANTICO))

    assert await _ids_en(cliente, revisor_pac, "revision", e["sufijo"]) == {pac}
    assert await _ids_en(cliente, revisor_atl, "revision", e["sufijo"]) == {atl}
    assert await _ids_en(cliente, revisor_ambos, "revision", e["sufijo"]) == {pac, atl}
    assert await _ids_en(cliente, admin, "revision", e["sufijo"]) == {pac, atl}

    # El expediente del otro sector no se abre ni se decide.
    r = await cliente.get(f"/solicitudes/{atl}", headers=revisor_pac.headers)
    assert r.status_code == 403
    r = await cliente.post(f"/solicitudes/{atl}/negar", json={"motivo": "No es de mi sector"}, headers=revisor_pac.headers)
    assert r.status_code == 403
    r = await cliente.get(f"/solicitudes/{pac}", headers=revisor_pac.headers)
    assert r.status_code == 200 and r.json()["acciones"]["revisar"] is True
    assert r.json()["sector_nombre"] == PACIFICO

    # La agencia no trabaja con sectores: no se lo mandamos.
    r = await cliente.get(f"/solicitudes/{pac}", headers=e["naviera"].headers)
    assert r.status_code == 200 and r.json()["sector_nombre"] is None

    # La campana del revisor del Atlántico cuenta lo mismo que su bandeja: lo de su sector.
    r = await cliente.get("/pendientes", headers=revisor_atl.headers)
    por_revisar = next(x for x in r.json()["pendientes"] if x["clave"] == "por_revisar")
    bandeja = (await cliente.get("/solicitudes/revision", headers=revisor_atl.headers)).json()
    assert por_revisar["cantidad"] == bandeja["conteos"]["review"] >= 1
    todas = (await cliente.get("/solicitudes/revision", headers=revisor_ambos.headers)).json()
    assert todas["conteos"]["review"] > bandeja["conteos"]["review"], "el Pacífico tiene las suyas"

    # Sin sector asignado no ve nada: la bandeja lo dice.
    sin_sector = await crear_actor("UCVMM", prefijo="revisor", sectores=())
    r = await cliente.get("/solicitudes/revision", headers=sin_sector.headers)
    assert r.status_code == 409 and "sector" in r.json()["detail"]


async def test_mover_un_puesto_de_sector_mueve_sus_solicitudes(cliente, admin):
    e = await _escenario(cliente, admin)
    pac = e["ids"][PACIFICO]
    revisor_atl = await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,))
    assert pac not in await _ids_en(cliente, revisor_atl, "revision", e["sufijo"])
    puesto = e["puestos"][PACIFICO]
    r = await cliente.patch(f"/admin/puestos/{puesto['id']}", json={"sector_id": await id_sector(ATLANTICO)},
                            headers=admin.headers)
    assert r.status_code == 200 and r.json()["sector_nombre"] == ATLANTICO
    assert pac in await _ids_en(cliente, revisor_atl, "revision", e["sufijo"])


async def test_los_supervisores_ven_sin_decidir(cliente, admin):
    e = await _escenario(cliente, admin)
    pac, atl = e["ids"][PACIFICO], e["ids"][ATLANTICO]
    sup_sector = await crear_actor("Supervisor de sector", prefijo="supervisor")
    sup_general = await crear_actor("Supervisor general", prefijo="supervisor")

    assert await _ids_en(cliente, sup_sector, "supervision", e["sufijo"]) == {pac}
    assert await _ids_en(cliente, sup_general, "supervision", e["sufijo"]) == {pac, atl}
    for actor, visibles in ((sup_sector, (pac,)), (sup_general, (pac, atl))):
        for sid in visibles:
            r = await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)
            assert r.status_code == 200
            assert not any(r.json()["acciones"].values()), "sin acciones: solo lectura"
            assert r.json()["sector_nombre"] is not None, "es personal del SNM: ve lo interno"
        r = await cliente.post(f"/solicitudes/{pac}/aprobar", json={"observacion": None}, headers=actor.headers)
        assert r.status_code == 403
        r = await cliente.get("/solicitudes/revision", headers=actor.headers)
        assert r.status_code == 403, "la cola de revisión es de UCVMM"
    r = await cliente.get(f"/solicitudes/{atl}", headers=sup_sector.headers)
    assert r.status_code == 403
    # Sin campana: no tienen nada que hacer.
    r = await cliente.get("/pendientes", headers=sup_general.headers)
    assert r.json()["disponible"] is False
    # UCVMM no supervisa (tiene su bandeja de revisión).
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    assert (await cliente.get("/solicitudes/supervision", headers=revisor.headers)).status_code == 403


async def test_estadisticas_por_sector(cliente, admin):
    e = await _escenario(cliente, admin)
    revisor_atl = await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,))
    sup_general = await crear_actor("Supervisor general", prefijo="supervisor")
    pacifico, atlantico = await id_sector(PACIFICO), await id_sector(ATLANTICO)

    r = await cliente.get("/solicitudes/estadisticas", headers=revisor_atl.headers)
    est = r.json()
    assert r.status_code == 200 and est["alcance"] == ATLANTICO and est["uso_del_sistema"] is False
    assert [x["nombre"] for x in est["sectores"]] == [ATLANTICO]
    r = await cliente.get("/solicitudes/estadisticas", params={"sector_id": pacifico}, headers=revisor_atl.headers)
    assert r.status_code == 403
    assert (await cliente.get("/admin/stats", headers=revisor_atl.headers)).status_code == 403

    todas = (await cliente.get("/solicitudes/estadisticas", headers=sup_general.headers)).json()
    assert todas["alcance"] == "Todos los sectores" and todas["uso_del_sistema"] is True
    assert [x["nombre"] for x in todas["sectores"]] == [PACIFICO, ATLANTICO]
    solo_atl = (await cliente.get("/solicitudes/estadisticas", params={"sector_id": atlantico},
                                  headers=sup_general.headers)).json()
    solo_pac = (await cliente.get("/solicitudes/estadisticas", params={"sector_id": pacifico},
                                  headers=sup_general.headers)).json()
    assert solo_atl["alcance"] == ATLANTICO and solo_atl["sector_id"] == atlantico
    assert solo_atl["recibidas"] == est["recibidas"] >= 1, "el revisor ve lo mismo que el supervisor en su sector"
    assert solo_atl["recibidas"] + solo_pac["recibidas"] == todas["recibidas"]
    assert (await cliente.get("/admin/stats", headers=sup_general.headers)).status_code == 200
    r = await cliente.get("/solicitudes/estadisticas/exportar", params={"formato": "csv", "sector_id": atlantico},
                          headers=sup_general.headers)
    assert r.status_code == 200 and "sector-atlantico" in r.headers["content-disposition"]
    assert e["ids"]


async def test_el_aviso_va_al_buzon_del_sector(cliente, admin, monkeypatch):
    """Con buzón, al del sector; sin buzón, al general de UCVMM (CORREO_UCVMM)."""
    from app.domain.services import notificacion_service

    e = await _escenario(cliente, admin)
    monkeypatch.setattr(notificacion_service.configuracion, "CORREO_UCVMM", "ucvmm@prueba.pa")
    pacifico, atlantico = await id_sector(PACIFICO), await id_sector(ATLANTICO)
    for sector, correo in ((atlantico, "atlantico@prueba.pa"), (pacifico, None)):
        r = await cliente.patch(f"/admin/sectores/{sector}", json={"correo": correo}, headers=admin.headers)
        assert r.status_code == 200 and r.json()["correo"] == correo
    try:
        async with SesionLocal() as s:
            repo = RepositorioSolicitud(s)
            for nombre, esperado in ((ATLANTICO, "atlantico@prueba.pa"), (PACIFICO, "ucvmm@prueba.pa")):
                solicitud = await repo.buscar_por_id(e["ids"][nombre])
                avisos = await ServicioNotificacion(s).recibida(solicitud, corregida=False)
                assert [a.destinatarios for a in avisos] == [[esperado]], nombre
    finally:
        await cliente.patch(f"/admin/sectores/{atlantico}", json={"correo": None}, headers=admin.headers)


async def test_catalogo_de_sectores(cliente, admin):
    r = await cliente.get("/admin/sectores", headers=admin.headers)
    assert r.status_code == 200
    assert [x["nombre"] for x in r.json()] == [PACIFICO, ATLANTICO]
    atlantico = await id_sector(ATLANTICO)
    revisor = await crear_actor("UCVMM", prefijo="revisor", sectores=())
    r = await cliente.put(f"/admin/sectores/{atlantico}/usuarios", json={"usuario_ids": [revisor.id]},
                          headers=admin.headers)
    assert r.status_code == 200 and [u["id"] for u in r.json()["usuarios"]] == [revisor.id]
    assert (await cliente.get("/solicitudes/revision", headers=revisor.headers)).status_code == 200
    r = await cliente.put(f"/admin/sectores/{atlantico}/usuarios", json={"usuario_ids": []}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["usuarios"] == []

    # Un puesto necesita su sector, y uno que exista.
    r = await cliente.post("/admin/puestos", json={"nombre": f"Sin sector {secrets.token_hex(2)}"}, headers=admin.headers)
    assert r.status_code == 422
    r = await cliente.post("/admin/puestos", json={"nombre": f"Sector raro {secrets.token_hex(2)}", "sector_id": 999999},
                           headers=admin.headers)
    assert r.status_code == 400
    # Solo el Administrador administra los sectores.
    assert (await cliente.get("/admin/sectores", headers=revisor.headers)).status_code == 403
