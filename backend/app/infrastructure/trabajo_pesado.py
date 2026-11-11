"""Tope de trabajos pesados por proceso (revisión de recursos del 2026-11-10).

Armar un PDF o un Excel es Python puro: unos cientos de milisegundos de CPU
(el PDF de estadísticas del peor caso, ~0,6 s). Va en un hilo, para no frenar
el ciclo de eventos, pero el hilo comparte el GIL con él: muchos a la vez le
quitarían la CPU a las demás peticiones del proceso, y cada uno ocupaba un
hilo del pool de asyncio (que comparten bcrypt, el AD y la validación de las
subidas).

Con este tope, cada proceso arma como mucho TRABAJOS_PESADOS_A_LA_VEZ archivos
a la vez; los demás esperan su turno sin ocupar un hilo. Los endpoints, además,
sueltan la conexión a la base antes de esperar (commit), para no retenerla.
"""
import asyncio
from collections.abc import Callable
from typing import TypeVar

from app.core.config import obtener_configuracion

T = TypeVar("T")

_turnos = asyncio.Semaphore(max(1, obtener_configuracion().TRABAJOS_PESADOS_A_LA_VEZ))


async def en_hilo_con_tope(funcion: Callable[..., T], *argumentos: object) -> T:
    """`funcion(*argumentos)` en un hilo, cuando haya turno."""
    async with _turnos:
        return await asyncio.to_thread(funcion, *argumentos)
