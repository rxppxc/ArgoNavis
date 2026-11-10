"""Horario laboral: las autorizaciones aprobadas fuera de él, en las
estadísticas y en la insignia del expediente (reunión del 2026-10-30; desde el
2026-11-06 cuenta la aprobación de UCVMM, no la finalización, y las 15:00 en
punto son laborales). También la serie por día, mes y año."""
import secrets
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import DateTime, literal, select

from app.core.horario import ZONA_PANAMA, fuera_de_horario
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.models.solicitud import EventoSolicitud, Solicitud
from app.domain.models.tramite import TipoTramite
from app.domain.repositories.solicitud_repository import _fuera_de_horario
from app.domain.services.solicitud_service import _meses_antes, _periodos_mes, _serie
from app.infrastructure.database import SesionLocal
from conftest import crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _panama(*partes: int) -> datetime:
    return datetime(*partes, tzinfo=ZONA_PANAMA)


# Viernes 30/10/2026, sábado 31, domingo 1/11 y lunes 2/11, en hora de Panamá.
BORDES = [
    (_panama(2026, 10, 30, 6, 59, 59), True),
    (_panama(2026, 10, 30, 7, 0), False),
    (_panama(2026, 10, 30, 14, 59, 59), False),
    (_panama(2026, 10, 30, 15, 0), False),         # las 15:00 en punto todavía son laborales
    (_panama(2026, 10, 30, 15, 0, 59), False),
    (_panama(2026, 10, 30, 15, 1), True),          # desde las 15:01, fuera
    (_panama(2026, 10, 30, 22, 30), True),         # en UTC ya es sábado
    (_panama(2026, 10, 31, 10, 0), True),          # sábado
    (_panama(2026, 11, 1, 10, 0), True),           # domingo
    (_panama(2026, 11, 2, 7, 30), False),          # lunes
]


@pytest.mark.parametrize(("momento", "fuera"), BORDES, ids=[m.isoformat() for m, _ in BORDES])
async def test_la_regla_en_python_y_en_sql_coinciden(momento, fuera):
    assert fuera_de_horario(momento) is fuera
    en_utc = literal(momento.astimezone(timezone.utc), DateTime(timezone=True))
    async with SesionLocal() as s:
        assert (await s.execute(select(_fuera_de_horario(en_utc)))).scalar_one() is fuera


async def test_la_serie_se_agrupa_por_dia_mes_y_anio():
    assert _meses_antes(date(2026, 1, 15), 1) == date(2025, 12, 1)
    assert _meses_antes(date(2026, 1, 15), -1) == date(2026, 2, 1)
    assert _periodos_mes(date(2025, 11, 20), date(2026, 2, 3)) == [
        date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1),
    ]
    diaria = {date(2026, 10, 30): {"recibidas": 2}, date(2026, 11, 2): {"recibidas": 1, "aprobadas": 1}}
    meses = _serie(diaria, [date(2026, 10, 1), date(2026, 11, 1)], lambda d: f"{d.year:04d}-{d.month:02d}")
    assert [(m.periodo, m.recibidas, m.aprobadas) for m in meses] == [("2026-10", 2, 0), ("2026-11", 1, 1)]
    anios = _serie(diaria, [date(2026, 1, 1)], lambda d: f"{d.year:04d}")
    assert (anios[0].periodo, anios[0].recibidas, anios[0].finalizadas) == ("2026", 3, 0)


def _ultimo(dia_semana: int) -> date:
    """El último lunes (0) … domingo (6) antes de hoy, en Panamá."""
    dia = datetime.now(ZONA_PANAMA).date() - timedelta(days=1)
    while dia.weekday() != dia_semana:
        dia -= timedelta(days=1)
    return dia


async def test_estadisticas_e_insignia(cliente):
    sufijo = secrets.token_hex(3)
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia Horario {sufijo}")
        puesto = PuestoControl(nombre=f"Puesto Horario {sufijo}", sector_id=await id_sector())
        s.add_all([agencia, puesto])
        await s.commit()
    naviera = await crear_actor("Naviera", agencia_id=agencia.id, prefijo="naviera")

    sabado, miercoles = _ultimo(5), _ultimo(2)
    # (aprobada en, finalizada en): cuenta la aprobación; la finalización no.
    momentos = {
        "sabado":   (datetime.combine(sabado, time(10, 0), ZONA_PANAMA), None),                 # fuera, sin finalizar
        "tarde":    (datetime.combine(miercoles, time(15, 1), ZONA_PANAMA),                     # fuera
                     datetime.combine(miercoles + timedelta(days=1), time(10, 0), ZONA_PANAMA)),
        "en_punto": (datetime.combine(miercoles, time(15, 0, 30), ZONA_PANAMA), None),          # dentro
        "manana":   (datetime.combine(miercoles, time(10, 0), ZONA_PANAMA),                     # dentro, aunque
                     datetime.combine(sabado, time(20, 0), ZONA_PANAMA)),                       # se finalice fuera
    }
    fuera = {"sabado", "tarde"}
    antes = (await cliente.get("/solicitudes/estadisticas", headers=revisor.headers)).json()
    ids: dict[str, int] = {}
    async with SesionLocal() as s:
        tipo_id = (await s.execute(select(TipoTramite.id).limit(1))).scalar_one()
        for clave, (aprobada, finalizada) in momentos.items():
            solicitud = Solicitud(
                agencia_id=agencia.id, agencia_nombre=agencia.nombre, creada_por_id=naviera.id,
                tipo_tramite_id=tipo_id, puesto_control_id=puesto.id, puesto_nombre=puesto.nombre,
                titulo="Prueba de horario", fecha_operacion=aprobada.date(), cantidad_tripulantes=0,
                estado="finalized" if finalizada else "approved", enviada_en=aprobada - timedelta(days=1),
                aprobada_en=aprobada, vigente_hasta=aprobada + timedelta(days=30), finalizada_en=finalizada,
                puesto_finalizacion_id=puesto.id if finalizada else None,
                puesto_finalizacion_nombre=puesto.nombre if finalizada else None,
            )
            s.add(solicitud)
            await s.flush()
            ids[clave] = solicitud.id
        s.add(EventoSolicitud(solicitud_id=ids["tarde"], tipo="aprobada", estado_anterior="review",
                              estado_nuevo="approved", usuario_nombre="Revisora Horario",
                              creado_en=momentos["tarde"][0]))
        await s.commit()

    r = await cliente.get("/solicitudes/estadisticas", headers=revisor.headers)
    est = r.json()
    assert r.status_code == 200 and est["horario_laboral"]
    assert est["aprobadas_fuera_horario"] == antes["aprobadas_fuera_horario"] + len(fuera)
    assert all("fuera_horario" not in f for f in est["por_puesto"]), "ya no se mide por puesto"
    listadas = {o["id"]: o for o in est["operaciones_fuera_horario"]}
    assert {ids[c] for c in fuera} <= set(listadas)
    assert not {ids["en_punto"], ids["manana"]} & set(listadas)
    assert listadas[ids["tarde"]]["aprobada_por"] == "Revisora Horario"
    assert listadas[ids["tarde"]]["puesto"] == puesto.nombre

    # Por día y por mes: cada una el día (y el mes) en que se aprobó.
    for unidad, formato in (("por_dia", "%Y-%m-%d"), ("por_mes", "%Y-%m")):
        filas_antes = {f["periodo"]: f for f in antes[unidad]}
        filas = {f["periodo"]: f for f in est[unidad]}
        for periodo in {momentos[c][0].strftime(formato) for c in fuera}:
            sumadas = sum(1 for c in fuera if momentos[c][0].strftime(formato) == periodo)
            assert filas[periodo]["fuera_horario"] == filas_antes[periodo]["fuera_horario"] + sumadas, (unidad, periodo)
    hoy = datetime.now(ZONA_PANAMA).date()
    assert len(est["por_dia"]) == 31 and est["por_dia"][-1]["periodo"] == hoy.isoformat()
    assert len(est["por_mes"]) == 12 and est["por_mes"][-1]["periodo"] == hoy.strftime("%Y-%m")
    assert est["por_anio"][-1]["periodo"] == str(hoy.year)
    assert sum(f["aprobadas"] for f in est["por_anio"]) == est["aprobadas"], "con «Todo», los años suman todo"

    # El mapa de horas: cada una en su día de la semana (1 = lunes) y la hora de la aprobación.
    def celdas(datos: dict) -> dict[tuple[int, int], int]:
        return {(c["dia"], c["hora"]): c["total"] for c in datos["aprobadas_por_hora"]}
    celdas_antes, celdas_despues = celdas(antes), celdas(est)
    for celda, sumadas in (((6, 10), 1), ((3, 15), 2), ((3, 10), 1)):   # sábado 10 h; miércoles 15 h (dos) y 10 h
        assert celdas_despues[celda] == celdas_antes.get(celda, 0) + sumadas, celda
    assert sum(celdas_despues.values()) == est["aprobadas"]

    # La insignia: el personal del SNM la ve; a la agencia le llega nula.
    for clave in momentos:
        r = await cliente.get(f"/solicitudes/{ids[clave]}", headers=revisor.headers)
        assert r.status_code == 200 and r.json()["fuera_de_horario"] is (clave in fuera), clave
        r = await cliente.get(f"/solicitudes/{ids[clave]}", headers=naviera.headers)
        assert r.status_code == 200 and r.json()["fuera_de_horario"] is None, clave
    r = await cliente.get("/solicitudes/agencia", headers=naviera.headers)
    assert {x["fuera_de_horario"] for x in r.json()["items"]} == {None}
    r = await cliente.get("/solicitudes/revision", params={"texto": puesto.nombre, "por_pagina": 100},
                          headers=revisor.headers)
    assert {x["id"]: x["fuera_de_horario"] for x in r.json()["items"]} == {ids[c]: c in fuera for c in momentos}


async def test_series_del_periodo(cliente):
    """Con un periodo, la serie muestra sus días, meses y años (hasta hoy)."""
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    hoy = datetime.now(ZONA_PANAMA).date()
    desde = hoy.replace(day=1)
    r = await cliente.get("/solicitudes/estadisticas", params={"desde": desde.isoformat(), "hasta": hoy.isoformat()},
                          headers=revisor.headers)
    est = r.json()
    assert r.status_code == 200
    assert [f["periodo"] for f in est["por_dia"]] == [(desde + timedelta(days=i)).isoformat()
                                                      for i in range((hoy - desde).days + 1)]
    assert [f["periodo"] for f in est["por_mes"]] == [hoy.strftime("%Y-%m")]
    assert [f["periodo"] for f in est["por_anio"]] == [str(hoy.year)]
