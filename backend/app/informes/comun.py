"""Lo común a los informes: el archivo que se responde, cómo se escriben fechas y
cifras (como en la pantalla) y el color de cada estado."""
from dataclasses import dataclass
from datetime import date, datetime

from app.core.horario import ZONA_PANAMA

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_PDF = "application/pdf"
TIPO_CSV = "text/csv; charset=utf-8"

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")

# El color de cada estado: el de su insignia en los gráficos (--graf-*, tema claro),
# validados con el validador de dataviz. «Fuera del horario» va en morado. Si cambias
# uno en globals.css, vuelve a validarlos y cámbialo aquí.
COLOR_RECIBIDAS = "#2563EB"
COLOR_CORRECCION = "#EA580C"
COLOR_APROBADA = "#1E7729"
COLOR_DENEGADA = "#DC2626"
COLOR_FINALIZADA = "#04A19B"
COLOR_EXPIRADA = "#8391A5"
COLOR_FUERA = "#9333EA"


@dataclass(frozen=True)
class ArchivoInforme:
    contenido: bytes
    tipo:      str   # MIME
    nombre:    str   # sin acentos: va en una cabecera HTTP


def fecha_larga(d: date, con_anio: bool = True) -> str:
    """"5 de octubre de 2026"."""
    return f"{d.day} de {MESES[d.month - 1]}" + (f" de {d.year}" if con_anio else "")


def fecha_hora(momento: datetime) -> str:
    """"05/10/2026 03:10 p. m.", en hora de Panamá."""
    local = momento.astimezone(ZONA_PANAMA)
    hora = local.hour % 12 or 12
    return f"{local:%d/%m/%Y} {hora:02d}:{local:%M} {'a. m.' if local.hour < 12 else 'p. m.'}"


def texto_generado(momento: datetime, por: str) -> str:
    """Quién generó el archivo y cuándo: "10/11/2026 03:10 p. m. por Nombre Apellido"."""
    return f"{fecha_hora(momento)} por {por}"


def cifra(n: int) -> str:
    """"1,342", como la pantalla (es-PA)."""
    return f"{n:,}"
