"""Exportar las estadísticas de Autorizaciones Marítimas: Excel, PDF y CSV.

Pedido del usuario del 2026-11-10: «que se puedan exportar a Excel, a CSV o
a PDF, que tengan identidad». Lo común a los tres formatos vive aquí: los
datos del informe, los textos (periodo, estados, rótulos de la serie), las
cifras derivadas y el nombre del archivo. Cada formato tiene su módulo
(estadisticas_excel, estadisticas_pdf, estadisticas_csv) y se genera en un
hilo aparte, con turno, como el PDF de la autorización: es CPU-bound.

Identidad: el escudo del SNM y el logo de ARGO NAVIS, la paleta del SNM
(core/identidad.py, la del PDF de la autorización y de los correos) y, en cada
estado, el color de su insignia (comun.py: los --graf-* del tema claro). Los
tres dicen «Uso interno del SNM»: la lista de fuera del horario lleva los
nombres de los funcionarios que aprobaron.

Los textos siguen a los de la pantalla (estadisticas/calculos.ts): si cambia
uno allá, revisa aquí.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from math import ceil
from typing import Literal

from app.core.horario import FIN_LABORAL, INICIO_LABORAL, ZONA_PANAMA
from app.core.identidad import TEXTO
from app.core.texto import slug
from app.domain.schemas.solicitud import (
    FilaEstadisticaPuesto, FilaEstadisticaSerie, SalidaEstadisticasSolicitudes, SalidaUsoSistema,
)
from app.informes.comun import (
    COLOR_APROBADA, COLOR_CORRECCION, COLOR_DENEGADA, COLOR_EXPIRADA, COLOR_FINALIZADA, COLOR_FUERA, COLOR_RECIBIDAS,
    MESES, TIPO_CSV, TIPO_PDF, TIPO_XLSX, ArchivoInforme, cifra, fecha_larga, texto_generado,
)

Formato = Literal["xlsx", "pdf", "csv"]
Unidad = Literal["dia", "mes", "anio"]

SECCION = "Sección de Autorizaciones Marítimas — UCVMM"
TITULO = "Estadísticas de Autorizaciones Marítimas"

COLOR_CALOR = COLOR_APROBADA   # el mapa de horas: el verde de «aprobada»

_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")
DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")

# Horario laboral para el mapa de horas, por horas enteras: laboral de 07 a 14, con el minuto de
# las 15:00 en la casilla de las 14 (2026-11-27, `aprobadas_por_hora`). Sale de core/horario.py.
HORA_INICIO_LABORAL = INICIO_LABORAL.hour
HORA_FIN_LABORAL = FIN_LABORAL.hour
NOTA_BORDE = (f"La columna {HORA_FIN_LABORAL - 1:02d} llega hasta las {HORA_FIN_LABORAL:02d}:00 y la "
              f"{HORA_FIN_LABORAL:02d} empieza a las {HORA_FIN_LABORAL:02d}:01, que ya es fuera del horario.")

_ESPACIO = "\u00a0"   # espacio sin corte: la cifra y el % no se separan (como en la pantalla)


@dataclass(frozen=True)
class DatosInforme:
    estadisticas: SalidaEstadisticasSolicitudes
    # Solo para quien ve todos los sectores (Administrador y supervisor general).
    uso:          SalidaUsoSistema | None
    desde:        date | None
    hasta:        date | None
    unidad:       Unidad
    generado_por: str
    generado_en:  datetime   # con zona horaria

    @property
    def hoy(self) -> date:
        return self.generado_en.astimezone(ZONA_PANAMA).date()

    @property
    def periodo(self) -> str:
        return texto_periodo(self.desde, self.hasta, self.hoy)

    @property
    def alcance(self) -> str:
        """De qué sectores son las cifras: "Todos los sectores", "Sector Pacífico"…"""
        return self.estadisticas.alcance

    @property
    def generado(self) -> str:
        """"10/11/2026 03:10 p. m. por Nombre Apellido"."""
        return texto_generado(self.generado_en, self.generado_por)


# ── Textos ───────────────────────────────────────────────────────────────────

def texto_periodo(desde: date | None, hasta: date | None, hoy: date) -> str:
    """El periodo, para el encabezado: "Del 1 al 31 de octubre de 2026", "Todo el
    historial, hasta el 10 de noviembre de 2026"… (como textoPeriodo en la pantalla)."""
    if not desde and not hasta:
        return f"Todo el historial, hasta el {fecha_larga(hoy)}"
    if desde and not hasta:
        return f"Desde el {fecha_larga(desde)}"
    if not desde and hasta:
        return f"Hasta el {fecha_larga(hasta)}"
    assert desde and hasta
    if desde == hasta:
        return f"El {fecha_larga(desde)}"
    if desde.year != hasta.year:
        return f"Del {fecha_larga(desde)} al {fecha_larga(hasta)}"
    if desde.month != hasta.month:
        return f"Del {fecha_larga(desde, con_anio=False)} al {fecha_larga(hasta)}"
    return f"Del {desde.day} al {fecha_larga(hasta)}"


def porcentaje(parte: int, total: int) -> str:
    """"77 %"; "<1 %" si hay alguna pero no llega al 1 %; nunca "100 %" si falta
    alguna; "—" sin total. Como `porcentaje` en la pantalla."""
    if total <= 0:
        return "—"
    p = parte / total * 100
    if 0 < p < 1:
        return f"<1{_ESPACIO}%"
    return f"{min(round(p), 99 if parte < total else 100)}{_ESPACIO}%"


def proporcion(parte: int, total: int) -> float | None:
    """Entre 0 y 1 (para Excel y el CSV), o None sin total."""
    return parte / total if total > 0 else None


def duracion(horas: float | None) -> str:
    """"45 min", "6 h 24 min", "2 días y 3 h" (como `duracion` en la pantalla)."""
    if horas is None:
        return "—"
    minutos = round(horas * 60)
    if minutos < 60:
        return f"{minutos} min"
    if minutos < 48 * 60:
        h, m = divmod(minutos, 60)
        return f"{h} h {m} min" if m else f"{h} h"
    dias, resto = divmod(minutos, 1440)
    h = resto // 60
    return f"{dias} días y {h} h" if h else f"{dias} días"


def tamano(bytes_: int) -> str:
    """"2.43 GB" (como formatBytes en la pantalla)."""
    for limite, unidad in ((1_073_741_824, "GB"), (1_048_576, "MB"), (1_024, "KB")):
        if bytes_ >= limite:
            return f"{bytes_ / limite:.2f} {unidad}"
    return f"{bytes_} B"


# ── Serie por día, mes o año ─────────────────────────────────────────────────

UNIDADES: dict[str, tuple[str, str]] = {
    # unidad: (encabezado de la columna, título del gráfico)
    "dia":  ("Día", "Solicitudes por día"),
    "mes":  ("Mes", "Solicitudes por mes"),
    "anio": ("Año", "Solicitudes por año"),
}


def serie(e: SalidaEstadisticasSolicitudes, unidad: str) -> list[FilaEstadisticaSerie]:
    return {"dia": e.por_dia, "mes": e.por_mes, "anio": e.por_anio}[unidad]


def rotulo_periodo(periodo: str) -> tuple[str, str, str]:
    """Rótulos de un periodo de la serie: (arriba, abajo, largo) para el eje y las tablas.
    "2026-10-05" → ("5", "oct", "Lunes 5 de octubre de 2026"); "2026-10" → ("oct",
    "2026", "Octubre de 2026"); "2026" → ("2026", "", "2026")."""
    partes = [int(p) for p in periodo.split("-")]
    if len(partes) == 3:
        d = date(*partes)
        return str(d.day), _MESES_CORTOS[d.month - 1], f"{DIAS_SEMANA[d.weekday()]} {fecha_larga(d)}"
    if len(partes) == 2:
        anio, mes = partes
        return _MESES_CORTOS[mes - 1], str(anio), f"{MESES[mes - 1].capitalize()} de {anio}"
    return str(partes[0]), "", str(partes[0])


# Las columnas de la serie, en el orden de la tabla de la pantalla.
COLUMNAS_SERIE: tuple[tuple[str, str], ...] = (
    ("recibidas", "Recibidas"), ("aprobadas", "Aprobadas"), ("finalizadas", "Finalizadas"),
    ("negadas", "Denegadas"), ("expiradas", "Expiradas"), ("fuera_horario", "Fuera del horario"),
)
# Las que se dibujan (el gráfico de la pantalla), con su color.
SERIES_DIBUJADAS: tuple[tuple[str, str, str], ...] = (
    ("recibidas", "Recibidas", COLOR_RECIBIDAS),
    ("aprobadas", "Aprobadas", COLOR_APROBADA),
    ("finalizadas", "Finalizadas", COLOR_FINALIZADA),
)


# ── Cifras del periodo ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Indicador:
    etiqueta: str
    texto:    str                # el valor, ya escrito ("98", "6 h 24 min")
    valor:    float | None       # el número, para Excel y el CSV (en horas, el tiempo de respuesta)
    parte:    int | None = None  # el porcentaje es parte / total
    total:    int | None = None
    base:     str = ""           # "de las recibidas"
    color:    str = TEXTO
    horas:    bool = False       # el tiempo de respuesta: no es una cantidad


def indicadores(e: SalidaEstadisticasSolicitudes) -> list[Indicador]:
    """Las cifras del periodo, en el orden de la pantalla (más las expiradas)."""
    def de(etiqueta: str, n: int, total: int, base: str, color: str) -> Indicador:
        return Indicador(etiqueta, cifra(n), n, n, total, base, color)
    return [
        Indicador("Recibidas", cifra(e.recibidas), e.recibidas, color=COLOR_RECIBIDAS),
        de("Aprobadas", e.aprobadas, e.recibidas, "de las recibidas", COLOR_APROBADA),
        de("Denegadas", e.negadas, e.recibidas, "de las recibidas", COLOR_DENEGADA),
        de("Expiradas", e.expiradas, e.recibidas, "de las recibidas", COLOR_EXPIRADA),
        de("Finalizadas en el puesto", e.finalizadas, e.aprobadas, "de las aprobadas", COLOR_FINALIZADA),
        de("Aprobadas fuera del horario", e.aprobadas_fuera_horario, e.aprobadas, "de las aprobadas", COLOR_FUERA),
        Indicador("Tiempo de respuesta de UCVMM", duracion(e.horas_promedio_resolucion),
                  e.horas_promedio_resolucion, base="promedio, del envío a la decisión", horas=True),
    ]


@dataclass(frozen=True)
class Estado:
    clave:    str   # el de la API
    etiqueta: str
    color:    str
    total:    int


# El orden de la barra «Estado actual» de la pantalla (ESTADOS_BARRA): lo
# terminado bien, lo que sigue en trámite y lo que no prosperó.
_ESTADOS = (
    ("finalized", "Finalizadas", COLOR_FINALIZADA),
    ("approved", "Por finalizar", COLOR_APROBADA),
    ("review", "En revisión", COLOR_RECIBIDAS),
    ("returned", "En corrección", COLOR_CORRECCION),
    ("expired", "Expiradas", COLOR_EXPIRADA),
    ("denied", "Denegadas", COLOR_DENEGADA),
)


def estados(e: SalidaEstadisticasSolicitudes) -> list[Estado]:
    """En qué estado están hoy las solicitudes recibidas en el periodo."""
    return [Estado(clave, etiqueta, color, int(e.por_estado.get(clave, 0) or 0)) for clave, etiqueta, color in _ESTADOS]


def por_finalizar(p: FilaEstadisticaPuesto) -> int:
    """Las aprobadas de un puesto que no se finalizaron ni expiraron (como en GraficoPuestos)."""
    return max(0, p.aprobadas - p.finalizadas - p.expiradas)


def matriz_horas(e: SalidaEstadisticasSolicitudes) -> list[list[int]]:
    """Las aprobadas por día de la semana (filas, lunes a domingo) y hora (columnas, 0 a 23)."""
    matriz = [[0] * 24 for _ in range(7)]
    for c in e.aprobadas_por_hora:
        if 1 <= c.dia <= 7 and 0 <= c.hora <= 23:
            matriz[c.dia - 1][c.hora] = c.total
    return matriz


NIVELES_CALOR = 5
# Como .nivel1 … .nivel5 en Graficos.module.css: el verde de «aprobada» mezclado con
# el blanco. Cero queda como una casilla vacía; en los dos niveles más oscuros la
# cifra va en blanco.
_MEZCLA_NIVEL = (0.0, 0.32, 0.50, 0.67, 0.84, 1.0)
CASILLA_VACIA = "#EEF2F6"


def mezclar(color: str, parte: float, fondo: str = "#FFFFFF") -> str:
    """`parte` de `color` sobre `fondo`, como color-mix en el CSS ("#RRGGBB")."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(fondo[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * parte + y * (1 - parte)):02X}" for x, y in zip(a, b, strict=True))


def nivel_calor(total: int, maximo: int) -> int:
    """0 = ninguna; de 1 a 5 según el máximo (como nivelCalor en la pantalla)."""
    if total <= 0 or maximo <= 0:
        return 0
    # La misma cuenta en coma flotante que la pantalla, para dar el mismo nivel.
    return min(NIVELES_CALOR, max(1, ceil(total / maximo * NIVELES_CALOR)))


def color_nivel(nivel: int) -> str:
    return CASILLA_VACIA if nivel == 0 else mezclar(COLOR_CALOR, _MEZCLA_NIVEL[nivel])


def en_horario_laboral(dia: int, hora: int) -> bool:
    """`dia` de 1 (lunes) a 7. Las casillas de las 07 a las 14: la de las 14 llega hasta las 15:00."""
    return dia <= 5 and HORA_INICIO_LABORAL <= hora < HORA_FIN_LABORAL


def texto_hora(hora: int) -> str:
    """Lo que abarca una casilla: «10:00 a 10:59»; la de las 14, «14:00 a 15:00», y la de las 15,
    «15:01 a 15:59» (como textoHora en la pantalla)."""
    if hora == HORA_FIN_LABORAL - 1:
        return f"{hora:02d}:00 a {HORA_FIN_LABORAL:02d}:00"
    if hora == HORA_FIN_LABORAL:
        return f"{hora:02d}:01 a {hora:02d}:59"
    return f"{hora:02d}:00 a {hora:02d}:59"


def texto_casilla(dia: int, hora: int) -> str:
    return "Laboral" if en_horario_laboral(dia, hora) else "Fuera del horario"


def ordenados_por_tramite(e: SalidaEstadisticasSolicitudes):
    return sorted(e.por_tipo, key=lambda t: (-t.recibidas, t.nombre))


def puestos_con_aprobadas(e: SalidaEstadisticasSolicitudes):
    return [p for p in e.por_puesto if p.aprobadas > 0]


# ── Archivo ──────────────────────────────────────────────────────────────────

def nombre_archivo(datos: DatosInforme, extension: str) -> str:
    """"Estadisticas-autorizaciones-2026-10-01_2026-10-31.xlsx", con el sector si son
    las de uno ("…-sector-atlantico-…"). Sin acentos: va en una cabecera HTTP."""
    desde = datos.desde.isoformat() if datos.desde else "inicio"
    hasta = (datos.hasta or datos.hoy).isoformat()
    sector = "" if datos.alcance == "Todos los sectores" else f"-{slug(datos.alcance)}"
    return f"Estadisticas-autorizaciones{sector}-{desde}_{hasta}.{extension}"


_GENERADORES: dict[str, tuple[str, str]] = {
    # formato: (módulo que lo arma, tipo MIME)
    "xlsx": ("app.informes.estadisticas_excel", TIPO_XLSX),
    "pdf":  ("app.informes.estadisticas_pdf", TIPO_PDF),
    "csv":  ("app.informes.estadisticas_csv", TIPO_CSV),
}


def generar_informe(formato: Formato, datos: DatosInforme) -> ArchivoInforme:
    """El archivo del informe en el formato pedido. Corre en un hilo aparte.
    Cada formato carga solo su módulo: si faltara XlsxWriter (una instalación de
    Windows sin el `pip install`), fallaría el Excel, no el PDF ni el CSV."""
    modulo, tipo = _GENERADORES[formato]
    generar: Callable[[DatosInforme], bytes] = import_module(modulo).generar
    return ArchivoInforme(contenido=generar(datos), tipo=tipo, nombre=nombre_archivo(datos, formato))
