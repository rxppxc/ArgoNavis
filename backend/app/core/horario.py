"""Horario laboral, para las autorizaciones aprobadas fuera de él.

De lunes a viernes, de 07:00 a 15:00, hora de Panamá (reunión del 2026-10-30;
los bordes, del 2026-11-06). Se mide al minuto y las dos puntas van dentro: a
las 15:00 (hasta las 15:00:59) todavía es laboral. Fuera es de 15:01 a 06:59,
y el sábado y el domingo enteros.

Cuenta la hora en que UCVMM aprueba (`solicitudes.aprobada_en`, pedido del
usuario del 2026-11-06); antes contaba la finalización del puesto de control.

`fuera_de_horario` tiene su versión en SQL para las estadísticas
(`_fuera_de_horario` en solicitud_repository.py): tienen que coincidir, y lo
comprueba tests/test_horario.py.

Aprobada fuera del horario, la solicitud lleva un recargo por atención fuera
del horario laboral (`COSTO_FUERA_DE_HORARIO`, guardado al aprobar) y lo ve
también la agencia (2026-11-11): en la bandeja, el expediente, el correo de
aprobación y el PDF. Para cobrarlo, el SNM genera una boleta (2026-11-16,
`boletas_recargo`), que la agencia no ve en el sistema.

Aquí vive también `entre_fechas_panama`, el filtro por días de Panamá que usan
las bandejas, las estadísticas y la bitácora.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

ZONA_PANAMA    = ZoneInfo("America/Panama")
INICIO_LABORAL = time(7, 0)    # el primer minuto laboral
FIN_LABORAL    = time(15, 0)   # el último minuto laboral (incluido)
TEXTO_HORARIO  = "lunes a viernes, de 07:00 a 15:00"


def fuera_de_horario(momento: datetime) -> bool:
    """Si el momento cae fuera del horario laboral (las 15:00 en punto todavía son laborales)."""
    local = momento.astimezone(ZONA_PANAMA)
    minuto = local.time().replace(second=0, microsecond=0)
    return local.weekday() >= 5 or not (INICIO_LABORAL <= minuto <= FIN_LABORAL)


def texto_costo(valor: Decimal) -> str:
    """El monto como se escribe en Panamá: B/.20.00, B/.1,250.00."""
    return f"B/.{valor:,.2f}"


def aviso_fuera_de_horario(costo: Decimal | None) -> list[str]:
    """Las frases del correo (una por línea) y del PDF (seguidas). La pantalla
    dice lo mismo con TEXTO_HORARIO espejado en el frontend."""
    lineas = [f"Aprobada fuera del horario laboral ({TEXTO_HORARIO})."]
    if costo:
        lineas.append(f"Recargo por atención fuera del horario laboral: {texto_costo(costo)}.")
    return lineas


def entre_fechas_panama(columna, desde: date | None, hasta: date | None) -> list:
    """Filtro por días de Panamá (inclusive) sobre una columna con hora, como un
    rango de instantes: `columna >= inicio de desde` y `< inicio del día siguiente
    a hasta`. Así PostgreSQL usa el índice de la columna; con date(timezone(...))
    sobre ella recorría la tabla entera en cada bandeja, estadística y bitácora.
    `columna` es una columna de SQLAlchemy; devuelve las condiciones para un where."""
    filtros = []
    if desde:
        filtros.append(columna >= datetime.combine(desde, time.min, tzinfo=ZONA_PANAMA))
    if hasta and hasta < date.max:   # date.max + 1 día no existe: sin tope arriba
        filtros.append(columna < datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=ZONA_PANAMA))
    return filtros
