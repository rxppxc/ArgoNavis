"""Alta disponibilidad (revisión del 2026-11-08): cada conexión lleva sus topes,
la BD caída, lenta o sin conexiones libres responde 503 con motivo (no un 500
mudo) y /api/health mira la BD."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolAgotado
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from app import main
from app.core.config import obtener_configuracion
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.infrastructure.database import SesionLocal

asincrona = pytest.mark.asyncio(loop_scope="session")

SALUD = "http://prueba/api/health"   # fuera de /api/v1 (la base del cliente)


def _pedido() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/v1/solicitudes/revision",
                    "headers": [], "query_string": b""})


@asincrona
async def test_cada_conexion_lleva_sus_topes(base_de_datos):
    """Una consulta descontrolada se cancela y una transacción olvidada se
    cierra, en vez de retener la conexión (y sus bloqueos de fila) para siempre."""
    conf = obtener_configuracion()
    async with SesionLocal() as s:
        valores = dict((await s.execute(text(
            "SELECT name, setting FROM pg_settings "
            "WHERE name IN ('statement_timeout', 'idle_in_transaction_session_timeout')"
        ))).all())
    assert valores["statement_timeout"] == str(conf.BD_TIEMPO_MAXIMO_CONSULTA * 1000)
    assert valores["idle_in_transaction_session_timeout"] == str(conf.BD_TIEMPO_MAXIMO_INACTIVA * 1000)


@asincrona
async def test_una_consulta_cancelada_por_el_tope_responde_503(base_de_datos):
    async with SesionLocal() as s:
        await s.execute(text("SET LOCAL statement_timeout = 50"))
        with pytest.raises(DBAPIError) as error:
            await s.execute(text("SELECT pg_sleep(2)"))
    assert main._es_falla_de_disponibilidad(error.value), "SQLSTATE 57014: la BD no respondió a tiempo"
    respuesta = await main.error_de_base_de_datos(_pedido(), error.value)
    assert respuesta.status_code == 503 and respuesta.headers["Retry-After"] == "5"


@asincrona
async def test_un_error_de_programacion_sigue_siendo_500(base_de_datos):
    """Un SQL mal armado es un defecto, no una caída: no se disfraza de «intenta de nuevo»."""
    async with SesionLocal() as s:
        with pytest.raises(DBAPIError) as error:
            await s.execute(text("SELECT columna_que_no_existe FROM users"))
    assert not main._es_falla_de_disponibilidad(error.value)
    respuesta = await main.error_de_base_de_datos(_pedido(), error.value)
    assert respuesta.status_code == 500


def test_conexion_cortada_o_invalidada_es_falla_de_disponibilidad():
    assert main._es_falla_de_disponibilidad(OperationalError("SELECT 1", {}, ConnectionResetError("se cortó")))
    assert main._es_falla_de_disponibilidad(
        DBAPIError("SELECT 1", {}, Exception("cerrada"), connection_invalidated=True))


@asincrona
async def test_sin_conexiones_libres_responde_503():
    respuesta = await main.sin_conexiones_libres(_pedido(), PoolAgotado("QueuePool limit reached"))
    assert respuesta.status_code == 503 and b"muy ocupado" in respuesta.body


@asincrona
async def test_la_bd_caida_en_una_bandeja_llega_como_503_con_motivo(cliente, admin, monkeypatch):
    """De punta a punta: el manejador está registrado y la respuesta trae `detail`,
    que el frontend muestra (antes, un 500 «Internal Server Error» en texto plano)."""
    async def caida(*_args, **_kwargs):
        raise OperationalError("SELECT ...", {}, ConnectionResetError("se cortó"))

    monkeypatch.setattr(RepositorioSolicitud, "listar", caida)
    r = await cliente.get("/solicitudes/revision", headers=admin.headers)
    assert r.status_code == 503, r.text
    assert "no respondió" in r.json()["detail"] and r.headers["retry-after"] == "5"


@asincrona
async def test_salud_mira_la_bd_y_reusa_la_respuesta(cliente, monkeypatch):
    monkeypatch.setitem(main._salud, "momento", float("-inf"))
    monkeypatch.setitem(main._salud, "bd_ok", False)
    r = await cliente.get(SALUD)
    assert r.status_code == 200 and r.json()["estado"] == "ok"

    async def sin_bd() -> bool:
        return False

    monkeypatch.setattr(main, "_bd_responde", sin_bd)
    r = await cliente.get(SALUD)
    assert r.status_code == 200, "dentro de la vigencia se reusa la respuesta: es pública y no debe cargar la BD"

    main._salud["momento"] = float("-inf")
    r = await cliente.get(SALUD)
    assert r.status_code == 503 and r.json()["estado"] == "sin base de datos"


@asincrona
async def test_salud_con_la_bd_apagada(base_de_datos, monkeypatch):
    """Un PostgreSQL que no escucha: no responde, sin colgar el healthcheck."""
    apagada = create_async_engine("postgresql+asyncpg://nadie:nada@127.0.0.1:1/ninguna")
    monkeypatch.setattr(main, "motor_bd", apagada)
    try:
        assert await main._bd_responde() is False
    finally:
        await apagada.dispose()
