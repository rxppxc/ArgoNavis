"""Lo común a los informes en Excel (XlsxWriter): el libro, los formatos de las
celdas y la identidad arriba de cada hoja. Lo usan las estadísticas
(estadisticas_excel.py) y la consulta histórica (historico_excel.py).

Arriba de cada hoja: el escudo del SNM en el margen (columna A), el título, la
institución y el sistema, una línea de contexto («Periodo: … · Sectores: …»),
quién lo generó y cuándo, el logo de ARGO NAVIS a la derecha y la franja
amarilla, como en el PDF de la autorización. Encabezados de tabla en marino con
letra blanca y filas alternas en celeste.

Las cifras son números y las fechas, fechas de Excel en hora de Panamá. Ningún
texto se convierte en fórmula ni en enlace: un nombre que empiece con «=» queda
como texto.
"""
import io
from datetime import datetime, time
from typing import Any

import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from app.core.horario import ZONA_PANAMA
from app.core.identidad import (
    AMARILLO, BORDE, FONDO, GRIS, INSTITUCION, INSTITUCION_COMPLETA, LOGO_ARGO_NAVIS, LOGO_SNM, MARINO, SISTEMA,
    TEXTO, USO_INTERNO,
)

# El formato de cada tipo de columna.
FORMATOS_CELDA: dict[str, dict[str, Any]] = {
    "texto":      {"text_wrap": True},
    "numero":     {"num_format": "#,##0", "align": "right"},
    "porcentaje": {"num_format": "0%", "align": "right"},
    "fecha":      {"num_format": "dd/mm/yyyy", "align": "right"},
    "fecha_hora": {"num_format": "dd/mm/yyyy hh:mm AM/PM", "align": "right"},
    "moneda":     {"num_format": '"B/."#,##0.00', "align": "right"},
}
PRIMERA_FILA_LIBRE = 6   # bajo la identidad (filas 0 a 4), con una de aire


class LibroInforme:
    """Un libro en memoria (sin archivos temporales) con la identidad del SNM."""

    def __init__(self, salida: io.BytesIO, *, titulo: str, asunto: str, categoria: str, generado: str) -> None:
        self.libro = xlsxwriter.Workbook(salida, {
            "in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
        })
        self.titulo_informe = titulo
        self.generado = generado
        self._formatos: dict[tuple, Any] = {}
        self.libro.set_properties({
            "title": titulo, "subject": asunto, "author": INSTITUCION, "company": INSTITUCION_COMPLETA,
            "category": categoria, "comments": f"{SISTEMA}. Generado el {generado}. {USO_INTERNO}.",
        })

    def f(self, **props: Any):
        """Un formato, creado una sola vez por combinación (XlsxWriter no deja
        cambiar uno que ya se usó)."""
        clave = tuple(sorted(props.items()))
        if clave not in self._formatos:
            base = {"font_name": "Calibri", "font_size": 10, "font_color": TEXTO, "valign": "vcenter"}
            self._formatos[clave] = self.libro.add_format({**base, **props})
        return self._formatos[clave]

    def celda(self, fila_par: bool, **props: Any):
        """Una celda de tabla: borde fino y, en las filas pares, el fondo celeste."""
        return self.f(border=1, border_color=BORDE, bg_color=FONDO if fila_par else "#FFFFFF", **props)

    def encabezado(self, tipo: str):
        """Un encabezado de tabla, en marino con letra blanca; a la derecha si la
        columna (`tipo`, ver FORMATOS_CELDA) es de cifras o fechas."""
        return self.f(bold=True, font_color="#FFFFFF", bg_color=MARINO, border=1, border_color=MARINO,
                      text_wrap=True, align="left" if tipo == "texto" else "right")

    def hoja(self, nombre: str, ancho: int, *, contexto: list[tuple[str, str]], encabezado: str,
             horizontal: bool = False, margenes: tuple[float, float] = (0.5, 0.75)) -> Worksheet:
        """Una hoja con la identidad en las filas 0 a 4 (la primera libre es
        PRIMERA_FILA_LIBRE). La columna A es el margen con el escudo; el contenido
        va desde la B, en `ancho` columnas, con el logo de ARGO NAVIS a su derecha.
        `contexto` son los pares (rótulo, valor) de la tercera línea; `encabezado`,
        lo que va a la derecha del encabezado de página; `margenes`, (lados, arriba
        y abajo) en pulgadas."""
        h = self.libro.add_worksheet(nombre)
        h.hide_gridlines(2)
        h.set_paper(1)   # carta
        lados, arriba = margenes
        h.set_margins(left=lados, right=lados, top=arriba, bottom=arriba)
        h.fit_to_pages(1, 0)
        if horizontal:
            h.set_landscape()
        h.set_header(f"&L&8{self.titulo_informe}&R&8{encabezado}")
        h.set_footer(f"&L&8{SISTEMA} — {INSTITUCION}. {USO_INTERNO}.&R&8Página &P de &N")
        h.set_column(0, 0, 9)
        for fila, alto in ((0, 24), (1, 16), (2, 16), (3, 16)):
            h.set_row(fila, alto)
        if LOGO_SNM.exists():
            h.insert_image(0, 0, str(LOGO_SNM), {
                "x_scale": 0.105, "y_scale": 0.105, "x_offset": 8, "y_offset": 4, "object_position": 3,
                "description": f"Escudo del {INSTITUCION}",
            })
        h.write_string(0, 1, self.titulo_informe, self.f(bold=True, font_size=15, font_color=MARINO))
        h.write_string(1, 1, f"{INSTITUCION} · {SISTEMA}", self.f(font_color=GRIS))
        partes: list[Any] = []
        for i, (rotulo, valor) in enumerate(contexto):
            partes += [self.f(bold=True, font_color=GRIS), f"{' · ' if i else ''}{rotulo}: ",
                       self.f(font_color=TEXTO), valor]
        h.write_rich_string(2, 1, *partes, self.f(font_color=GRIS))
        h.write_string(3, 1, f"Generado el {self.generado} · {USO_INTERNO}", self.f(font_color=GRIS, italic=True))
        if LOGO_ARGO_NAVIS.exists():
            h.insert_image(0, ancho + 1, str(LOGO_ARGO_NAVIS), {
                "x_scale": 0.19, "y_scale": 0.19, "x_offset": 4, "y_offset": 2, "object_position": 3,
                "description": "Logo de ARGO NAVIS",
            })
        # La franja amarilla bajo la identidad, como en el PDF de la autorización.
        h.set_row(4, 5)
        for col in range(ancho + 2):
            h.write_blank(4, col, None, self.f(bg_color=AMARILLO))
        return h

    @staticmethod
    def escribir(h: Worksheet, fila: int, col: int, valor: Any, tipo: str, formato) -> None:
        """Un valor según el tipo de su columna: vacío, fecha, fecha y hora (en hora
        de Panamá: XlsxWriter no admite zona horaria), texto o número."""
        if valor is None or valor == "":
            h.write_blank(fila, col, None, formato)
        elif tipo == "fecha":
            h.write_datetime(fila, col, datetime.combine(valor, time()), formato)
        elif tipo == "fecha_hora":
            h.write_datetime(fila, col, valor.astimezone(ZONA_PANAMA).replace(tzinfo=None), formato)
        elif isinstance(valor, str):
            h.write_string(fila, col, valor, formato)
        else:
            h.write_number(fila, col, float(valor), formato)
