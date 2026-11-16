"""La consulta histórica de solicitudes en Excel (.xlsx), con XlsxWriter (2026-11-11).

Una hoja, «Solicitudes», con la identidad del informe de estadísticas (escudo
del SNM, título, filtros, quién la generó, logo de ARGO NAVIS y la franja
amarilla) y una fila por solicitud: número, estado (con el color de su
insignia a la izquierda), trámite, agencia, puesto, sector, buque, IMO,
operación, pasajeros, fechas de envío, aprobación y finalización, si se
aprobó fuera del horario y su costo migratorio.

La fila de encabezados queda fija al bajar y lleva los filtros de Excel. Las
cifras son números; las fechas, fechas de Excel en hora de Panamá; el costo,
moneda (B/.). Ningún texto se convierte en fórmula ni en enlace.

Recibe datos planos (no objetos ORM): se arma en un hilo, con turno
(infrastructure/trabajo_pesado.py). La identidad arriba y los formatos de
las celdas son los de app/informes/excel.py.
"""
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.horario import ZONA_PANAMA
from app.core.identidad import GRIS
from app.informes.comun import (
    COLOR_APROBADA, COLOR_CORRECCION, COLOR_DENEGADA, COLOR_EXPIRADA, COLOR_FINALIZADA, COLOR_RECIBIDAS, TIPO_XLSX,
    ArchivoInforme, cifra, fecha_larga, texto_generado,
)
from app.informes.excel import FORMATOS_CELDA, LibroInforme

TITULO = "Consulta histórica de solicitudes"

# Como ETIQUETA_ESTADO en la pantalla (presentacion.ts), con el color de cada insignia.
ESTADOS: dict[str, tuple[str, str]] = {
    "review":    ("En revisión", COLOR_RECIBIDAS),
    "returned":  ("En corrección", COLOR_CORRECCION),
    "approved":  ("Aprobada", COLOR_APROBADA),
    "denied":    ("Denegada", COLOR_DENEGADA),
    "finalized": ("Finalizada", COLOR_FINALIZADA),
    "expired":   ("Expirada", COLOR_EXPIRADA),
}

# (encabezado, ancho, tipo de celda)
_COLUMNAS: tuple[tuple[str, int, str], ...] = (
    ("N.º", 17, "texto"),
    ("Estado", 13, "texto"),
    ("Trámite", 26, "texto"),
    ("Agencia naviera", 26, "texto"),
    ("Puesto", 22, "texto"),
    ("Sector", 15, "texto"),
    ("Buque", 20, "texto"),
    ("IMO", 10, "texto"),
    ("Operación", 11, "fecha"),
    ("Pasajeros", 9, "numero"),
    ("Enviada", 18, "fecha_hora"),
    ("Aprobada", 18, "fecha_hora"),
    ("Finalizada", 18, "fecha_hora"),
    ("Fuera del horario", 10, "texto"),
    ("Costo migratorio", 11, "moneda"),
)
_FILA_NOTA = 6
_FILA_ENCABEZADO = 7


@dataclass(frozen=True)
class FilaHistorico:
    numero:           str | None
    estado:           str               # la clave: "approved", "finalized"…
    tramite:          str
    agencia:          str
    puesto:           str
    sector:           str | None
    buque:            str | None
    imo:              str | None
    fecha_operacion:  date
    pasajeros:        int
    enviada_en:       datetime
    aprobada_en:      datetime | None
    finalizada_en:    datetime | None
    fuera_de_horario: bool
    costo:            Decimal | None


@dataclass(frozen=True)
class FiltrosAplicados:
    """Los filtros de la consulta, con los nombres ya resueltos (para el encabezado)."""
    texto:            str | None = None
    pasajero:         str | None = None
    agencia:          str | None = None
    puesto:           str | None = None
    tramite:          str | None = None
    estado:           str | None = None
    fuera_de_horario: bool = False
    fecha:            str = "envio"     # "envio" | "operacion"
    desde:            date | None = None
    hasta:            date | None = None


@dataclass(frozen=True)
class DatosHistorico:
    filas:        list[FilaHistorico]
    total:        int                   # las que cumplen los filtros (puede ser más que las filas)
    filtros:      FiltrosAplicados
    alcance:      str                   # "Todos los sectores", "Sector Atlántico"…
    generado_por: str
    generado_en:  datetime              # con zona horaria
    ordenadas_por: str = field(default="fecha de envío")


def describir_filtros(f: FiltrosAplicados) -> str:
    """"Enviadas: del 1 de enero al 31 de diciembre de 2027 · Agencia: …"."""
    partes: list[str] = []
    if f.desde or f.hasta:
        que = "Operación" if f.fecha == "operacion" else "Enviadas"
        if f.desde and f.hasta:
            partes.append(f"{que}: del {fecha_larga(f.desde)} al {fecha_larga(f.hasta)}")
        elif f.desde:
            partes.append(f"{que}: desde el {fecha_larga(f.desde)}")
        elif f.hasta:
            partes.append(f"{que}: hasta el {fecha_larga(f.hasta)}")
    estado = ESTADOS[f.estado][0] if f.estado in ESTADOS else None
    for etiqueta, valor in (("Estado", estado), ("Trámite", f.tramite), ("Agencia", f.agencia), ("Puesto", f.puesto)):
        if valor:
            partes.append(f"{etiqueta}: {valor}")
    if f.pasajero:
        partes.append(f"Pasajero: «{f.pasajero}»")
    if f.texto:
        partes.append(f"Texto: «{f.texto}»")
    if f.fuera_de_horario:
        partes.append("Solo aprobadas fuera del horario")
    return " · ".join(partes) or "Sin filtros: todas las solicitudes"


def generar(d: DatosHistorico) -> bytes:
    salida = io.BytesIO()
    filtros = describir_filtros(d.filtros)
    x = LibroInforme(salida, titulo=TITULO, asunto=filtros, categoria="Consulta histórica",
                     generado=texto_generado(d.generado_en, d.generado_por))
    ancho = len(_COLUMNAS)
    h = x.hoja("Solicitudes", ancho, contexto=[("Filtros", filtros), ("Sectores", d.alcance)],
               encabezado=d.alcance, horizontal=True, margenes=(0.4, 0.7))
    h.repeat_rows(_FILA_ENCABEZADO)
    for col, (_, ancho_col, _) in enumerate(_COLUMNAS, start=1):
        h.set_column(col, col, ancho_col)

    # ── Cuántas son ──
    n = len(d.filas)
    if d.total > n:
        nota = (f"Se exportaron las primeras {cifra(n)} de {cifra(d.total)} solicitudes (por {d.ordenadas_por}, "
                "de la más reciente a la más antigua): acota los filtros para ver el resto.")
        h.write_string(_FILA_NOTA, 1, nota, x.f(bold=True, font_color=COLOR_CORRECCION))
    else:
        h.write_string(_FILA_NOTA, 1, f"{n} solicitud{'' if n == 1 else 'es'}, por {d.ordenadas_por} "
                       "(de la más reciente a la más antigua).", x.f(font_color=GRIS, italic=True))

    # ── La tabla ──
    h.set_row(_FILA_ENCABEZADO, 30)
    for col, (encabezado, _, tipo) in enumerate(_COLUMNAS, start=1):
        h.write_string(_FILA_ENCABEZADO, col, encabezado, x.encabezado(tipo))
    if not d.filas:
        h.write_string(_FILA_ENCABEZADO + 1, 1, "Ninguna solicitud coincide con los filtros.",
                       x.f(italic=True, font_color=GRIS))
    for i, s in enumerate(d.filas, start=1):
        etiqueta, color = ESTADOS.get(s.estado, (s.estado, GRIS))
        valores: list[Any] = [
            s.numero, etiqueta, s.tramite, s.agencia, s.puesto, s.sector, s.buque, s.imo,
            s.fecha_operacion, s.pasajeros, s.enviada_en, s.aprobada_en, s.finalizada_en,
            "Sí" if s.fuera_de_horario else None, s.costo,
        ]
        for col, ((_, _, tipo), valor) in enumerate(zip(_COLUMNAS, valores, strict=True), start=1):
            # El estado lleva a la izquierda el color de su insignia (el texto, en tinta).
            extra = {"left": 5, "left_color": color} if col == 2 else {}
            x.escribir(h, _FILA_ENCABEZADO + i, col, valor, tipo, x.celda(i % 2 == 0, **FORMATOS_CELDA[tipo], **extra))
    h.freeze_panes(_FILA_ENCABEZADO + 1, 2)
    h.autofilter(_FILA_ENCABEZADO, 1, _FILA_ENCABEZADO + max(n, 1), ancho)
    x.libro.close()
    return salida.getvalue()


def nombre_archivo(d: DatosHistorico) -> str:
    """"Consulta-historica-2026-11-11.xlsx" (sin acentos: va en una cabecera HTTP)."""
    return f"Consulta-historica-{d.generado_en.astimezone(ZONA_PANAMA):%Y-%m-%d}.xlsx"


def generar_archivo(d: DatosHistorico) -> ArchivoInforme:
    """El Excel listo para responder. Corre en un hilo aparte."""
    return ArchivoInforme(contenido=generar(d), tipo=TIPO_XLSX, nombre=nombre_archivo(d))
