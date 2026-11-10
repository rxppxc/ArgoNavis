"""El informe de estadísticas en PDF (carta vertical), con reportlab.

La misma identidad del PDF de la autorización: el escudo del SNM, la
institución, la franja amarilla y el pie con la línea amarilla; a la derecha,
el logo de ARGO NAVIS (donde la autorización lleva el QR). Después: las
cifras del periodo en recuadros, el estado actual en una barra, la serie
(por día, mes o año, la que se veía en pantalla) en columnas con su tabla,
los trámites y los puestos con barras dentro de la tabla, el mapa de horas
con el horario laboral recuadrado, la lista de fuera del horario y el uso
del sistema.

Gráficos dibujados a mano (como en la pantalla): marcas finas, 1 pt del fondo
entre segmentos, rejilla tenue y el texto siempre en marino o gris; el color
de cada serie va en la marca, nunca en las letras.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as lienzo_pdf
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.core.horario import ZONA_PANAMA
from app.core.informe_estadisticas import (
    AMARILLO, BORDE, COLOR_APROBADA, COLOR_EXPIRADA, COLOR_FINALIZADA, COLOR_RECIBIDAS, COLUMNAS_SERIE,
    DIAS_CORTOS, FONDO, GRIS, HORA_FIN_LABORAL, HORA_INICIO_LABORAL, INSTITUCION, LOGO_ARGO_NAVIS, LOGO_SNM,
    MARINO, NIVELES_CALOR, SECCION, SERIES_DIBUJADAS, SISTEMA, TEXTO, TITULO, UNIDADES, USO_INTERNO, DatosInforme,
    cifra, color_nivel, estados, fecha_hora, indicadores, matriz_horas, nivel_calor, ordenados_por_tramite,
    por_finalizar, porcentaje, puestos_con_aprobadas, rotulo_periodo, serie, tamano,
)
from app.core.pdf_autorizacion import obtener_fuentes

_MARGEN = 17 * mm
_REJILLA = "#E3E9F0"
_TEXTO_2 = "#3E4C5E"


def _c(hexa: str):
    return colors.HexColor(hexa)


def _t(texto: str | None) -> str:
    """Texto listo para un Paragraph (que interpreta marcado)."""
    return escape(texto) if texto else "—"


def _escala(maximo: int, marcas: int = 4) -> tuple[int, list[int]]:
    """Un tope redondo (pasos de 1, 2 o 5 × 10ⁿ, nunca menores que 1) y sus marcas,
    como escalaEje en la pantalla."""
    if maximo <= 0:
        return 1, [0, 1]
    crudo = maximo / marcas
    potencia = 10 ** len(str(int(crudo))) // 10 if crudo >= 1 else 1
    paso = next((m * potencia for m in (1, 2, 5, 10) if m * potencia >= crudo), 10 * potencia)
    paso = max(1, paso)
    tope = -(-maximo // paso) * paso
    return tope, list(range(0, tope + 1, paso))


def _lienzo(pie: str, encabezado: str, fuente: str):
    """El lienzo que numera las páginas («Página 2 de 4») y dibuja el pie con la
    línea amarilla y, desde la segunda página, un encabezado discreto."""

    class Lienzo(lienzo_pdf.Canvas):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._paginas: list[dict] = []

        def showPage(self) -> None:   # noqa: N802 (nombre de reportlab)
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                self._marco(total)
                super().showPage()
            super().save()

        def _marco(self, total: int) -> None:
            ancho, alto = self._pagesize
            self.saveState()
            self.setStrokeColor(_c(AMARILLO))
            self.setLineWidth(1.2)
            self.line(_MARGEN, 13 * mm, ancho - _MARGEN, 13 * mm)
            self.setFont(fuente, 7)
            self.setFillColor(_c(GRIS))
            self.drawString(_MARGEN, 9 * mm, pie)
            self.drawRightString(ancho - _MARGEN, 9 * mm, f"Página {self._pageNumber} de {total}")
            if self._pageNumber > 1:
                self.drawString(_MARGEN, alto - 9 * mm, encabezado)
                self.setStrokeColor(_c(BORDE))
                self.setLineWidth(0.5)
                self.line(_MARGEN, alto - 10.5 * mm, ancho - _MARGEN, alto - 10.5 * mm)
            self.restoreState()

    return Lienzo


class _Pdf:
    def __init__(self, datos: DatosInforme) -> None:
        self.d = datos
        self.e = datos.estadisticas
        self.normal, self.negrita = obtener_fuentes()
        n, b = self.normal, self.negrita

        def estilo(nombre: str, **kw) -> ParagraphStyle:
            return ParagraphStyle(nombre, **{"fontName": n, "fontSize": 9, "leading": 12, "textColor": _c(TEXTO), **kw})

        self.e_pais = estilo("pais", fontSize=8, leading=10, textColor=_c(GRIS))
        self.e_org = estilo("org", fontName=b, fontSize=12.5, leading=15)
        self.e_seccion = estilo("seccion", fontSize=8.5, leading=11, textColor=_c(GRIS))
        self.e_titulo = estilo("titulo", fontName=b, fontSize=15, leading=19, alignment=TA_CENTER)
        self.e_periodo = estilo("periodo", fontName=b, fontSize=11, leading=14, alignment=TA_CENTER, textColor=_c(MARINO))
        self.e_meta = estilo("meta", fontSize=7.5, leading=10, alignment=TA_CENTER, textColor=_c(GRIS))
        self.e_subtit = estilo("subtitulo", fontName=b, fontSize=10.5, leading=13, textColor=_c(MARINO),
                               spaceBefore=10, spaceAfter=2)
        self.e_nota = estilo("nota", fontSize=7.5, leading=10, textColor=_c(GRIS), spaceAfter=5)
        self.e_etiqueta = estilo("etiqueta", fontName=b, fontSize=7.5, leading=9.5, textColor=_c(_TEXTO_2))
        self.e_valor = estilo("valor", fontName=b, fontSize=17, leading=20, textColor=_c(MARINO))
        self.e_contexto = estilo("contexto", fontSize=7, leading=9, textColor=_c(_TEXTO_2))
        self.e_cabecera = estilo("cabecera", fontName=b, fontSize=7.5, leading=9.5, textColor=colors.white)
        self.e_cabecera_d = estilo("cabecera_d", fontName=b, fontSize=7.5, leading=9.5, textColor=colors.white,
                                   alignment=TA_RIGHT)
        self.e_celda = estilo("celda", fontSize=8, leading=10)
        self.e_numero = estilo("numero", fontSize=8, leading=10, alignment=TA_RIGHT)
        self.e_leyenda = estilo("leyenda", fontSize=7.5, leading=10, textColor=_c(_TEXTO_2))
        self.e_vacio = estilo("vacio", fontSize=8, leading=11, textColor=_c(GRIS))

    # ── Piezas ───────────────────────────────────────────────────────────────

    def ancho(self) -> float:
        return letter[0] - 2 * _MARGEN

    def seccion(self, titulo: str, nota: str | None, *contenido, partir: bool = False) -> KeepTogether | list:
        """Un título con su nota y su contenido, sin separarse de página. Con `partir`
        (tablas que pueden ser largas), solo se pide lugar para el título y unas
        filas: si no, la sección entera pasaba a la página siguiente y dejaba un hueco."""
        partes = [Paragraph(escape(titulo), self.e_subtit)]
        if nota:
            partes.append(Paragraph(escape(nota), self.e_nota))
        else:
            partes.append(Spacer(1, 4))
        if partir:
            return [CondPageBreak(42 * mm), *partes, *contenido]
        return KeepTogether([*partes, *contenido])

    def agregar(self, historia: list, parte: KeepTogether | list) -> None:
        historia.extend(parte if isinstance(parte, list) else [parte])

    def tabla(self, encabezados: list[str], filas: list[list], anchos: list[float], derecha: set[int],
              colores: list[str] | None = None) -> Table:
        """Encabezados en marino con letra blanca y filas alternas, como la tabla de
        tripulantes de la autorización. `derecha`: las columnas con cifras."""
        datos = [[Paragraph(escape(t), self.e_cabecera_d if i in derecha else self.e_cabecera)
                  for i, t in enumerate(encabezados)]]
        for fila in filas:
            celdas = []
            for i, v in enumerate(fila):
                if isinstance(v, (Drawing, Paragraph)):
                    celdas.append(v)
                else:
                    celdas.append(Paragraph(escape(str(v)), self.e_numero if i in derecha else self.e_celda))
            datos.append(celdas)
        t = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), _c(MARINO)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _c(FONDO)]),
            ("BOX", (0, 0), (-1, -1), 0.6, _c(BORDE)),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, _c(BORDE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]
        for n, color in enumerate(colores or [], start=1):
            estilo.append(("LINEBEFORE", (0, n), (0, n), 3, _c(color)))
        t.setStyle(TableStyle(estilo))
        return t

    def vacio(self, texto: str = "Sin datos en el periodo.") -> Paragraph:
        return Paragraph(texto, self.e_vacio)

    def barra(self, segmentos: list[tuple[int, str]], maximo: int, ancho: float, alto: float = 7) -> Drawing:
        """Una barra horizontal (partida en segmentos) para una celda de tabla."""
        d = Drawing(ancho, alto + 2)
        total = sum(v for v, _ in segmentos)
        largo = ancho * total / maximo if maximo else 0
        x = 0.0
        for valor, color in segmentos:
            if valor <= 0 or total <= 0:
                continue
            w = largo * valor / total
            d.add(Rect(x, 1, max(w - 1, 0.8), alto, fillColor=_c(color), strokeColor=None))
            x += w
        return d

    def muestra(self, color: str, texto: str, ancho: float) -> Table:
        """Una entrada de leyenda: el cuadrito de color y su texto."""
        cuadro = Drawing(8, 8)
        cuadro.add(Rect(0, 0.5, 7, 7, rx=1.5, ry=1.5, fillColor=_c(color), strokeColor=None))
        t = Table([[cuadro, Paragraph(texto, self.e_leyenda)]], colWidths=[10, ancho - 10])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return t

    def leyenda(self, entradas: list[tuple[str, str]], columnas: int) -> Table:
        ancho = self.ancho() / columnas
        filas, fila = [], []
        for color, texto in entradas:
            fila.append(self.muestra(color, texto, ancho))
            if len(fila) == columnas:
                filas.append(fila)
                fila = []
        if fila:
            filas.append(fila + [""] * (columnas - len(fila)))
        t = Table(filas, colWidths=[ancho] * columnas)
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        return t

    # ── Encabezado y cifras ──────────────────────────────────────────────────

    def encabezado(self) -> list:
        ancho = self.ancho()
        escudo = Image(str(LOGO_SNM), width=19 * mm, height=19 * mm, kind="proportional") if LOGO_SNM.exists() else ""
        logo = Image(str(LOGO_ARGO_NAVIS), width=25 * mm, height=22 * mm, kind="proportional") \
            if LOGO_ARGO_NAVIS.exists() else ""
        institucion = [
            Paragraph("REPÚBLICA DE PANAMÁ", self.e_pais),
            Paragraph(INSTITUCION.upper(), self.e_org),
            Paragraph(escape(SECCION), self.e_seccion),
        ]
        t = Table([[escudo, institucion, logo]], colWidths=[23 * mm, ancho - 23 * mm - 28 * mm, 28 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        franja = Table([[""]], colWidths=[ancho], rowHeights=[2.2])
        franja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _c(AMARILLO))]))
        return [
            t, Spacer(1, 3 * mm), franja, Spacer(1, 5 * mm),
            Paragraph(TITULO.upper(), self.e_titulo),
            Paragraph(escape(self.d.periodo), self.e_periodo),
            Spacer(1, 1.5 * mm),
            Paragraph(f"Generado el {escape(self.d.generado)} · {USO_INTERNO}", self.e_meta),
            Spacer(1, 3 * mm),
        ]

    def recuadro(self, etiqueta: str, valor: str, contexto: str, color: str, ancho: float) -> Table:
        t = Table([[Paragraph(escape(etiqueta), self.e_etiqueta)], [Paragraph(escape(valor), self.e_valor)],
                   [Paragraph(escape(contexto) or "&nbsp;", self.e_contexto)]], colWidths=[ancho])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _c(FONDO)),
            ("BOX", (0, 0), (-1, -1), 0.5, _c(BORDE)),
            ("LINEBEFORE", (0, 0), (0, -1), 3, _c(color)),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ]))
        return t

    def cifras(self) -> list:
        lista = indicadores(self.e)
        separacion = 2.5 * mm

        def fila_de(items) -> Table:
            ancho = (self.ancho() - separacion * (len(items) - 1)) / len(items)
            celdas = []
            for i in items:
                # Sin base (ninguna recibida o aprobada), sin porcentaje: «— de las recibidas» confundía.
                contexto = i.base if i.horas else (
                    f"{porcentaje(i.parte, i.total)} {i.base}" if i.total and i.parte is not None else "")
                celdas.append(self.recuadro(i.etiqueta, i.texto, contexto, i.color, ancho))
            t = Table([celdas], colWidths=[ancho + (separacion if n < len(items) - 1 else 0)
                                           for n in range(len(items))])
            t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), separacion),
                                   ("RIGHTPADDING", (-1, 0), (-1, 0), 0), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            return t

        return [self.seccion("Cifras del periodo", None, fila_de(lista[:4])), Spacer(1, separacion), fila_de(lista[4:])]

    def estado_actual(self) -> list:
        lista = estados(self.e)
        suma = sum(x.total for x in lista)
        titulo, nota = "Estado actual de las solicitudes recibidas", "En qué estado están hoy las que llegaron en el periodo."
        if not suma:
            return [self.seccion(titulo, nota, self.vacio())]
        ancho = self.ancho()
        d = Drawing(ancho, 14)
        x = 0.0
        for estado in lista:
            if not estado.total:
                continue
            w = ancho * estado.total / suma
            # 1,5 pt del fondo entre segmentos, como los 2 px de la pantalla.
            d.add(Rect(x, 0, max(w - 1.5, 1.2), 14, fillColor=_c(estado.color), strokeColor=None))
            x += w
        entradas = [(x.color, f"<b>{escape(x.etiqueta)}</b>  {cifra(x.total)} · {porcentaje(x.total, suma)}")
                    for x in lista]
        return [self.seccion(titulo, nota, d, Spacer(1, 2.5 * mm), self.leyenda(entradas, 3))]

    # ── Serie ────────────────────────────────────────────────────────────────

    def grafico_serie(self, filas, compacto: bool) -> Drawing:
        ancho, alto = self.ancho(), 62 * mm
        izquierda, abajo, arriba = 22.0, 20.0, 12.0
        area_w, area_h = ancho - izquierda, alto - abajo - arriba
        d = Drawing(ancho, alto)
        maximo = max((getattr(f, clave) for f in filas for clave, _, _ in SERIES_DIBUJADAS), default=0)
        tope, marcas = _escala(maximo)
        for m in marcas:
            y = abajo + area_h * m / tope
            d.add(Line(izquierda, y, ancho, y, strokeColor=_c(BORDE if m == 0 else _REJILLA), strokeWidth=0.6))
            d.add(String(izquierda - 4, y - 2.3, cifra(m), fontName=self.normal, fontSize=6.5,
                         fillColor=_c(GRIS), textAnchor="end"))
        n = len(filas)
        grupo = area_w / n
        separacion = 0.8 if compacto else 1.5
        columna = min(10.0, (grupo * (0.82 if compacto else 0.7) - 2 * separacion) / 3)
        for i, f in enumerate(filas):
            x = izquierda + i * grupo + (grupo - (3 * columna + 2 * separacion)) / 2
            for clave, _, color in SERIES_DIBUJADAS:
                valor = getattr(f, clave)
                alto_col = area_h * valor / tope
                if valor:
                    radio = min(1.6, columna / 2, alto_col / 2)
                    d.add(Rect(x, abajo, columna, alto_col, rx=radio, ry=radio, fillColor=_c(color), strokeColor=None))
                    # Base recta: la punta redondeada va solo arriba.
                    d.add(Rect(x, abajo, columna, min(alto_col, radio), fillColor=_c(color), strokeColor=None))
                if clave == "recibidas" and valor and not compacto:
                    d.add(String(x + columna / 2, abajo + alto_col + 2.5, cifra(valor), fontName=self.negrita,
                                 fontSize=6.5, fillColor=_c(_TEXTO_2), textAnchor="middle"))
                x += columna + separacion
            arriba_txt, abajo_txt, _ = rotulo_periodo(f.periodo)
            centro = izquierda + i * grupo + grupo / 2
            # Por día, el mes va solo en el primero y donde empieza uno nuevo.
            if compacto and i > 0 and arriba_txt != "1":
                abajo_txt = ""
            if compacto and n > 16 and i % 2 and arriba_txt != "1":
                arriba_txt = ""   # con muchos días, uno sí y uno no
            d.add(String(centro, abajo - 8.5, arriba_txt, fontName=self.negrita, fontSize=6.5 if compacto else 7,
                         fillColor=_c(_TEXTO_2), textAnchor="middle"))
            if abajo_txt:
                d.add(String(centro, abajo - 16, abajo_txt, fontName=self.normal, fontSize=6, fillColor=_c(GRIS),
                             textAnchor="middle"))
        return d

    def serie(self) -> list:
        unidad = self.d.unidad
        columna, titulo = UNIDADES[unidad]
        filas = serie(self.e, unidad)
        alcance = {"dia": "los últimos 31 días del periodo, como mucho",
                   "mes": "los meses del periodo, hasta los últimos 12",
                   "anio": "los años del periodo, hasta los últimos 10"}[unidad]
        nota = f"Cada cifra cuenta en la fecha en que ocurrió; {alcance}."
        if not filas or not any(f.recibidas or f.aprobadas or f.finalizadas or f.negadas or f.expiradas for f in filas):
            return [self.seccion(titulo, nota, self.vacio("Sin movimiento en el periodo."))]
        leyenda = self.leyenda([(color, nombre) for _, nombre, color in SERIES_DIBUJADAS], 6)
        ancho = self.ancho()
        anchos = [ancho * 0.31] + [ancho * 0.69 / len(COLUMNAS_SERIE)] * len(COLUMNAS_SERIE)
        tabla = self.tabla([columna, *(n for _, n in COLUMNAS_SERIE)],
                           [[rotulo_periodo(f.periodo)[2], *(cifra(getattr(f, c)) for c, _ in COLUMNAS_SERIE)]
                            for f in filas],
                           anchos, derecha=set(range(1, len(COLUMNAS_SERIE) + 1)))
        return [self.seccion(titulo, nota, leyenda, self.grafico_serie(filas, compacto=unidad == "dia")),
                Spacer(1, 2 * mm), CondPageBreak(30 * mm), tabla]

    # ── Trámites, puestos, horas, fuera del horario y uso ────────────────────

    def tramites(self) -> list:
        lista = ordenados_por_tramite(self.e)
        titulo, nota = "Por trámite", "Solicitudes recibidas en el periodo, por tipo de trámite."
        if not lista:
            return [self.seccion(titulo, nota, self.vacio())]
        ancho = self.ancho()
        anchos = [ancho * p for p in (0.34, 0.22, 0.09, 0.09, 0.09, 0.08, 0.09)]
        maximo = max(t.recibidas for t in lista)
        filas = [[Paragraph(_t(t.nombre), self.e_celda), self.barra([(t.recibidas, COLOR_RECIBIDAS)], maximo, anchos[1] - 8),
                  cifra(t.recibidas), cifra(t.aprobadas), porcentaje(t.aprobadas, t.recibidas), cifra(t.negadas),
                  cifra(t.expiradas)] for t in lista]
        tabla = self.tabla(["Trámite", "", "Recibidas", "Aprobadas", "% aprob.", "Denegadas", "Expiradas"], filas,
                           anchos, derecha={2, 3, 4, 5, 6})
        return self.seccion(titulo, nota, tabla, partir=True)

    def puestos(self) -> list:
        lista = puestos_con_aprobadas(self.e)
        titulo, nota = "Por puesto de control", "Las autorizaciones aprobadas para cada puesto y en qué terminaron."
        if not lista:
            return [self.seccion(titulo, nota, self.vacio("Sin autorizaciones aprobadas en el periodo."))]
        ancho = self.ancho()
        anchos = [ancho * p for p in (0.30, 0.26, 0.11, 0.11, 0.11, 0.11)]
        maximo = max(p.aprobadas for p in lista)
        filas = [[Paragraph(_t(p.puesto), self.e_celda),
                  self.barra([(p.finalizadas, COLOR_FINALIZADA), (por_finalizar(p), COLOR_APROBADA),
                              (p.expiradas, COLOR_EXPIRADA)], maximo, anchos[1] - 8),
                  cifra(p.aprobadas), cifra(p.finalizadas), cifra(por_finalizar(p)), cifra(p.expiradas)] for p in lista]
        leyenda = self.leyenda([(COLOR_FINALIZADA, "Finalizadas"), (COLOR_APROBADA, "Por finalizar"),
                                (COLOR_EXPIRADA, "Expiradas")], 6)
        tabla = self.tabla(["Puesto", "", "Aprobadas", "Finalizadas", "Por finalizar", "Expiradas"], filas, anchos,
                           derecha={2, 3, 4, 5})
        return self.seccion(titulo, nota, leyenda, Spacer(1, 1.5 * mm), tabla, partir=True)

    def mapa_horas(self) -> list:
        e = self.e
        titulo = "Hora de aprobación de UCVMM"
        nota = (f"Aprobadas por día y hora, en hora de Panamá. Recuadro: horario laboral ({e.horario_laboral}; "
                "desde las 15:01 es fuera).")
        if not e.aprobadas:
            return [self.seccion(titulo, nota, self.vacio("Ninguna autorización aprobada en el periodo."))]
        matriz = matriz_horas(e)
        maximo = max(max(f) for f in matriz)
        ancho = self.ancho()
        izquierda, separacion, alto_celda = 22.0, 1.2, 11.5
        celda = (ancho - izquierda) / 24
        alto = 12 + 7 * (alto_celda + separacion) + 22
        d = Drawing(ancho, alto)
        tope = alto - 9
        for hora in range(24):
            d.add(String(izquierda + hora * celda + celda / 2, tope + 1, f"{hora:02d}", fontName=self.normal,
                         fontSize=6, fillColor=_c(GRIS), textAnchor="middle"))
        for dia in range(1, 8):
            y = tope - 4 - dia * (alto_celda + separacion)
            d.add(String(0, y + 3, DIAS_CORTOS[dia - 1], fontName=self.negrita, fontSize=7, fillColor=_c(_TEXTO_2)))
            for hora in range(24):
                total = matriz[dia - 1][hora]
                nivel = nivel_calor(total, maximo)
                x = izquierda + hora * celda
                d.add(Rect(x, y, celda - separacion, alto_celda, rx=1.2, ry=1.2, fillColor=_c(color_nivel(nivel)),
                           strokeColor=None))
                if total:
                    d.add(String(x + (celda - separacion) / 2, y + 3.4, cifra(total), fontName=self.negrita,
                                 fontSize=6, fillColor=colors.white if nivel >= 4 else _c(TEXTO), textAnchor="middle"))
        # El recuadro del horario laboral (lunes a viernes, de 07 a 14).
        y_lunes = tope - 4 - 1 * (alto_celda + separacion)
        y_viernes = tope - 4 - 5 * (alto_celda + separacion)
        x0 = izquierda + HORA_INICIO_LABORAL * celda
        x1 = izquierda + HORA_FIN_LABORAL * celda - separacion
        d.add(Rect(x0 - 1.4, y_viernes - 1.4, x1 - x0 + 2.8, y_lunes + alto_celda - y_viernes + 2.8, rx=2.5, ry=2.5,
                   fillColor=None, strokeColor=_c(TEXTO), strokeWidth=1.3))
        # La escala, debajo.
        y = 4
        d.add(String(izquierda, y + 1.5, "Menos", fontName=self.normal, fontSize=6.5, fillColor=_c(GRIS)))
        x = izquierda + 22
        for n in range(NIVELES_CALOR + 1):
            d.add(Rect(x, y, 8, 8, rx=1.2, ry=1.2, fillColor=_c(color_nivel(n)), strokeColor=None))
            x += 9.5
        d.add(String(x + 2, y + 1.5, "Más", fontName=self.normal, fontSize=6.5, fillColor=_c(GRIS)))
        x += 34
        d.add(Rect(x, y, 12, 8, rx=1.5, ry=1.5, fillColor=None, strokeColor=_c(TEXTO), strokeWidth=1.1))
        d.add(String(x + 16, y + 1.5, "Horario laboral", fontName=self.normal, fontSize=6.5, fillColor=_c(GRIS)))
        resumen = Paragraph(
            f"<b>{cifra(e.aprobadas_fuera_horario)}</b> de {cifra(e.aprobadas)} aprobadas fueron fuera del horario "
            f"laboral (<b>{porcentaje(e.aprobadas_fuera_horario, e.aprobadas)}</b>).", self.e_celda)
        return [self.seccion(titulo, nota, resumen, Spacer(1, 2 * mm), d)]

    def fuera_del_horario(self) -> list:
        e = self.e
        lista = e.operaciones_fuera_horario
        titulo = "Autorizaciones aprobadas fuera del horario"
        nota = "Cuenta la hora de la aprobación de UCVMM."
        if e.aprobadas_fuera_horario > len(lista):
            nota += f" Se muestran las {len(lista)} más recientes de {cifra(e.aprobadas_fuera_horario)}."
        if not lista:
            return [self.seccion(titulo, nota, self.vacio("Ninguna en el periodo."))]
        ancho = self.ancho()
        anchos = [ancho * p for p in (0.15, 0.25, 0.19, 0.21, 0.20)]
        filas = [[o.numero or f"#{o.id}", Paragraph(_t(o.tipo_tramite), self.e_celda), Paragraph(_t(o.puesto), self.e_celda),
                  fecha_hora(o.aprobada_en.astimezone(ZONA_PANAMA)), Paragraph(_t(o.aprobada_por), self.e_celda)]
                 for o in lista]
        tabla = self.tabla(["Solicitud", "Trámite", "Puesto", "Aprobada el", "Aprobada por"], filas, anchos, derecha={3})
        return self.seccion(titulo, nota, tabla, partir=True)

    def uso(self) -> list:
        uso = self.d.uso
        ancho = self.ancho()
        separacion = 2.5 * mm
        a = (ancho - 3 * separacion) / 4
        activos = f"{cifra(uso.usuarios_activos)} activos ({porcentaje(uso.usuarios_activos, uso.usuarios)})"
        recuadros = [
            self.recuadro("Usuarios registrados", cifra(uso.usuarios), activos, COLOR_RECIBIDAS, a),
            self.recuadro("Agencias navieras", cifra(uso.agencias), "", GRIS, a),
            self.recuadro("Documentos en expedientes", cifra(uso.documentos), "", GRIS, a),
            self.recuadro("Almacenamiento usado", tamano(uso.almacenamiento_bytes), "", GRIS, a),
        ]
        fila = Table([recuadros], colWidths=[a + separacion] * 3 + [a])
        fila.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), separacion),
                                  ("RIGHTPADDING", (-1, 0), (-1, 0), 0), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        partes: list = [self.seccion("Uso del sistema", "Totales a hoy: no dependen del periodo.", fila)]
        if uso.top_agencias:
            anchos = [ancho * p for p in (0.42, 0.43, 0.15)]
            maximo = max(x.total for x in uso.top_agencias)
            filas = [[Paragraph(_t(x.nombre), self.e_celda), self.barra([(x.total, COLOR_RECIBIDAS)], maximo, anchos[1] - 8),
                      cifra(x.total)] for x in uso.top_agencias]
            partes.append(self.seccion("Agencias con más solicitudes", "Las cinco con más solicitudes, desde el inicio.",
                                       self.tabla(["Agencia", "", "Solicitudes"], filas, anchos, derecha={2})))
        return partes

    def generar(self) -> bytes:
        salida = BytesIO()
        doc = SimpleDocTemplate(
            salida, pagesize=letter, leftMargin=_MARGEN, rightMargin=_MARGEN, topMargin=14 * mm, bottomMargin=19 * mm,
            title=f"{TITULO} — {self.d.periodo}", author="Servicio Nacional de Migración de Panamá",
            subject=USO_INTERNO, creator=SISTEMA,
        )
        historia: list = []
        for parte in (self.encabezado(), self.cifras(), self.estado_actual(), self.serie(), self.tramites(),
                      self.puestos(), self.mapa_horas(), self.fuera_del_horario(), self.uso()):
            for pieza in parte if isinstance(parte, list) else [parte]:
                self.agregar(historia, pieza)
        pie = f"{SISTEMA} · Generado el {self.d.generado} · {USO_INTERNO}"
        encabezado = f"{TITULO} · {self.d.periodo}"
        doc.build(historia, canvasmaker=_lienzo(pie, encabezado, self.normal))
        return salida.getvalue()


def generar(datos: DatosInforme) -> bytes:
    return _Pdf(datos).generar()
