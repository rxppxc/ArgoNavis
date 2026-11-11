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
(infrastructure/trabajo_pesado.py).
"""
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import xlsxwriter

from app.core.horario import ZONA_PANAMA
from app.core.informe_estadisticas import (
    AMARILLO, BORDE, COLOR_APROBADA, COLOR_CORRECCION, COLOR_DENEGADA, COLOR_EXPIRADA, COLOR_FINALIZADA,
    COLOR_RECIBIDAS, FONDO, GRIS, INSTITUCION, LOGO_ARGO_NAVIS, LOGO_SNM, MARINO, SISTEMA, TEXTO, USO_INTERNO,
    ArchivoInforme, fecha_hora, fecha_larga,
)

TITULO = "Consulta histórica de solicitudes"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

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
_FORMATO_CELDA: dict[str, dict[str, Any]] = {
    "texto":      {"text_wrap": True},
    "numero":     {"num_format": "#,##0", "align": "right"},
    "fecha":      {"num_format": "dd/mm/yyyy", "align": "right"},
    "fecha_hora": {"num_format": "dd/mm/yyyy hh:mm AM/PM", "align": "right"},
    "moneda":     {"num_format": '"B/."#,##0.00', "align": "right"},
}
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


def _local(momento: datetime) -> datetime:
    """XlsxWriter no admite zona horaria: la hora de Panamá, sin zona."""
    return momento.astimezone(ZONA_PANAMA).replace(tzinfo=None)


def generar(d: DatosHistorico) -> bytes:
    salida = io.BytesIO()
    libro = xlsxwriter.Workbook(salida, {
        "in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
    })
    formatos: dict[tuple, Any] = {}

    def fmt(**props: Any):
        clave = tuple(sorted(props.items()))
        if clave not in formatos:
            base = {"font_name": "Calibri", "font_size": 10, "font_color": TEXTO, "valign": "vcenter"}
            formatos[clave] = libro.add_format({**base, **props})
        return formatos[clave]

    generado = f"{fecha_hora(d.generado_en)} por {d.generado_por}"
    filtros = describir_filtros(d.filtros)
    libro.set_properties({
        "title": TITULO, "subject": filtros, "author": INSTITUCION,
        "company": "Servicio Nacional de Migración de Panamá", "category": "Consulta histórica",
        "comments": f"{SISTEMA}. Generado el {generado}. {USO_INTERNO}.",
    })

    h = libro.add_worksheet("Solicitudes")
    h.hide_gridlines(2)
    h.set_paper(1)   # carta
    h.set_landscape()
    h.set_margins(left=0.4, right=0.4, top=0.7, bottom=0.7)
    h.fit_to_pages(1, 0)
    h.repeat_rows(_FILA_ENCABEZADO)
    h.set_header(f"&L&8{TITULO}&R&8{d.alcance}")
    h.set_footer(f"&L&8{SISTEMA} — {INSTITUCION}. {USO_INTERNO}.&R&8Página &P de &N")

    # ── La identidad, como en el informe de estadísticas ──
    ancho = len(_COLUMNAS)
    h.set_column(0, 0, 9)
    for col, (_, ancho_col, _) in enumerate(_COLUMNAS, start=1):
        h.set_column(col, col, ancho_col)
    for fila, alto in ((0, 24), (1, 16), (2, 16), (3, 16)):
        h.set_row(fila, alto)
    if LOGO_SNM.exists():
        h.insert_image(0, 0, str(LOGO_SNM), {
            "x_scale": 0.105, "y_scale": 0.105, "x_offset": 8, "y_offset": 4, "object_position": 3,
            "description": "Escudo del Servicio Nacional de Migración",
        })
    h.write_string(0, 1, TITULO, fmt(bold=True, font_size=15, font_color=MARINO))
    h.write_string(1, 1, f"{INSTITUCION} · {SISTEMA}", fmt(font_color=GRIS))
    h.write_rich_string(2, 1, fmt(bold=True, font_color=GRIS), "Filtros: ", fmt(font_color=TEXTO), filtros,
                        fmt(font_color=GRIS))
    h.write_rich_string(3, 1, fmt(bold=True, font_color=GRIS), "Alcance: ", fmt(font_color=TEXTO), d.alcance,
                        fmt(font_color=GRIS, italic=True), f" · Generado el {generado} · {USO_INTERNO}",
                        fmt(font_color=GRIS))
    if LOGO_ARGO_NAVIS.exists():
        h.insert_image(0, ancho + 1, str(LOGO_ARGO_NAVIS), {
            "x_scale": 0.19, "y_scale": 0.19, "x_offset": 4, "y_offset": 2, "object_position": 3,
            "description": "Logo de ARGO NAVIS",
        })
    h.set_row(4, 5)
    for col in range(ancho + 2):
        h.write_blank(4, col, None, fmt(bg_color=AMARILLO))

    # ── Cuántas son ──
    n = len(d.filas)
    if d.total > n:
        nota = (f"Se exportaron las primeras {n:,} de {d.total:,} solicitudes (por {d.ordenadas_por}, de la más "
                "reciente a la más antigua): acota los filtros para ver el resto.").replace(",", ".")
        h.write_string(_FILA_NOTA, 1, nota, fmt(bold=True, font_color=COLOR_CORRECCION))
    else:
        h.write_string(_FILA_NOTA, 1, f"{n} solicitud{'' if n == 1 else 'es'}, por {d.ordenadas_por} "
                       "(de la más reciente a la más antigua).", fmt(font_color=GRIS, italic=True))

    # ── La tabla ──
    h.set_row(_FILA_ENCABEZADO, 30)
    for col, (encabezado, _, tipo) in enumerate(_COLUMNAS, start=1):
        h.write_string(_FILA_ENCABEZADO, col, encabezado, fmt(
            bold=True, font_color="#FFFFFF", bg_color=MARINO, border=1, border_color=MARINO, text_wrap=True,
            align="left" if tipo == "texto" else "right"))
    if not d.filas:
        h.write_string(_FILA_ENCABEZADO + 1, 1, "Ninguna solicitud coincide con los filtros.",
                       fmt(italic=True, font_color=GRIS))
    for i, s in enumerate(d.filas, start=1):
        fila = _FILA_ENCABEZADO + i
        etiqueta, color = ESTADOS.get(s.estado, (s.estado, GRIS))
        valores: list[Any] = [
            s.numero, etiqueta, s.tramite, s.agencia, s.puesto, s.sector, s.buque, s.imo,
            s.fecha_operacion, s.pasajeros, s.enviada_en, s.aprobada_en, s.finalizada_en,
            "Sí" if s.fuera_de_horario else None, s.costo,
        ]
        celda = {"border": 1, "border_color": BORDE, "bg_color": FONDO if i % 2 == 0 else "#FFFFFF"}
        for col, ((_, _, tipo), valor) in enumerate(zip(_COLUMNAS, valores), start=1):
            # El estado lleva a la izquierda el color de su insignia (el texto, en tinta).
            extra = {"left": 5, "left_color": color} if col == 2 else {}
            formato = fmt(**celda, **_FORMATO_CELDA[tipo], **extra)
            if valor is None or valor == "":
                h.write_blank(fila, col, None, formato)
            elif tipo == "fecha":
                h.write_datetime(fila, col, datetime.combine(valor, datetime.min.time()), formato)
            elif tipo == "fecha_hora":
                h.write_datetime(fila, col, _local(valor), formato)
            elif tipo in ("numero", "moneda"):
                h.write_number(fila, col, float(valor), formato)
            else:
                h.write_string(fila, col, str(valor), formato)
    h.freeze_panes(_FILA_ENCABEZADO + 1, 2)
    h.autofilter(_FILA_ENCABEZADO, 1, _FILA_ENCABEZADO + max(n, 1), ancho)
    libro.close()
    return salida.getvalue()


def nombre_archivo(d: DatosHistorico) -> str:
    """"Consulta-historica-2026-11-11.xlsx" (sin acentos: va en una cabecera HTTP)."""
    return f"Consulta-historica-{d.generado_en.astimezone(ZONA_PANAMA):%Y-%m-%d}.xlsx"


def generar_archivo(d: DatosHistorico) -> ArchivoInforme:
    """El Excel listo para responder. Corre en un hilo aparte."""
    return ArchivoInforme(contenido=generar(d), tipo=TIPO_XLSX, nombre=nombre_archivo(d))
