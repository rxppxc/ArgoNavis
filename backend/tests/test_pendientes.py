"""Notificaciones internas (la campana): pendientes y novedades por rol, sin
las acciones propias y sin lo interno para la agencia (reunión del 2026-10-30)."""
import secrets

import pytest

from ayudas import cabecera, enviar, pdf, tripulante
from conftest import Actor, crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _campana(cliente, actor: Actor) -> dict:
    r = await cliente.get("/pendientes", headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


def _pendiente(campana: dict, clave: str) -> dict:
    return next(p for p in campana["pendientes"] if p["clave"] == clave)


def _novedades_de(campana: dict, solicitud_id: int) -> list[dict]:
    return [n for n in campana["novedades"] if n["solicitud_id"] == solicitud_id]


async def test_campana_por_rol(cliente, admin, sysadmin):
    sufijo = secrets.token_hex(2)

    async def crear(ruta: str, cuerpo: dict) -> dict:
        r = await cliente.post(ruta, json=cuerpo, headers=admin.headers)
        assert r.status_code == 201, r.text
        return r.json()

    agencia = await crear("/admin/agencias", {"nombre": f"Agencia Campana {sufijo}"})
    puesto = await crear("/admin/puestos", {"nombre": f"Puesto Campana {sufijo}"})
    otro_puesto = await crear("/admin/puestos", {"nombre": f"Otro Puesto Campana {sufijo}"})
    nav1 = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    nav2 = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    revisor = await crear_actor("Sector Pacífico", prefijo="revisor")
    del_puesto = await crear_actor("Puesto de Control", prefijo="puerto")
    de_otro_puesto = await crear_actor("Puesto de Control", prefijo="puerto")
    for p, actor in ((puesto, del_puesto), (otro_puesto, de_otro_puesto)):
        r = await cliente.put(f"/admin/puestos/{p['id']}/usuarios", json={"usuario_ids": [actor.id]}, headers=admin.headers)
        assert r.status_code == 200, r.text

    assert (await _campana(cliente, sysadmin)) == {"disponible": False, "pendientes": [], "novedades": [], "no_leidas": 0}
    antes = await _campana(cliente, revisor)
    assert antes["disponible"] and [p["clave"] for p in antes["pendientes"]] == ["por_revisar"]

    # ── La agencia envía: UCVMM tiene una más por revisar y la novedad ──
    datos = cabecera("F3-CAMBIO-NAVE", puesto["id"], tripulantes=[tripulante("Luis")], asignaciones=[
        {"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
        {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
    ])
    r = await enviar(cliente, nav1, datos, [pdf("visa"), pdf("pasaporte")])
    assert r.status_code == 201, r.text
    s = r.json()
    campana = await _campana(cliente, revisor)
    assert _pendiente(campana, "por_revisar")["cantidad"] == _pendiente(antes, "por_revisar")["cantidad"] + 1
    assert [n["tipo"] for n in _novedades_de(campana, s["id"])] == ["creada"]
    assert _novedades_de(campana, s["id"])[0]["no_leida"] and campana["no_leidas"] >= 1
    assert _novedades_de(await _campana(cliente, nav1), s["id"]) == [], "lo que hizo uno mismo no es novedad"

    # ── UCVMM la devuelve: la agencia tiene una por corregir, con el motivo ──
    r = await cliente.post(f"/solicitudes/{s['id']}/devolver", json={"motivo": "La visa está ilegible"},
                           headers=revisor.headers)
    assert r.status_code == 200, r.text
    campana = await _campana(cliente, nav2)
    por_corregir = _pendiente(campana, "por_corregir")
    assert por_corregir["cantidad"] == 1 and por_corregir["vence_en"] and por_corregir["bandeja"] == "agencia"
    devuelta, = _novedades_de(campana, s["id"])
    assert (devuelta["tipo"], devuelta["comentario"], devuelta["usuario_nombre"]) == (
        "devuelta", "La visa está ilegible", "UCVMM",
    ), "el motivo sí lo ve; el nombre del funcionario, no"
    assert _novedades_de(await _campana(cliente, revisor), s["id"])[0]["tipo"] == "creada"

    # ── Corrige otro usuario de la agencia; UCVMM verifica y aprueba ──
    detalle = (await cliente.get(f"/solicitudes/{s['id']}", headers=nav2.headers)).json()
    ficha = tripulante("Luis", pasaporte=detalle["tripulantes"][0]["pasaporte"])
    ficha["id"] = detalle["tripulantes"][0]["id"]
    correccion = cabecera(None, puesto["id"], tripulantes=[ficha], documentos_conservados=[d["id"] for d in detalle["documentos"]],
                          asignaciones=[])
    r = await enviar(cliente, nav2, correccion, [], metodo="PUT", ruta=f"/solicitudes/{s['id']}")
    assert r.status_code == 200, r.text
    assert [n["tipo"] for n in _novedades_de(await _campana(cliente, revisor), s["id"])] == ["corregida", "creada"]

    # Aprueba el Administrador: su campana junta la de UCVMM y la del puesto, sin lo que hizo él.
    impedimentos = {"tripulantes": [{"tripulante_id": t["id"], "con_impedimento": False} for t in r.json()["tripulantes"]]}
    assert (await cliente.post(f"/solicitudes/{s['id']}/impedimentos", json=impedimentos,
                               headers=admin.headers)).status_code == 200
    r = await cliente.post(f"/solicitudes/{s['id']}/aprobar", json={"observacion": "Nota interna de UCVMM"},
                           headers=admin.headers)
    assert r.status_code == 200, r.text
    campana = await _campana(cliente, admin)
    assert {p["clave"] for p in campana["pendientes"]} == {"por_revisar", "por_finalizar"}
    assert [n["tipo"] for n in _novedades_de(campana, s["id"])] == ["corregida", "creada"], "su aprobación no es novedad"

    # El puesto autorizado la tiene por finalizar; el otro puesto, no.
    campana = await _campana(cliente, del_puesto)
    assert _pendiente(campana, "por_finalizar")["cantidad"] == 1
    aprobada, = _novedades_de(campana, s["id"])
    assert aprobada["tipo"] == "aprobada" and aprobada["usuario_nombre"] == "Admin Prueba"
    otro = await _campana(cliente, de_otro_puesto)
    assert _pendiente(otro, "por_finalizar")["cantidad"] == 0 and _novedades_de(otro, s["id"]) == []

    # La agencia ve la aprobación sin la observación interna ni el nombre.
    campana = await _campana(cliente, nav1)
    assert [n["tipo"] for n in _novedades_de(campana, s["id"])] == ["aprobada", "devuelta"]
    aprobada = _novedades_de(campana, s["id"])[0]
    assert aprobada["comentario"] is None and aprobada["usuario_nombre"] == "UCVMM"
    assert all(n["tipo"] != "impedimentos" for n in campana["novedades"]), "lo interno no le llega"
    assert _pendiente(campana, "por_corregir")["cantidad"] == 0

    # ── Abrir la campana deja las novedades leídas ──
    assert campana["no_leidas"] == 2
    r = await cliente.post("/pendientes/vistas", headers=nav1.headers)
    assert r.status_code == 204
    campana = await _campana(cliente, nav1)
    assert campana["no_leidas"] == 0 and not any(n["no_leida"] for n in campana["novedades"])
    assert (await _campana(cliente, nav2))["no_leidas"] == 2, "cada usuario tiene las suyas"
