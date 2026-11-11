"""Consulta histórica (2026-11-11): las solicitudes que ve el personal del SNM, de
cualquier año, con filtros que las bandejas no tienen, y su exportación a Excel.
El alcance es el mismo que el del expediente (`puede_ver`): cada uno, lo suyo."""
import io
import re
import secrets
import zipfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import insert, select

from app.core.horario import ZONA_PANAMA
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl, usuarios_puestos
from app.domain.models.solicitud import Solicitud, TripulanteSolicitud
from app.domain.models.tramite import TipoTramite
from app.infrastructure.database import SesionLocal
from conftest import ATLANTICO, PACIFICO, crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

RUTA = "/solicitudes/historico"


def _panama(*partes: int) -> datetime:
    return datetime(*partes, tzinfo=ZONA_PANAMA)


def _ultimo_sabado() -> date:
    dia = datetime.now(ZONA_PANAMA).date() - timedelta(days=1)
    while dia.weekday() != 5:
        dia -= timedelta(days=1)
    return dia


@pytest.fixture(scope="module")
async def historia(cliente):
    """Cinco solicitudes de varios años, dos sectores, dos agencias y un puesto ya
    desactivado. El sufijo, en el título, las separa de las de otras pruebas."""
    sufijo = secrets.token_hex(3)
    pacifico, atlantico = await id_sector(PACIFICO), await id_sector(ATLANTICO)
    async with SesionLocal() as s:
        agencias = [AgenciaNaviera(nombre=f"Agencia Historia {sufijo} {n}") for n in (1, 2)]
        puesto_p = PuestoControl(nombre=f"Puesto Pacífico {sufijo}", sector_id=pacifico)
        puesto_a = PuestoControl(nombre=f"Puesto Atlántico {sufijo}", sector_id=atlantico)
        puesto_viejo = PuestoControl(nombre=f"Puesto Cerrado {sufijo}", sector_id=pacifico, activo=False)
        s.add_all([*agencias, puesto_p, puesto_a, puesto_viejo])
        await s.commit()
        tipos = list((await s.execute(select(TipoTramite.id).order_by(TipoTramite.id).limit(2))).scalars())
    naviera = await crear_actor("Naviera", agencia_id=agencias[0].id, prefijo="naviera")
    async with SesionLocal() as s:
        sabado = _ultimo_sabado()
        hoy = datetime.now(ZONA_PANAMA).date()
        # clave: (agencia, puesto, trámite, estado, enviada, operación, aprobada, pasajero, pasaporte)
        datos = {
            "marzo25":  (0, puesto_p, 0, "finalized", _panama(2025, 3, 10, 9), date(2025, 3, 12),
                         _panama(2025, 3, 11, 10), ("Ana Maria", "Rios"), "PA%123"),
            "julio25":  (1, puesto_a, 1, "denied", _panama(2025, 7, 1, 9), date(2025, 7, 5),
                         None, ("Beto", "Cruz"), "XB777"),
            "revision": (0, puesto_a, 0, "review", datetime.now(ZONA_PANAMA) - timedelta(days=1), hoy + timedelta(days=3),
                         None, ("Carla", "Diaz"), "CD100"),
            "fuera":    (1, puesto_p, 1, "approved", datetime.combine(sabado, time(9), ZONA_PANAMA), hoy,
                         datetime.combine(sabado, time(10), ZONA_PANAMA), ("Dario", "Paz"), "DP200"),
            "cerrado":  (0, puesto_viejo, 0, "finalized", _panama(2024, 5, 2, 9), date(2024, 5, 3),
                         _panama(2024, 5, 2, 11), ("Eva", "Luna"), "EL300"),
        }
        ids: dict[str, int] = {}
        for i, (clave, (ag, puesto, tipo, estado, enviada, operacion, aprobada, (nombre, apellido), pasaporte)) \
                in enumerate(datos.items()):
            solicitud = Solicitud(
                numero=f"HX-{sufijo}-{i}", agencia_id=agencias[ag].id, agencia_nombre=agencias[ag].nombre,
                creada_por_id=naviera.id, tipo_tramite_id=tipos[tipo], puesto_control_id=puesto.id,
                puesto_nombre=puesto.nombre, titulo=f"Historia {sufijo}", nombre_buque=f"BUQUE {clave.upper()}",
                fecha_operacion=operacion, cantidad_tripulantes=1, estado=estado, enviada_en=enviada,
                aprobada_en=aprobada, costo_fuera_de_horario=Decimal("20.00") if clave == "fuera" else None,
                finalizada_en=aprobada + timedelta(days=1) if estado == "finalized" else None,
            )
            s.add(solicitud)
            await s.flush()
            s.add(TripulanteSolicitud(
                solicitud_id=solicitud.id, orden=0, nombre=nombre, apellido=apellido, fecha_nacimiento=date(1990, 1, 1),
                pais_nacimiento="PAN", nacionalidad="PAN", sexo="F", pasaporte=pasaporte,
                pasaporte_expira=date(2035, 1, 1), rango="marino", ocupacion="Marino",
            ))
            ids[clave] = solicitud.id
        await s.commit()
    return {
        "sufijo": sufijo, "ids": ids, "naviera": naviera, "tipos": tipos,
        "agencias": [a.id for a in agencias], "puesto_p": puesto_p.id, "puesto_a": puesto_a.id,
        "puesto_viejo": puesto_viejo.id,
    }


async def _ids(cliente, actor, **filtros) -> list[int]:
    r = await cliente.get(RUTA, params={"por_pagina": 100, **filtros}, headers=actor.headers)
    assert r.status_code == 200, r.text
    return [x["id"] for x in r.json()["items"]]


async def test_de_cualquier_anio_y_por_fecha(cliente, admin, historia):
    ids, texto = historia["ids"], historia["sufijo"]
    # Todas, de la más reciente a la más antigua (por la fecha de envío).
    assert await _ids(cliente, admin, texto=texto) == [ids[c] for c in ("revision", "fuera", "julio25", "marzo25", "cerrado")]
    # Un año entero de otro tiempo: las de 2025.
    assert await _ids(cliente, admin, texto=texto, desde="2025-01-01", hasta="2025-12-31") == [ids["julio25"], ids["marzo25"]]
    # Por la fecha de la operación: la del 12 de marzo de 2025 (se envió el 10).
    assert await _ids(cliente, admin, texto=texto, fecha="operacion", desde="2025-03-12", hasta="2025-03-12") \
        == [ids["marzo25"]]
    assert await _ids(cliente, admin, texto=texto, desde="2025-03-12", hasta="2025-03-12") == []
    r = await cliente.get(RUTA, params={"desde": "2025-12-31", "hasta": "2025-01-01"}, headers=admin.headers)
    assert r.status_code == 422, "«hasta» antes de «desde»"


async def test_filtros(cliente, admin, historia):
    ids, texto = historia["ids"], historia["sufijo"]
    assert set(await _ids(cliente, admin, texto=texto, agencia_id=historia["agencias"][1])) == {ids["julio25"], ids["fuera"]}
    assert set(await _ids(cliente, admin, texto=texto, puesto_id=historia["puesto_p"])) == {ids["marzo25"], ids["fuera"]}
    assert set(await _ids(cliente, admin, texto=texto, tipo_tramite_id=historia["tipos"][1])) == {ids["julio25"], ids["fuera"]}
    assert await _ids(cliente, admin, texto=texto, estado="denied") == [ids["julio25"]]
    assert await _ids(cliente, admin, texto=texto, fuera_de_horario="true") == [ids["fuera"]]
    # Pasajero: nombre, apellido, los dos juntos (sin distinguir mayúsculas) o pasaporte.
    for buscado in ("ana maria", "RIOS", "Ana Maria Rios", "pa%1"):
        assert await _ids(cliente, admin, texto=texto, pasajero=buscado) == [ids["marzo25"]], buscado
    assert await _ids(cliente, admin, texto=texto, pasajero="P%3") == [], "«%» se busca tal cual, no como comodín"
    # Los conteos por estado siguen a los filtros (sin el de estado), para las pestañas.
    r = await cliente.get(RUTA, params={"texto": texto, "estado": "finalized"}, headers=admin.headers)
    assert r.json()["conteos"] == {"finalized": 2, "denied": 1, "review": 1, "approved": 1}
    # El costo y el fuera del horario van en cada fila, como en las bandejas.
    fila = next(x for x in r.json()["items"] if x["id"] == ids["marzo25"])
    assert fila["fuera_de_horario"] is False and fila["costo_fuera_de_horario"] is None


async def test_cada_uno_ve_lo_suyo(cliente, admin, sysadmin, historia):
    ids, texto = historia["ids"], historia["sufijo"]
    atlantico = await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,))
    assert set(await _ids(cliente, atlantico, texto=texto)) == {ids["julio25"], ids["revision"]}
    sup_pacifico = await crear_actor("Supervisor de sector", prefijo="supervisor", sectores=(PACIFICO,))
    assert set(await _ids(cliente, sup_pacifico, texto=texto)) == {ids["marzo25"], ids["fuera"], ids["cerrado"]}
    general = await crear_actor("Supervisor general", prefijo="general")
    assert len(await _ids(cliente, general, texto=texto)) == 5
    # El puesto de control: las de sus puestos, desde que se aprueban.
    puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    async with SesionLocal() as s:
        await s.execute(insert(usuarios_puestos).values(usuario_id=puesto.id, puesto_id=historia["puesto_p"]))
        await s.execute(insert(usuarios_puestos).values(usuario_id=puesto.id, puesto_id=historia["puesto_a"]))
        await s.commit()
    assert set(await _ids(cliente, puesto, texto=texto)) == {ids["marzo25"], ids["fuera"]}, "sin la denegada ni la en revisión"
    # Lo que ven aquí, lo pueden abrir.
    for actor in (atlantico, sup_pacifico, puesto):
        for sid in await _ids(cliente, actor, texto=texto):
            assert (await cliente.get(f"/solicitudes/{sid}", headers=actor.headers)).status_code == 200
    # La agencia usa su bandeja; el SysAdmin no trabaja solicitudes.
    for actor in (historia["naviera"], sysadmin):
        assert (await cliente.get(RUTA, headers=actor.headers)).status_code == 403
        assert (await cliente.get(f"{RUTA}/opciones", headers=actor.headers)).status_code == 403
        assert (await cliente.get(f"{RUTA}/exportar", headers=actor.headers)).status_code == 403
    sin_sector = await crear_actor("UCVMM", prefijo="revisor", sectores=())
    assert (await cliente.get(RUTA, headers=sin_sector.headers)).status_code == 409


async def test_opciones_de_los_filtros(cliente, admin, historia):
    r = await cliente.get(f"{RUTA}/opciones", headers=admin.headers)
    assert r.status_code == 200
    opciones = r.json()
    puestos = {p["id"]: p for p in opciones["puestos"]}
    assert puestos[historia["puesto_viejo"]]["activo"] is False, "también los desactivados: hay solicitudes viejas"
    assert set(historia["agencias"]) <= {a["id"] for a in opciones["agencias"]}
    assert set(historia["tipos"]) <= {t["id"] for t in opciones["tramites"]}
    atlantico = await crear_actor("UCVMM", prefijo="revisor", sectores=(ATLANTICO,))
    puestos = {p["id"] for p in (await cliente.get(f"{RUTA}/opciones", headers=atlantico.headers)).json()["puestos"]}
    assert historia["puesto_a"] in puestos and historia["puesto_p"] not in puestos, "los puestos de su alcance"


def _textos(contenido: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        return z.read("xl/sharedStrings.xml").decode()


async def test_exportar_a_excel(cliente, admin, historia, monkeypatch):
    from app.domain.services import solicitud_service

    ids, texto = historia["ids"], historia["sufijo"]
    r = await cliente.get(f"{RUTA}/exportar", params={"texto": texto, "desde": "2025-01-01"}, headers=admin.headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert re.fullmatch(r'attachment; filename="Consulta-historica-\d{4}-\d{2}-\d{2}\.xlsx"', r.headers["content-disposition"])
    textos = _textos(r.content)
    for esperado in ("Consulta histórica de solicitudes", "Uso interno del SNM", "Todos los sectores",
                     f"Texto: «{texto}»", "Enviadas: desde el 1 de enero de 2025", f"HX-{texto}-0", "Finalizada",
                     "Fuera del horario", "4 solicitudes"):
        assert esperado in textos, esperado
    assert f"HX-{texto}-4" not in textos, "la de 2024 queda fuera del rango"

    # Con más de las que caben, lo dice el archivo.
    monkeypatch.setattr(solicitud_service, "MAX_FILAS_EXPORTACION", 2)
    r = await cliente.get(f"{RUTA}/exportar", params={"texto": texto}, headers=admin.headers)
    textos = _textos(r.content)
    assert "Se exportaron las primeras 2 de 5 solicitudes" in textos
    assert f"HX-{texto}-2" in textos and f"HX-{texto}-4" not in textos, "las más recientes"
    assert ids


async def test_exportar_tiene_tope_por_cuenta(cliente, admin, monkeypatch):
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit._config, "LIMITE_EXPORTACIONES_POR_HORA", 1)
    monkeypatch.setattr(rate_limit.limiter, "enabled", True)
    rate_limit.limiter.reset()
    try:
        assert (await cliente.get(f"{RUTA}/exportar", params={"texto": "x"}, headers=admin.headers)).status_code == 200
        r = await cliente.get(f"{RUTA}/exportar", params={"texto": "x"}, headers=admin.headers)
        assert r.status_code == 429 and "Espera" in r.json()["detail"]
    finally:
        rate_limit.limiter.reset()
