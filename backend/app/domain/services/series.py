"""Las series de las estadísticas por día, mes y año (2026-11-06; hasta el
2026-11-14, en solicitud_service.py). Funciones puras: las prueba test_horario.py."""
from collections.abc import Callable
from datetime import date, timedelta

from app.domain.schemas.solicitud import FilaEstadisticaSerie


def meses_antes(dia: date, meses: int) -> date:
    """El primer día del mes que queda `meses` meses antes del de `dia` (negativo: después)."""
    total = dia.year * 12 + dia.month - 1 - meses
    return date(total // 12, total % 12 + 1, 1)


def periodos_dia(inicio: date, fin: date) -> list[date]:
    return [inicio + timedelta(days=i) for i in range((fin - inicio).days + 1)]


def periodos_mes(inicio: date, fin: date) -> list[date]:
    """El primer día de cada mes, del de `inicio` al de `fin`."""
    meses: list[date] = []
    mes = inicio.replace(day=1)
    while mes <= fin:
        meses.append(mes)
        mes = meses_antes(mes, -1)
    return meses


def periodos_anio(inicio: date, fin: date) -> list[date]:
    return [date(anio, 1, 1) for anio in range(inicio.year, fin.year + 1)]


def serie(
    diaria: dict[date, dict[str, int]], periodos: list[date], clave_de: Callable[[date], str],
) -> list[FilaEstadisticaSerie]:
    """La serie diaria sumada en los `periodos` (días, meses o años, según `clave_de`)."""
    cifras: dict[str, dict[str, int]] = {}
    for dia, del_dia in diaria.items():
        destino = cifras.setdefault(clave_de(dia), {})
        for hito, total in del_dia.items():
            destino[hito] = destino.get(hito, 0) + total
    return [FilaEstadisticaSerie(periodo=clave_de(p), **cifras.get(clave_de(p), {})) for p in periodos]
