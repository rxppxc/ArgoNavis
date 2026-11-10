"""Exportar las estadísticas a Excel, PDF y CSV (pedido del usuario del 2026-11-10).

Los tres archivos llevan la identidad (periodo, quién lo generó, «Uso interno
del SNM»), las mismas cifras que /solicitudes/estadisticas y se generan aunque
el periodo esté vacío o los nombres sean larguísimos. El CSV neutraliza las
fórmulas y el Excel no convierte textos en fórmulas.
"""
import csv
import io
import re
import zipfile
from datetime import date, datetime

import pytest

from app.core.horario import ZONA_PANAMA
from app.core.informe_estadisticas import (
    DatosInforme, duracion, generar_informe, nombre_archivo, porcentaje, rotulo_periodo, texto_periodo,
)
from app.domain.schemas.solicitud import (
    FilaEstadisticaPuesto, FilaEstadisticaSerie, FilaEstadisticaTipo, FilaFueraHorario, FilaPorHora, FilaTopAgencia,
    SalidaEstadisticasSolicitudes, SalidaUsoSistema,
)
from conftest import crear_actor

asincrona = pytest.mark.asyncio(loop_scope="session")

RUTA = "/solicitudes/estadisticas/exportar"
NBSP = " "


def _hojas(contenido: bytes) -> tuple[list[str], str, list[str]]:
    """Del .xlsx: los nombres de las hojas, los textos y el XML de cada hoja."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        libro = z.read("xl/workbook.xml").decode()
        textos = z.read("xl/sharedStrings.xml").decode()
        hojas = [z.read(n).decode() for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)]
    return re.findall(r'<sheet name="([^"]+)"', libro), textos, hojas


def _csv(contenido: bytes) -> list[list[str]]:
    assert contenido.startswith("﻿".encode()), "con BOM, para que Excel lo abra como UTF-8"
    return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig"))))


HOJAS = ["Resumen", "Por día", "Por mes", "Por año", "Por trámite", "Por puesto", "Horas de aprobación",
         "Fuera del horario"]


@asincrona
async def test_exporta_en_los_tres_formatos(cliente, admin):
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    est = (await cliente.get("/solicitudes/estadisticas", headers=revisor.headers)).json()
    hoy = datetime.now(ZONA_PANAMA).date()

    r = await cliente.get(RUTA, params={"formato": "xlsx"}, headers=revisor.headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # Las de su sector (2026-11-10): lo dicen el nombre del archivo y el encabezado.
    assert r.headers["content-disposition"] == (
        f'attachment; filename="Estadisticas-autorizaciones-sector-pacifico-inicio_{hoy.isoformat()}.xlsx"')
    assert r.headers["cache-control"] == "no-store"
    hojas, textos, xml_hojas = _hojas(r.content)
    assert hojas == HOJAS, "sin el uso del sistema: no ve todos los sectores"
    assert "Revisor Prueba" in textos and "Uso interno del SNM" in textos and "Todo el historial" in textos
    assert "Sector Pacífico" in textos
    assert not any("<f>" in x for x in xml_hojas), "solo valores: ninguna fórmula"

    # El Administrador ve todos los sectores, con el uso del sistema.
    r = await cliente.get(RUTA, params={"formato": "xlsx"}, headers=admin.headers)
    hojas, textos, _ = _hojas(r.content)
    assert hojas == [*HOJAS, "Uso del sistema"] and "Todos los sectores" in textos
    assert r.headers["content-disposition"] == (
        f'attachment; filename="Estadisticas-autorizaciones-inicio_{hoy.isoformat()}.xlsx"')

    r = await cliente.get(RUTA, params={"formato": "pdf"}, headers=revisor.headers)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-") and r.headers["content-disposition"].endswith('.pdf"')

    r = await cliente.get(RUTA, params={"formato": "csv"}, headers=revisor.headers)
    assert r.status_code == 200 and r.headers["content-type"] == "text/csv; charset=utf-8"
    filas = _csv(r.content)
    assert filas[0] == ["ARGO NAVIS · Sistema Interno Marítimo"]
    generado = next(f for f in filas if f and f[0] == "Generado")
    assert generado[1].endswith("por Revisor Prueba")
    # Las mismas cifras que la pantalla.
    recibidas = next(f for f in filas if f and f[0] == "Recibidas")
    assert int(recibidas[1]) == est["recibidas"]
    finalizadas = next(f for f in filas if f and f[0] == "Finalizadas en el puesto")
    assert int(finalizadas[1]) == est["finalizadas"]


@asincrona
async def test_periodo_unidad_y_validacion(cliente):
    revisor = await crear_actor("UCVMM", prefijo="revisor")
    params = {"formato": "pdf", "desde": "2026-10-01", "hasta": "2026-10-31", "unidad": "dia"}
    r = await cliente.get(RUTA, params=params, headers=revisor.headers)
    assert r.status_code == 200, r.text
    assert 'filename="Estadisticas-autorizaciones-sector-pacifico-2026-10-01_2026-10-31.pdf"' in \
        r.headers["content-disposition"]
    r = await cliente.get(RUTA, params={**params, "formato": "xlsx", "unidad": "anio"}, headers=revisor.headers)
    hojas, textos, _ = _hojas(r.content)
    assert r.status_code == 200 and "Del 1 al 31 de octubre de 2026" in textos
    assert "Solicitudes por año" in textos, "la hoja «Resumen» lleva la serie que se veía en pantalla"
    for malo in ({"formato": "docx"}, {"formato": "pdf", "unidad": "semana"}, {}):
        r = await cliente.get(RUTA, params=malo, headers=revisor.headers)
        assert r.status_code == 422, malo


@asincrona
async def test_solo_quien_ve_las_estadisticas(cliente, admin, sysadmin):
    naviera = await crear_actor("Naviera", prefijo="naviera")
    puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    for actor in (naviera, puesto, sysadmin):
        r = await cliente.get(RUTA, params={"formato": "csv"}, headers=actor.headers)
        assert r.status_code == 403, actor.username
    assert (await cliente.get(RUTA, params={"formato": "csv"})).status_code == 401
    assert (await cliente.get(RUTA, params={"formato": "csv"}, headers=admin.headers)).status_code == 200


# ── Sin HTTP: los generadores con datos armados ──────────────────────────────

def _datos(estadisticas: SalidaEstadisticasSolicitudes, uso: SalidaUsoSistema | None = None, **extra) -> DatosInforme:
    return DatosInforme(
        estadisticas=estadisticas,
        uso=uso or SalidaUsoSistema(usuarios=0, usuarios_activos=0, agencias=0, documentos=0, almacenamiento_bytes=0),
        desde=extra.get("desde"), hasta=extra.get("hasta"), unidad=extra.get("unidad", "mes"),
        generado_por="Persona de Prueba", generado_en=datetime(2026, 11, 10, 15, 10, tzinfo=ZONA_PANAMA),
    )


def _vacias(**campos) -> SalidaEstadisticasSolicitudes:
    base = {"recibidas": 0, "por_estado": {}, "aprobadas": 0, "negadas": 0, "expiradas": 0, "finalizadas": 0,
            "horario_laboral": "lunes a viernes, de 07:00 a 15:00",
            "por_dia": [FilaEstadisticaSerie(periodo="2026-11-10")], "por_mes": [FilaEstadisticaSerie(periodo="2026-11")],
            "por_anio": [FilaEstadisticaSerie(periodo="2026")]}
    return SalidaEstadisticasSolicitudes(**{**base, **campos})


def test_el_csv_neutraliza_las_formulas():
    """Un nombre que empieza con =, +, - o @ Excel lo ejecutaría como fórmula."""
    peligrosos = ['=HYPERLINK("http://x","clic")', "+cmd", "-2+3", "@SUMA(1)"]
    e = _vacias(por_puesto=[FilaEstadisticaPuesto(puesto=n, aprobadas=1, finalizadas=0, expiradas=0) for n in peligrosos])
    uso = SalidaUsoSistema(usuarios=1, usuarios_activos=1, agencias=1, documentos=0, almacenamiento_bytes=0,
                           top_agencias=[FilaTopAgencia(agencia_id=1, nombre="=1+1", total=3)])
    filas = _csv(generar_informe("csv", _datos(e, uso)).contenido)
    celdas = {f[0] for f in filas if f}
    assert {"'" + n for n in peligrosos} <= celdas and "'=1+1" in celdas
    assert not celdas & set(peligrosos)


def test_el_excel_deja_los_textos_como_texto():
    e = _vacias(por_tipo=[FilaEstadisticaTipo(codigo="X", nombre="=1+1", recibidas=1, aprobadas=0, negadas=0,
                                             expiradas=0)], recibidas=1, por_estado={"review": 1})
    _, textos, hojas = _hojas(generar_informe("xlsx", _datos(e)).contenido)
    assert "=1+1" in textos and not any("<f>" in x for x in hojas)


def test_se_generan_vacios_y_con_nombres_larguisimos():
    largo = "Nombre larguísimo sin espacios " + "x" * 160
    e = _vacias(
        recibidas=40, por_estado={"finalized": 20, "approved": 5, "review": 5, "returned": 4, "expired": 3, "denied": 3},
        aprobadas=30, negadas=3, expiradas=3, finalizadas=20, horas_promedio_resolucion=50.5, aprobadas_fuera_horario=60,
        operaciones_fuera_horario=[FilaFueraHorario(id=i, numero=None, tipo_tramite=largo, puesto=largo,
                                                    aprobada_en=datetime(2026, 11, 1, 16, 0, tzinfo=ZONA_PANAMA),
                                                    aprobada_por=largo) for i in range(50)],
        aprobadas_por_hora=[FilaPorHora(dia=d, hora=h, total=d * h + 1) for d in range(1, 8) for h in range(24)],
        por_tipo=[FilaEstadisticaTipo(codigo=str(i), nombre=largo, recibidas=i, aprobadas=i, negadas=0, expiradas=0)
                  for i in range(12)],
        por_puesto=[FilaEstadisticaPuesto(puesto=largo + str(i), aprobadas=5, finalizadas=3, expiradas=1)
                    for i in range(15)],
        por_dia=[FilaEstadisticaSerie(periodo=f"2026-10-{d:02d}", recibidas=d, aprobadas=d, finalizadas=d)
                 for d in range(1, 32)],
    )
    for estadisticas, unidad in ((e, "dia"), (e, "anio"), (_vacias(), "mes")):
        for formato in ("xlsx", "pdf", "csv"):
            archivo = generar_informe(formato, _datos(estadisticas, unidad=unidad))
            assert len(archivo.contenido) > 1000, (formato, unidad)
    pdf = generar_informe("pdf", _datos(e, unidad="dia")).contenido
    assert len(re.findall(rb"/Type /Page[^s]", pdf)) >= 2


def test_textos_del_informe():
    hoy = date(2026, 11, 10)
    assert texto_periodo(None, None, hoy) == "Todo el historial, hasta el 10 de noviembre de 2026"
    assert texto_periodo(date(2026, 10, 1), date(2026, 10, 31), hoy) == "Del 1 al 31 de octubre de 2026"
    assert texto_periodo(date(2026, 9, 15), date(2026, 10, 31), hoy) == "Del 15 de septiembre al 31 de octubre de 2026"
    assert texto_periodo(date(2025, 12, 1), date(2026, 1, 31), hoy) == \
        "Del 1 de diciembre de 2025 al 31 de enero de 2026"
    assert texto_periodo(date(2026, 11, 2), date(2026, 11, 2), hoy) == "El 2 de noviembre de 2026"
    assert texto_periodo(date(2026, 1, 5), None, hoy) == "Desde el 5 de enero de 2026"
    assert texto_periodo(None, date(2026, 3, 1), hoy) == "Hasta el 1 de marzo de 2026"
    # Como `porcentaje` y `duracion` de la pantalla (calculos.ts).
    assert porcentaje(0, 0) == "—"
    assert porcentaje(1, 200) == f"<1{NBSP}%"
    assert porcentaje(199, 200) == f"99{NBSP}%", "nunca 100 % si falta alguna"
    assert porcentaje(200, 200) == f"100{NBSP}%"
    assert porcentaje(77, 100) == f"77{NBSP}%"
    assert [duracion(h) for h in (None, 0.5, 6.4, 6, 50.5, 72)] == ["—", "30 min", "6 h 24 min", "6 h", "2 días y 2 h",
                                                                     "3 días"]
    assert rotulo_periodo("2026-10-05") == ("5", "oct", "Lunes 5 de octubre de 2026")
    assert rotulo_periodo("2026-09") == ("sept", "2026", "Septiembre de 2026")
    assert rotulo_periodo("2026") == ("2026", "", "2026")
    assert nombre_archivo(_datos(_vacias(), desde=date(2026, 1, 5)), "csv") == \
        "Estadisticas-autorizaciones-2026-01-05_2026-11-10.csv"
