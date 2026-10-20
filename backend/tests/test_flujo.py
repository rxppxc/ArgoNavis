"""Flujo de Autorizaciones Marítimas de punta a punta, por la API.

Agencia → UCVMM → puesto de control, con el acceso por agencia, los
documentos con sesión, la separación de funciones, el bloqueo de fila, los
vencimientos y las bandejas paginadas.
"""
import asyncio
import secrets
from dataclasses import dataclass

import pytest
from sqlalchemy import select, text, update

from app.domain.models.solicitud import Solicitud
from app.domain.services.solicitud_service import ServicioSolicitud
from app.infrastructure.database import SesionLocal
from app.infrastructure.tareas import expirar_solicitudes
from ayudas import HOY, cabecera, enviar, pdf, tripulante
from conftest import STORAGE, Actor, crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class Escenario:
    puesto_a:  dict
    puesto_b:  dict
    agencia_a: dict
    agencia_b: dict
    nav_a1:    Actor   # dos usuarios de la misma agencia
    nav_a2:    Actor
    nav_b:     Actor   # otra agencia
    nav_sin:   Actor   # naviera sin agencia asignada
    revisor:   Actor   # UCVMM
    revisor_a: Actor   # UCVMM que además pertenece a la agencia A
    puerto_a:  Actor
    puerto_b:  Actor


async def solicitud_simple(cliente, actor: Actor, puesto_id: int) -> dict:
    """Cambio de Nave con un tripulante: visa + pasaporte."""
    datos = cabecera("F3-CAMBIO-NAVE", puesto_id, tripulantes=[tripulante("Luis")], asignaciones=[
        {"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
        {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
    ])
    r = await enviar(cliente, actor, datos, [pdf("visa"), pdf("pasaporte")])
    assert r.status_code == 201, r.text
    return r.json()


def cuerpo_impedimentos(detalle: dict, con_impedimento: set[str] = frozenset(),
                        comentario: str = "Sin impedimentos en SIMPLUS") -> dict:
    """La verificación por tripulante: todos "sin impedimento" salvo los nombrados."""
    return {
        "tripulantes": [{"tripulante_id": t["id"], "con_impedimento": t["nombre"] in con_impedimento}
                        for t in detalle["tripulantes"]],
        "comentario": comentario,
    }


async def verificar_impedimentos(cliente, actor: Actor, solicitud_id: int,
                                 con_impedimento: set[str] = frozenset()) -> dict:
    detalle = (await cliente.get(f"/solicitudes/{solicitud_id}", headers=actor.headers)).json()
    r = await cliente.post(f"/solicitudes/{solicitud_id}/impedimentos",
                           json=cuerpo_impedimentos(detalle, con_impedimento), headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def escenario(cliente, admin) -> Escenario:
    sufijo = secrets.token_hex(2)

    async def crear(ruta: str, cuerpo: dict) -> dict:
        r = await cliente.post(ruta, json=cuerpo, headers=admin.headers)
        assert r.status_code == 201, r.text
        return r.json()

    puesto_a  = await crear("/admin/puestos", {"nombre": f"Puerto de Balboa {sufijo}", "correo": "balboa@prueba.pa"})
    puesto_b  = await crear("/admin/puestos", {"nombre": f"Puerto de Rodman {sufijo}"})
    agencia_a = await crear("/admin/agencias", {"nombre": f"Agencia del Istmo {sufijo}", "correo": "istmo@prueba.pa"})
    agencia_b = await crear("/admin/agencias", {"nombre": f"Naviera del Pacífico {sufijo}"})

    e = Escenario(
        puesto_a=puesto_a, puesto_b=puesto_b, agencia_a=agencia_a, agencia_b=agencia_b,
        nav_a1=await crear_actor("Naviera", correo="a1@prueba.pa", prefijo="naviera"),
        nav_a2=await crear_actor("Naviera", prefijo="naviera"),
        nav_b=await crear_actor("Naviera", prefijo="naviera"),
        nav_sin=await crear_actor("Naviera", prefijo="naviera"),
        revisor=await crear_actor("Sector Pacífico", prefijo="revisor"),
        revisor_a=await crear_actor("Sector Pacífico", prefijo="revisor"),
        puerto_a=await crear_actor("Puesto de Control", correo="p1@prueba.pa", prefijo="puerto"),
        puerto_b=await crear_actor("Puesto de Control", prefijo="puerto"),
    )

    async def asignar(ruta: str, actores: list[Actor]) -> dict:
        r = await cliente.put(ruta, json={"usuario_ids": [a.id for a in actores]}, headers=admin.headers)
        assert r.status_code == 200, r.text
        return r.json()

    salida = await asignar(f"/admin/agencias/{agencia_a['id']}/usuarios", [e.nav_a1, e.nav_a2, e.revisor_a])
    assert sorted(u["id"] for u in salida["usuarios"]) == sorted([e.nav_a1.id, e.nav_a2.id, e.revisor_a.id])
    await asignar(f"/admin/agencias/{agencia_b['id']}/usuarios", [e.nav_b])
    await asignar(f"/admin/puestos/{puesto_a['id']}/usuarios", [e.puerto_a])
    await asignar(f"/admin/puestos/{puesto_b['id']}/usuarios", [e.puerto_b])

    r = await cliente.patch("/admin/paises/CUB", json={"nacionalidad_restringida": True}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["nacionalidad_restringida"]
    return e


# ── Catálogos y administración ───────────────────────────────────────────────

async def test_catalogos_y_permisos_de_admin(cliente, escenario: Escenario, admin):
    e = escenario
    r = await cliente.post("/admin/agencias", json={"nombre": e.agencia_a["nombre"].upper()}, headers=admin.headers)
    assert r.status_code == 409, "nombre de agencia duplicado (sin distinguir mayúsculas)"
    r = await cliente.post("/admin/puestos", json={"nombre": "Otro"}, headers=e.nav_a1.headers)
    assert r.status_code == 403, "la naviera no administra puestos"
    r = await cliente.get("/admin/agencias", headers=e.revisor.headers)
    assert r.status_code == 403, "UCVMM no administra agencias"

    r = await cliente.get("/catalogos/puestos", headers=e.nav_a1.headers)
    assert r.status_code == 200 and {e.puesto_a["id"], e.puesto_b["id"]} <= {p["id"] for p in r.json()}
    r = await cliente.get("/catalogos/paises", headers=e.nav_a1.headers)
    assert r.status_code == 200 and len(r.json()) > 240

    r = await cliente.get("/auth/me", headers=e.nav_a2.headers)
    assert r.json()["agencia"]["id"] == e.agencia_a["id"], "el perfil trae la agencia"


# ── Creación ─────────────────────────────────────────────────────────────────

async def test_validaciones_de_creacion(cliente, escenario: Escenario):
    e = escenario
    pid = e.puesto_a["id"]

    datos = cabecera("F3-DESEMBARQUE", pid, imo="1234568", tripulantes=[tripulante("Juan")], asignaciones=[])
    r = await enviar(cliente, e.nav_a1, datos, [])
    assert r.status_code == 400 and "IMO" in r.json()["detail"]

    datos = cabecera("F3-EMBARQUE", pid, tripulantes=[tripulante("Juan", pasaporte_expira=HOY.isoformat())], asignaciones=[])
    r = await enviar(cliente, e.nav_a1, datos, [])
    assert r.status_code == 400 and "pasaporte vence" in r.json()["detail"]

    datos = cabecera("F3-EMBARQUE", pid, tripulantes=[tripulante("Juan", libreta_marino=None, libreta_expira=None)], asignaciones=[])
    r = await enviar(cliente, e.nav_a1, datos, [])
    assert r.status_code == 400 and "seamanbook" in r.json()["detail"]

    datos = cabecera("F3-EMBARQUE", pid, tripulantes=[{"nombre": "Juan"}], asignaciones=[])
    r = await enviar(cliente, e.nav_a1, datos, [])
    assert r.status_code == 422 and "Tripulante 1" in r.json()["detail"]

    datos = cabecera("F3-EMBARQUE", pid, nombre_buque=None, tripulantes=[tripulante("Juan")], asignaciones=[])
    r = await enviar(cliente, e.nav_a1, datos, [])
    assert r.status_code == 400 and "Nombre del buque" in r.json()["detail"]

    r = await enviar(cliente, e.nav_sin, cabecera("F3-CAMBIO-NAVE", pid, tripulantes=[tripulante("Juan")]), [])
    assert r.status_code == 409 and "agencia" in r.json()["detail"], "sin agencia no se puede solicitar"

    r = await cliente.get("/solicitudes/agencia", headers=e.nav_sin.headers)
    assert r.status_code == 409

    # Más de 20 documentos adicionales
    asignaciones = [{"documento_codigo": None}] * 21
    datos = cabecera("F3-CAMBIO-NAVE", pid, tripulantes=[tripulante("Juan")], asignaciones=asignaciones)
    r = await enviar(cliente, e.nav_a1, datos, [pdf(f"extra{i}") for i in range(21)])
    assert r.status_code == 400 and "adicionales" in r.json()["detail"]

    # Archivo con extensión no permitida: no se registra nada
    datos = cabecera("F3-CAMBIO-NAVE", pid, tripulantes=[tripulante("Juan")], asignaciones=[
        {"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
        {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
    ])
    r = await enviar(cliente, e.nav_a1, datos, [pdf("visa"), ("script.exe", b"MZ", "application/octet-stream")])
    assert r.status_code == 415
    assert not list(STORAGE.glob("tmp-*")), "no quedan carpetas temporales tras un rechazo"


# ── Ciclo completo ───────────────────────────────────────────────────────────

async def test_ciclo_completo(cliente, escenario: Escenario):
    e = escenario
    pid = e.puesto_a["id"]

    # Desembarque: dos tripulantes, uno cubano (nacionalidad restringida)
    tripulantes = [tripulante("Juan", "PHL"), tripulante("Raúl", "CUB")]
    asignaciones, archivos = [], []
    for i in range(2):
        for codigo in ("DOC-BOLETO-AEREO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO"):
            asignaciones.append({"documento_codigo": codigo, "indice_tripulante": i})
            archivos.append(pdf(f"{codigo}-{i}"))
    asignaciones.append({"documento_codigo": "DOC-LISTA-TRIPULANTES"})
    archivos.append(pdf("lista"))
    asignaciones.append({"documento_codigo": None})   # documento adicional
    archivos.append(pdf("carta-del-capitan"))

    r = await enviar(cliente, e.nav_a1, cabecera("F3-DESEMBARQUE", pid, tripulantes=tripulantes, asignaciones=asignaciones), archivos)
    assert r.status_code == 400 and "Formulario No. 6" in r.json()["detail"] and "Raúl" in r.json()["detail"]

    asignaciones.append({"documento_codigo": "DOC-FORM6-CUSTODIA", "indice_tripulante": 1})
    archivos.append(pdf("custodia"))
    r = await enviar(cliente, e.nav_a1, cabecera("F3-DESEMBARQUE", pid, tripulantes=tripulantes, asignaciones=asignaciones), archivos)
    assert r.status_code == 201, r.text
    s = r.json()
    sid = s["id"]
    assert s["estado"] == "review" and s["numero"] == f"AM-{HOY.year}-{sid:06d}"
    assert s["agencia_id"] == e.agencia_a["id"] and s["agencia_nombre"] == e.agencia_a["nombre"]
    assert len(s["checklist"]) == 8 and all(c["cubierta"] for c in s["checklist"])
    assert len(s["documentos"]) == 9
    assert [d["nombre_original"] for d in s["documentos"] if d["documento_id"] is None] == ["carta-del-capitan.pdf"]
    assert s["tiene_nacionalidad_restringida"] and s["tripulantes"][1]["nacionalidad_restringida"]
    assert s["bandera_nombre"] == "Panamá" and s["imo"] == "9074729"
    carpeta = STORAGE / f"solicitud-{sid}"
    assert carpeta.is_dir() and len(list(carpeta.iterdir())) == 9
    assert not list(STORAGE.glob("tmp-*"))

    # ── Acceso por agencia y por rol ──
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.nav_a2.headers)
    assert r.status_code == 200, "otro usuario de la misma agencia la ve"
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.nav_b.headers)
    assert r.status_code == 403, "otra agencia no la ve"
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.puerto_a.headers)
    assert r.status_code == 403, "el puerto no la ve antes de aprobarse"
    r = await cliente.get("/solicitudes/agencia", headers=e.nav_a2.headers)
    assert sid in [x["id"] for x in r.json()["items"]]
    r = await cliente.get("/solicitudes/agencia", headers=e.nav_b.headers)
    assert sid not in [x["id"] for x in r.json()["items"]]
    r = await cliente.get("/solicitudes/revision", headers=e.nav_a1.headers)
    assert r.status_code == 403
    r = await cliente.get("/solicitudes/revision", params={"estado": "review", "por_pagina": 100}, headers=e.revisor.headers)
    assert sid in [x["id"] for x in r.json()["items"]]

    # ── Revisión ──
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e.revisor.headers)
    assert r.status_code == 409 and "impedimentos" in r.json()["detail"]
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=cuerpo_impedimentos(s, comentario="Revisado"),
                           headers=e.revisor_a.headers)
    assert r.status_code == 403, "un revisor de la misma agencia no la revisa"
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.revisor_a.headers)
    assert r.json()["acciones"]["conflicto_revision"] and not r.json()["acciones"]["revisar"]

    await verificar_impedimentos(cliente, e.revisor, sid)
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.nav_a1.headers)
    vista = r.json()
    assert vista["comentario_impedimentos"] is None and not vista["impedimentos_verificados"]
    assert all(ev["tipo"] != "impedimentos" for ev in vista["eventos"]), "la agencia no ve la verificación interna"

    r = await cliente.post(f"/solicitudes/{sid}/devolver", json={"motivo": "La libreta de Raúl está ilegible"}, headers=e.revisor.headers)
    assert r.status_code == 200 and r.json()["estado"] == "returned" and r.json()["plazo_correccion"]
    r = await cliente.post(f"/solicitudes/{sid}/devolver", json={"motivo": "otra vez"}, headers=e.revisor.headers)
    assert r.status_code == 409

    # ── Corrige OTRO usuario de la agencia: quita a Juan, reemplaza la libreta de Raúl ──
    detalle = (await cliente.get(f"/solicitudes/{sid}", headers=e.nav_a2.headers)).json()
    assert detalle["acciones"]["corregir"]
    raul = detalle["tripulantes"][1]
    conservados = [
        d["id"] for d in detalle["documentos"]
        if (d["tripulante_id"] == raul["id"] and d["documento_codigo"] != "DOC-LIBRETA-MARINO")
        or d["tripulante_id"] is None
    ]
    ficha = tripulante("Raúl", "CUB", pasaporte=raul["pasaporte"], libreta_marino=raul["libreta_marino"])
    ficha["id"] = raul["id"]
    datos = cabecera(None, pid, tripulantes=[ficha], documentos_conservados=conservados,
                     asignaciones=[{"documento_codigo": "DOC-LIBRETA-MARINO", "indice_tripulante": 0}])
    r = await enviar(cliente, e.nav_b, datos, [pdf("libreta-nueva")], metodo="PUT", ruta=f"/solicitudes/{sid}")
    assert r.status_code == 403, "otra agencia no corrige"
    r = await enviar(cliente, e.nav_a2, datos, [pdf("libreta-nueva")], metodo="PUT", ruta=f"/solicitudes/{sid}")
    assert r.status_code == 200, r.text
    corregida = r.json()
    assert corregida["estado"] == "review" and corregida["cantidad_tripulantes"] == 1
    assert not corregida["impedimentos_verificados"]
    assert len(corregida["documentos"]) == 6 and all(c["cubierta"] for c in corregida["checklist"])
    assert [ev["tipo"] for ev in corregida["eventos"]] == ["creada", "devuelta", "corregida"]
    r = await cliente.get(f"/solicitudes/{sid}", headers=e.revisor.headers)
    assert [ev["tipo"] for ev in r.json()["eventos"]] == ["creada", "impedimentos", "devuelta", "corregida"]
    assert len(list(carpeta.iterdir())) == 6, "en disco quedan solo los documentos vigentes"

    # ── Aprobación, PDF y QR ──
    await verificar_impedimentos(cliente, e.revisor, sid)
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={"observacion": "Presentar custodia en el muelle"}, headers=e.revisor.headers)
    assert r.status_code == 200 and r.json()["estado"] == "approved" and r.json()["vigente_hasta"]
    assert r.json()["aprobada_por"] == "Revisor Prueba"

    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e.nav_a2.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and r.headers["content-type"] == "application/pdf"
    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e.nav_b.headers)
    assert r.status_code == 403

    async with SesionLocal() as sesion:
        codigo = (await sesion.execute(select(Solicitud.codigo_verificacion).where(Solicitud.id == sid))).scalar_one()
    r = await cliente.get(f"/verificacion/{codigo}")
    assert r.status_code == 200 and r.json()["valida"] and r.json()["numero"] == s["numero"]
    assert r.json()["tripulantes"][0]["pasaporte"].startswith("•")
    r = await cliente.get("/verificacion/codigo-que-no-existe")
    assert r.status_code == 404

    # ── Puesto de control ──
    r = await cliente.get("/solicitudes/puerto", headers=e.puerto_a.headers)
    assert sid in [x["id"] for x in r.json()["items"]]
    r = await cliente.get("/solicitudes/puerto", headers=e.puerto_b.headers)
    assert sid not in [x["id"] for x in r.json()["items"]]
    r = await cliente.post(f"/solicitudes/{sid}/finalizar", json={"comentario": "intento"}, headers=e.puerto_b.headers)
    assert r.status_code == 403
    r = await cliente.post(f"/solicitudes/{sid}/finalizar",
                           json={"comentario": "Desembarque realizado sin novedad", "puesto_finalizacion_id": 999999},
                           headers=e.puerto_a.headers)
    assert r.status_code == 400, "el puesto de finalización tiene que existir"
    r = await cliente.post(f"/solicitudes/{sid}/finalizar",
                           json={"comentario": "Desembarque realizado sin novedad", "puesto_finalizacion_id": e.puesto_b["id"]},
                           headers=e.puerto_a.headers)
    assert r.status_code == 200 and r.json()["estado"] == "finalized" and r.json()["finalizada_por"] == "Puerto Prueba"
    assert r.json()["puesto_finalizacion_nombre"] == e.puesto_b["nombre"], "terminó en otro puerto"
    r = await cliente.get(f"/verificacion/{codigo}")
    assert r.json()["estado"] == "finalized" and r.json()["valida"]
    assert r.json()["puesto_finalizacion_nombre"] == e.puesto_b["nombre"]
    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e.nav_a1.headers)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"

    # ── Lo que ve la agencia: estados y motivos, nada interno del SNM ──
    vista = (await cliente.get(f"/solicitudes/{sid}", headers=e.nav_a1.headers)).json()
    tipos = [ev["tipo"] for ev in vista["eventos"]]
    assert tipos == ["creada", "devuelta", "corregida", "aprobada", "finalizada"]
    por_tipo = {ev["tipo"]: ev for ev in vista["eventos"]}
    assert por_tipo["devuelta"]["comentario"] == "La libreta de Raúl está ilegible", "el motivo de devolución sí se ve"
    assert por_tipo["aprobada"]["comentario"] is None and por_tipo["finalizada"]["comentario"] is None
    assert por_tipo["aprobada"]["usuario_nombre"] == "UCVMM"
    assert por_tipo["finalizada"]["usuario_nombre"] == "Puesto de control"
    assert por_tipo["devuelta"]["usuario_nombre"] == "UCVMM"
    assert vista["observacion_aprobacion"] is None and vista["comentario_finalizacion"] is None
    assert vista["aprobada_por"] is None and vista["finalizada_por"] is None
    assert all(t["con_impedimento"] is None for t in vista["tripulantes"])
    assert vista["puesto_finalizacion_nombre"] == e.puesto_b["nombre"]
    interna = (await cliente.get(f"/solicitudes/{sid}", headers=e.revisor.headers)).json()
    assert "impedimentos" in [ev["tipo"] for ev in interna["eventos"]]
    assert interna["observacion_aprobacion"] == "Presentar custodia en el muelle"
    assert all(t["con_impedimento"] is False for t in interna["tripulantes"])


# ── Impedimentos por tripulante y solo PDF ───────────────────────────────────

async def test_impedimentos_por_tripulante(cliente, escenario: Escenario):
    e = escenario
    datos = cabecera("F3-CAMBIO-NAVE", e.puesto_a["id"], tripulantes=[tripulante("Luis"), tripulante("Marta", "COL")],
                     asignaciones=[{"documento_codigo": c, "indice_tripulante": i}
                                   for i in range(2) for c in ("DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE")])
    r = await enviar(cliente, e.nav_a1, datos, [pdf(f"d{i}") for i in range(4)])
    assert r.status_code == 201, r.text
    s = r.json()
    sid = s["id"]

    incompleto = cuerpo_impedimentos(s)
    incompleto["tripulantes"] = incompleto["tripulantes"][:1]
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=incompleto, headers=e.revisor.headers)
    assert r.status_code == 400, "hay que verificar a cada tripulante"
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e.revisor.headers)
    assert r.status_code == 409

    sin_comentario = cuerpo_impedimentos(s)
    del sin_comentario["comentario"]
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=sin_comentario, headers=e.revisor.headers)
    assert r.status_code == 200, "el comentario de la acción tomada es opcional"
    assert r.json()["comentario_impedimentos"] is None
    assert r.json()["eventos"][-1]["comentario"] == "Sin impedimentos (2 tripulantes)."
    eventos = len(r.json()["eventos"])
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=sin_comentario, headers=e.revisor.headers)
    assert r.status_code == 409, "repetir la misma verificación no suma otra entrada al historial"
    vista = (await cliente.get(f"/solicitudes/{sid}", headers=e.revisor.headers)).json()
    assert len(vista["eventos"]) == eventos

    # Ya registrada: cambiarla es una corrección y exige motivo
    correccion = cuerpo_impedimentos(s, con_impedimento={"Marta"}, comentario=None)
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=correccion, headers=e.revisor.headers)
    assert r.status_code == 400 and "motivo de la corrección" in r.json()["detail"]
    correccion["motivo_correccion"] = "Revisé de nuevo en SIMPLUS"
    r = await cliente.post(f"/solicitudes/{sid}/impedimentos", json=correccion, headers=e.revisor.headers)
    assert r.status_code == 200, r.text
    revisada = r.json()
    assert {t["nombre"]: t["con_impedimento"] for t in revisada["tripulantes"]} == {"Luis": False, "Marta": True}
    assert revisada["eventos"][-1]["tipo"] == "impedimentos_corregidos"
    assert revisada["eventos"][-1]["comentario"] == (
        "Marta Pérez pasa de sin impedimento a con impedimento. Motivo: Revisé de nuevo en SIMPLUS.")
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e.revisor.headers)
    assert r.status_code == 200, "con impedimento se aprueba igual: se informa a Operaciones"
    vista = (await cliente.get(f"/solicitudes/{sid}", headers=e.nav_a1.headers)).json()
    assert all(t["con_impedimento"] is None for t in vista["tripulantes"]), "la agencia no ve el resultado"
    assert not {"impedimentos", "impedimentos_corregidos"} & {ev["tipo"] for ev in vista["eventos"]}, \
        "ni la verificación ni su corrección"


async def test_solo_se_aceptan_pdf(cliente, escenario: Escenario):
    e = escenario
    datos = cabecera("F3-CAMBIO-NAVE", e.puesto_a["id"], tripulantes=[tripulante("Luis")], asignaciones=[
        {"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
        {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
    ])
    imagen = ("visa.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")
    r = await enviar(cliente, e.nav_a1, datos, [imagen, pdf("pasaporte")])
    assert r.status_code == 415 and "PDF" in r.json()["detail"]
    disfrazado = ("visa.pdf", b"MZ esto no es un pdf", "application/pdf")
    r = await enviar(cliente, e.nav_a1, datos, [disfrazado, pdf("pasaporte")])
    assert r.status_code == 415 and "no es un PDF válido" in r.json()["detail"]


# ── Documentos del expediente ────────────────────────────────────────────────

async def test_documentos_requieren_sesion_y_acceso(cliente, escenario: Escenario, admin):
    e = escenario
    s = await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    sid, doc = s["id"], s["documentos"][0]
    ruta = f"/solicitudes/{sid}/documentos/{doc['id']}"

    r = await cliente.get(ruta)
    assert r.status_code == 401, "sin sesión no hay documentos"
    r = await cliente.get(ruta, headers=e.nav_b.headers)
    assert r.status_code == 403
    r = await cliente.get(ruta, headers=e.puerto_a.headers)
    assert r.status_code == 403, "el puerto solo ve documentos de autorizaciones aprobadas"
    r = await cliente.get(f"/solicitudes/{sid}/documentos/999999", headers=e.nav_a2.headers)
    assert r.status_code == 404

    r = await cliente.get(ruta, headers=e.nav_a2.headers)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert r.headers["content-disposition"].startswith("inline")
    r = await cliente.get(ruta, params={"descargar": True}, headers=e.revisor.headers)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment")

    r = await cliente.get("/admin/bitacora", params={"accion": "DOCUMENTO_VISTO", "usuario": e.nav_a2.username}, headers=admin.headers)
    assert r.json()["total"] == 1 and r.json()["items"][0]["detalle"]["documento_id"] == doc["id"]
    r = await cliente.get("/admin/bitacora", params={"accion": "DOCUMENTO_DESCARGADO", "usuario": e.revisor.username}, headers=admin.headers)
    assert r.json()["total"] >= 1


async def test_rutas_del_storage_ya_no_existen(cliente, escenario: Escenario):
    for ruta in ("/transfers", "/transfers/public/abc", "/transfers/download/abc"):
        r = await cliente.get(ruta, headers=escenario.nav_a1.headers)
        assert r.status_code == 404, ruta


# ── Separación de funciones ──────────────────────────────────────────────────

async def test_nadie_revisa_lo_que_creo(cliente, escenario: Escenario):
    e = escenario
    admin_b = await crear_actor("Administrador", agencia_id=e.agencia_b["id"], prefijo="adminb")
    s = await solicitud_simple(cliente, admin_b, e.puesto_a["id"])
    sid = s["id"]

    assert s["acciones"]["conflicto_revision"] and not s["acciones"]["revisar"]
    for accion, cuerpo in (
        ("impedimentos", cuerpo_impedimentos(s, comentario="Autorrevisión")),
        ("aprobar", {}), ("devolver", {"motivo": "Autodevolución"}), ("negar", {"motivo": "Autonegación"}),
    ):
        r = await cliente.post(f"/solicitudes/{sid}/{accion}", json=cuerpo, headers=admin_b.headers)
        assert r.status_code == 403, accion

    await verificar_impedimentos(cliente, e.revisor, sid)
    r = await cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e.revisor.headers)
    assert r.status_code == 200, "otro revisor sí la aprueba"


async def test_negar(cliente, escenario: Escenario):
    e = escenario
    datos = cabecera("F3-TECNICO", e.puesto_a["id"], tripulantes=[tripulante("Ana", "ESP", rango="tecnico")], asignaciones=[
        {"documento_codigo": "DOC-FORM7-RESPONSABILIDAD", "indice_tripulante": 0},
        {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
    ])
    r = await enviar(cliente, e.nav_b, datos, [pdf("carta"), pdf("pasaporte")])
    assert r.status_code == 201, "un técnico no porta seamanbook"
    sid = r.json()["id"]
    r = await cliente.post(f"/solicitudes/{sid}/negar", json={"motivo": "Documentación falsa"}, headers=e.revisor.headers)
    assert r.status_code == 200 and r.json()["estado"] == "denied" and r.json()["motivo_negacion"] == "Documentación falsa"
    r = await cliente.get(f"/solicitudes/{sid}/autorizacion.pdf", headers=e.nav_b.headers)
    assert r.status_code == 409


# ── Concurrencia ─────────────────────────────────────────────────────────────

async def test_aprobar_y_negar_a_la_vez(cliente, escenario: Escenario, monkeypatch):
    """El bloqueo de fila deja pasar una sola transición. Una pausa entre leer
    la solicitud y escribirla asegura que las dos peticiones se crucen: sin el
    bloqueo, las dos leerían "en revisión" y las dos responderían 200."""
    e = escenario
    s = await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    sid = s["id"]
    await verificar_impedimentos(cliente, e.revisor, sid)

    original = ServicioSolicitud._para_revision

    async def con_pausa(self, ctx, solicitud_id):
        solicitud = await original(self, ctx, solicitud_id)
        await asyncio.sleep(0.3)
        return solicitud

    monkeypatch.setattr(ServicioSolicitud, "_para_revision", con_pausa)
    aprobar, negar = await asyncio.gather(
        cliente.post(f"/solicitudes/{sid}/aprobar", json={}, headers=e.revisor.headers),
        cliente.post(f"/solicitudes/{sid}/negar", json={"motivo": "Negada en paralelo"}, headers=e.revisor.headers),
    )
    assert sorted([aprobar.status_code, negar.status_code]) == [200, 409]
    ganador = aprobar if aprobar.status_code == 200 else negar
    final = (await cliente.get(f"/solicitudes/{sid}", headers=e.revisor.headers)).json()
    assert final["estado"] == ganador.json()["estado"]
    assert [ev["tipo"] for ev in final["eventos"]].count("aprobada") + [ev["tipo"] for ev in final["eventos"]].count("negada") == 1


# ── Vencimientos ─────────────────────────────────────────────────────────────

async def test_vencimientos(cliente, escenario: Escenario):
    e = escenario
    aprobada = await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    devuelta = await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    await verificar_impedimentos(cliente, e.revisor, aprobada["id"])
    assert (await cliente.post(f"/solicitudes/{aprobada['id']}/aprobar", json={}, headers=e.revisor.headers)).status_code == 200
    assert (await cliente.post(f"/solicitudes/{devuelta['id']}/devolver", json={"motivo": "Visa ilegible"}, headers=e.revisor.headers)).status_code == 200

    async with SesionLocal() as sesion:
        await sesion.execute(update(Solicitud).where(Solicitud.id == aprobada["id"])
                             .values(vigente_hasta=text("now() - interval '1 minute'")))
        await sesion.execute(update(Solicitud).where(Solicitud.id == devuelta["id"])
                             .values(plazo_correccion=text("now() - interval '1 minute'")))
        await sesion.commit()

    r = await cliente.post(f"/solicitudes/{aprobada['id']}/finalizar", json={"comentario": "tarde"}, headers=e.puerto_a.headers)
    assert r.status_code == 409, "no se finaliza una autorización vencida"
    r = await enviar(cliente, e.nav_a1, {}, [], metodo="PUT", ruta=f"/solicitudes/{devuelta['id']}")
    assert r.status_code in (409, 422)

    assert await expirar_solicitudes() == 2
    for sid in (aprobada["id"], devuelta["id"]):
        detalle = (await cliente.get(f"/solicitudes/{sid}", headers=e.revisor.headers)).json()
        assert detalle["estado"] == "expired" and detalle["expirada_en"]
        assert detalle["eventos"][-1]["usuario_nombre"] == "Sistema"
    assert await expirar_solicitudes() == 0, "una segunda vuelta no repite"


# ── Bandejas ─────────────────────────────────────────────────────────────────

async def test_bandejas_paginadas(cliente, escenario: Escenario, admin):
    e = escenario
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Paginada {secrets.token_hex(2)}"}, headers=admin.headers)
    agencia = r.json()
    naviera = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    creadas = [await solicitud_simple(cliente, naviera, e.puesto_b["id"]) for _ in range(7)]

    r = await cliente.get("/solicitudes/agencia", params={"por_pagina": 5}, headers=naviera.headers)
    pagina = r.json()
    assert pagina["total"] == 7 and len(pagina["items"]) == 5 and pagina["conteos"] == {"review": 7}
    assert [x["id"] for x in pagina["items"]] == [s["id"] for s in reversed(creadas)][:5], "lo más reciente primero"
    r = await cliente.get("/solicitudes/agencia", params={"por_pagina": 5, "pagina": 2}, headers=naviera.headers)
    assert len(r.json()["items"]) == 2

    r = await cliente.get("/solicitudes/agencia", params={"texto": creadas[3]["numero"]}, headers=naviera.headers)
    assert [x["id"] for x in r.json()["items"]] == [creadas[3]["id"]]
    r = await cliente.get("/solicitudes/agencia", params={"estado": "approved"}, headers=naviera.headers)
    assert r.json()["total"] == 0 and r.json()["conteos"] == {"review": 7}

    r = await cliente.get("/solicitudes/revision", params={"estado": "review", "texto": agencia["nombre"], "por_pagina": 100},
                          headers=e.revisor.headers)
    assert [x["id"] for x in r.json()["items"]] == [s["id"] for s in creadas], "la cola de UCVMM va por orden de llegada"

    r = await cliente.get("/solicitudes/agencia", params={"por_pagina": 500}, headers=naviera.headers)
    assert r.status_code == 422


# ── Estadísticas, bitácora y protecciones del admin ──────────────────────────

async def test_estadisticas_y_uso(cliente, escenario: Escenario, admin):
    e = escenario
    antes = (await cliente.get("/solicitudes/estadisticas", headers=e.revisor.headers)).json()
    await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    r = await cliente.get("/solicitudes/estadisticas", headers=e.revisor.headers)
    est = r.json()
    assert r.status_code == 200 and len(est["por_mes"]) == 6
    assert est["recibidas"] == antes["recibidas"] + 1 == sum(est["por_estado"].values())
    assert est["por_mes"][-1]["recibidas"] == antes["por_mes"][-1]["recibidas"] + 1
    assert est["aprobadas"] >= est["finalizadas"]
    r = await cliente.get("/solicitudes/estadisticas", headers=e.nav_a1.headers)
    assert r.status_code == 403

    r = await cliente.get("/admin/stats", headers=admin.headers)
    uso = r.json()
    assert r.status_code == 200 and uso["documentos"] > 0 and uso["almacenamiento_bytes"] > 0
    assert uso["agencias"] >= 2 and uso["top_agencias"]

    r = await cliente.get("/admin/bitacora", params={"accion": "SOLICITUD_APROBADA"}, headers=admin.headers)
    assert r.json()["total"] >= 1
    r = await cliente.get("/admin/bitacora", params={"accion": "AGENCIA_CREADA"}, headers=admin.headers)
    assert r.json()["total"] >= 2
    r = await cliente.get("/admin/bitacora", headers=e.revisor.headers)
    assert r.status_code == 403


async def test_protecciones_del_admin(cliente, escenario: Escenario, admin, sysadmin):
    e = escenario
    await solicitud_simple(cliente, e.nav_a1, e.puesto_a["id"])
    r = await cliente.delete(f"/admin/usuarios/{e.nav_a1.id}", headers=sysadmin.headers)
    assert r.status_code == 409, "no se elimina un usuario con solicitudes"
    r = await cliente.delete(f"/admin/puestos/{e.puesto_a['id']}", headers=admin.headers)
    assert r.status_code == 409
    r = await cliente.delete(f"/admin/agencias/{e.agencia_a['id']}", headers=admin.headers)
    assert r.status_code == 409

    r = await cliente.post("/admin/puestos", json={"nombre": f"Puesto Temporal {secrets.token_hex(2)}"}, headers=admin.headers)
    r = await cliente.delete(f"/admin/puestos/{r.json()['id']}", headers=admin.headers)
    assert r.status_code == 204

    # Agencia inactiva: sus usuarios ya no entran (ni, por lo tanto, envían)
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Inactiva {secrets.token_hex(2)}"}, headers=admin.headers)
    agencia = r.json()
    naviera = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    r = await cliente.patch(f"/admin/agencias/{agencia['id']}", json={"activo": False}, headers=admin.headers)
    assert r.status_code == 200 and not r.json()["activo"]
    datos = cabecera("F3-CAMBIO-NAVE", e.puesto_a["id"], tripulantes=[tripulante("Luis")])
    r = await enviar(cliente, naviera, datos, [])
    assert r.status_code == 401 and "desactivada" in r.json()["detail"]

    r = await cliente.delete(f"/admin/agencias/{agencia['id']}", headers=admin.headers)
    assert r.status_code == 204, "una agencia sin solicitudes sí se elimina"
    r = await cliente.get("/auth/me", headers=naviera.headers)
    assert r.json()["agencia_id"] is None, "sus usuarios quedan sin agencia"
