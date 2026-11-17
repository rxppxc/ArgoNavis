"""La revisión del esquema al arrancar (2026-11-17). El código se puso al día y la base
no (faltaba correr migrate.bat): cada pedido respondía «Error interno del servidor» y el
log decía «no existe la columna». Ahora el arranque compara la base con el ORM, dice en
el log qué le falta y qué hacer, y mientras tanto la API responde 503 con el motivo."""
import logging

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.infrastructure import esquema
from app.infrastructure.database import motor_bd

asincrona = pytest.mark.asyncio(loop_scope="session")

SALUD = "http://prueba/api/health"   # fuera de /api/v1 (la base del cliente)


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros: list[logging.LogRecord] = []

    def emit(self, registro):
        self.registros.append(registro)


def _capturar(nombre: str) -> _Captura:
    captura = _Captura()
    logging.getLogger(nombre).addHandler(captura)
    return captura


@asincrona
async def test_la_base_migrada_tiene_todo_lo_que_usa_el_codigo(cliente):
    """Sin falsas alarmas con la base al día. Falla también si un modelo cambia sin su migración."""
    async with motor_bd.connect() as conexion:
        assert await esquema.faltantes_del_esquema(conexion) == []


@asincrona
async def test_nombra_lo_que_le_falta_a_la_base(cliente):
    md = MetaData()
    Table("solicitudes", md, Column("id", Integer, primary_key=True), Column("columna_nueva", String))
    Table("tabla_nueva", md, Column("id", Integer, primary_key=True))
    Table("audit_logs", md, Column("accion", SAEnum("LOGIN_EXITOSO", "ACCION_NUEVA", name="accionauditoria")))
    Table("users", md, Column("user_type", SAEnum("AD", name="tipo_nuevo")))
    async with motor_bd.connect() as conexion:
        faltan = await esquema.faltantes_del_esquema(conexion, md)
    assert set(faltan) == {
        "la columna solicitudes.columna_nueva",
        "la tabla tabla_nueva",
        "el valor ACCION_NUEVA del tipo accionauditoria",
        "el tipo tipo_nuevo",
    }


def test_el_mensaje_dice_que_falta_y_que_hacer():
    mensaje = esquema.mensaje_esquema_atrasado(["la tabla boletas_recargo"])
    assert "le falta la tabla boletas_recargo." in mensaje and "migrate.bat" in mensaje
    muchas = esquema.mensaje_esquema_atrasado([f"la columna t.c{i}" for i in range(1, 8)])
    assert "t.c5" in muchas and "y 2 más" in muchas and "t.c6" not in muchas


@asincrona
async def test_revisar_lo_dice_en_el_log(cliente):
    md = MetaData()
    Table("solicitudes", md, Column("subir_y_bajar_2", String))
    captura = _capturar("app.infrastructure.esquema")
    try:
        assert await esquema.revisar_esquema(motor_bd, md) == ["la columna solicitudes.subir_y_bajar_2"]
    finally:
        logging.getLogger("app.infrastructure.esquema").removeHandler(captura)
    errores = [r.getMessage() for r in captura.registros if r.levelno == logging.ERROR]
    assert errores and "solicitudes.subir_y_bajar_2" in errores[0] and "migrate.bat" in errores[0]


@asincrona
async def test_con_la_bd_apagada_arranca_igual(base_de_datos):
    """Una base que no responde no impide arrancar (como hoy): /api/health lo dice."""
    apagada = create_async_engine("postgresql+asyncpg://nadie:nada@127.0.0.1:1/ninguna")
    captura = _capturar("app.infrastructure.esquema")
    try:
        assert await esquema.revisar_esquema(apagada) == []
    finally:
        logging.getLogger("app.infrastructure.esquema").removeHandler(captura)
        await apagada.dispose()
    assert any(r.levelno == logging.WARNING for r in captura.registros)


def _tareas_de_prueba(monkeypatch) -> list[str]:
    """Las tareas de fondo del ciclo de vida, cambiadas por unas que solo anotan que arrancaron."""
    arrancadas: list[str] = []

    def tarea(nombre):
        async def correr():
            arrancadas.append(nombre)
        return correr

    monkeypatch.setattr(main, "tarea_vencimientos", tarea("vencimientos"))
    monkeypatch.setattr(main, "tarea_correos", tarea("correos"))
    return arrancadas


@asincrona
async def test_al_arrancar_con_la_base_atrasada_la_api_responde_503_con_el_motivo(cliente, admin, monkeypatch):
    """De punta a punta: el ciclo de vida revisa y la API lo dice, en vez de un 500 sin pista.
    Las tareas de fondo no arrancan: fallarían en cada vuelta."""
    async def falta(_conexion, _metadatos=None):
        return ["la columna solicitudes.subir_y_bajar"]

    arrancadas = _tareas_de_prueba(monkeypatch)
    monkeypatch.setattr(esquema, "faltantes_del_esquema", falta)
    monkeypatch.setitem(main._salud, "momento", float("-inf"))
    try:
        async with main.ciclo_vida(main.aplicacion):
            assert main.aplicacion.state.esquema_faltante == ["la columna solicitudes.subir_y_bajar"]
            r = await cliente.get("/solicitudes/revision", headers=admin.headers)
            assert r.status_code == 503, r.text
            assert "base de datos" in r.json()["detail"] and r.headers["x-request-id"]
            salud = await cliente.get(SALUD)
            assert salud.status_code == 503 and salud.json()["estado"] == "base de datos sin migrar"
    finally:
        main.aplicacion.state.esquema_faltante = []
    assert arrancadas == []
    assert (await cliente.get("/solicitudes/revision", headers=admin.headers)).status_code == 200


@asincrona
async def test_al_arrancar_con_la_base_al_dia_todo_sigue_igual(cliente, admin, monkeypatch):
    arrancadas = _tareas_de_prueba(monkeypatch)
    monkeypatch.setitem(main._salud, "momento", float("-inf"))
    try:
        async with main.ciclo_vida(main.aplicacion):
            assert main.aplicacion.state.esquema_faltante == []
            assert (await cliente.get("/solicitudes/revision", headers=admin.headers)).status_code == 200
            assert (await cliente.get(SALUD)).json()["estado"] == "ok"
    finally:
        main.aplicacion.state.esquema_faltante = []
    assert sorted(arrancadas) == ["correos", "vencimientos"]
