"""PDF de la boleta de recargo por atención fuera del horario laboral (2026-11-16).

Borrador con la identidad del sistema, como el PDF de la autorización: hay un
modelo en papel que lo reemplazará. La imprime el SNM y se la entrega a la
agencia para el cobro, así que no lleva nombres de funcionarios ni unidades
internas (quién la generó queda en la bitácora y en el historial interno). Una
boleta anulada sale con el sello ANULADA y el motivo. El tipo de operación va en
casillas, como en papel, con la respuesta a «¿Subir y bajar?» si el trámite la pide
(2026-11-16).
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core import identidad
from app.core.horario import TEXTO_HORARIO, ZONA_PANAMA, texto_costo
from app.informes.comun import COLOR_DENEGADA
from app.informes.pdf import color_pdf, obtener_fuentes, texto_pdf

TINTA    = color_pdf(identidad.TEXTO)
GRIS     = color_pdf(identidad.GRIS)
MARINO   = color_pdf(identidad.MARINO)
AMARILLO = color_pdf(identidad.AMARILLO)
BORDE    = color_pdf(identidad.BORDE)
FONDO    = color_pdf(identidad.FONDO)
CREMA    = color_pdf(identidad.CREMA)
ROJO     = color_pdf(COLOR_DENEGADA)

CONCEPTO = "Recargo por atención fuera del horario laboral"
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@dataclass
class DatosPdfBoleta:
    numero_oficio:    str
    monto:            Decimal
    numero_solicitud: str
    tipo_tramite:     str
    agencia:          str
    buque:            str | None
    imo:              str | None
    puesto:           str
    puesto_destino:   str | None   # cambio de puerto: el nuevo
    fecha_operacion:  date
    pasajeros:        int
    aprobada_en:      datetime
    generada_en:      datetime
    anulada_en:       datetime | None = None
    motivo_anulacion: str | None = None
    # El tipo de operación en casillas (2026-11-16): los trámites activos del catálogo, en
    # su orden; la X va en `tipo_tramite`.
    tipos_operacion:  list[str] = field(default_factory=list)
    # «¿Subir y bajar?»: None si el trámite no hace la pregunta.
    subir_y_bajar:    bool | None = None
    # Lo que la agencia eligió en el formulario, también en casillas (2026-11-18): la operación
    # del trámite de Técnico y los días del sellado de Shore Pass. Cada una es (rótulo,
    # opciones, elegida); una fila por cada una.
    elecciones: list[tuple[str, tuple[str, ...], str]] = field(default_factory=list)


def casillas_operacion(tipos: list[str], elegido: str) -> list[tuple[str, bool]]:
    """Cada tipo de operación con su marca, como las casillas de un formulario en papel.
    Si el de la solicitud ya no está entre los activos (Cambio de Puerto, desde el
    2026-11-13), va al final, marcado."""
    casillas = [(tipo, tipo == elegido) for tipo in tipos]
    if elegido not in tipos:
        casillas.append((elegido, True))
    return casillas


def _momento(valor: datetime) -> str:
    """«sábado 14/11/2026, 16:20»: en 24 horas, como el horario laboral."""
    local = valor.astimezone(ZONA_PANAMA)
    return f"{DIAS[local.weekday()]} {local:%d/%m/%Y, %H:%M}"


def _fuente_oficio(numero: str, negrita: str) -> str:
    """Letra de máquina (Courier) si el número cabe en su juego de caracteres; si no,
    la negrita con cobertura Unicode."""
    try:
        numero.encode("cp1252")
        return "Courier-Bold"
    except UnicodeEncodeError:
        return negrita


class _Documento(SimpleDocTemplate):
    """Con `encima`, lo que se dibuja sobre el contenido de cada página (el sello de
    una boleta anulada): onFirstPage dibuja antes y las tablas lo taparían."""

    def __init__(self, *args, encima=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._encima = encima

    def afterPage(self) -> None:
        if self._encima:
            self._encima(self.canv, self)


def generar_pdf_boleta(d: DatosPdfBoleta) -> bytes:
    normal, negrita = obtener_fuentes()

    def estilo(nombre: str, **kw) -> ParagraphStyle:
        base = {"fontName": normal, "fontSize": 9, "leading": 12, "textColor": TINTA}
        base.update(kw)
        return ParagraphStyle(nombre, **base)

    e_pais     = estilo("pais", fontSize=8, leading=10, textColor=GRIS)
    e_org      = estilo("org", fontName=negrita, fontSize=12.5, leading=15)
    e_seccion  = estilo("seccion", fontSize=8.5, leading=11, textColor=GRIS)
    e_rotulo   = estilo("rotulo", fontName=negrita, fontSize=7, leading=9, textColor=GRIS, alignment=TA_CENTER)
    e_oficio   = estilo("oficio", fontName=_fuente_oficio(d.numero_oficio, negrita), fontSize=12, leading=15,
                        textColor=MARINO, alignment=TA_CENTER)
    e_titulo   = estilo("titulo", fontName=negrita, fontSize=14, leading=18, alignment=TA_CENTER)
    e_sub      = estilo("sub", fontSize=10, leading=13, alignment=TA_CENTER, textColor=GRIS)
    e_etiqueta = estilo("etiqueta", fontName=negrita, fontSize=7, leading=9, textColor=GRIS)
    e_valor    = estilo("valor", fontSize=9.5, leading=12)
    e_cabecera = estilo("cabecera", fontName=negrita, fontSize=8, leading=10, textColor=colors.white)
    e_cab_der  = estilo("cabecera_der", fontName=negrita, fontSize=8, leading=10, textColor=colors.white,
                        alignment=TA_RIGHT)
    e_concepto = estilo("concepto", fontSize=10, leading=13)
    e_monto    = estilo("monto", fontName=negrita, fontSize=10, leading=13, alignment=TA_RIGHT)
    e_total    = estilo("total", fontName=negrita, fontSize=11, leading=14)
    e_total_m  = estilo("total_monto", fontName=negrita, fontSize=12, leading=15, alignment=TA_RIGHT)
    e_nota     = estilo("nota", fontSize=7.5, leading=10, textColor=GRIS)
    e_firma    = estilo("firma", fontSize=8, leading=10, textColor=GRIS, alignment=TA_CENTER)
    e_anulada  = estilo("anulada", fontName=negrita, fontSize=8.5, leading=11, textColor=ROJO, alignment=TA_CENTER)
    e_opcion   = estilo("opcion", fontSize=9, leading=11)
    e_elegida  = estilo("elegida", fontName=negrita, fontSize=9, leading=11)
    e_marca    = estilo("marca", fontName=negrita, fontSize=8, leading=9, textColor=MARINO, alignment=TA_CENTER)

    def sello_anulada(canvas, documento) -> None:
        # Cruzado sobre la página, encima de todo: que no se pueda usar para cobrar.
        canvas.saveState()
        canvas.setFillColor(ROJO)
        canvas.setFillAlpha(0.2)
        canvas.setFont(negrita, 96)
        canvas.translate(documento.pagesize[0] / 2, documento.pagesize[1] / 2)
        canvas.rotate(32)
        canvas.drawCentredString(0, -30, "ANULADA")
        canvas.restoreState()

    buffer = BytesIO()
    doc = _Documento(
        buffer, pagesize=letter, encima=sello_anulada if d.anulada_en else None,
        leftMargin=17 * mm, rightMargin=17 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
        title=f"Boleta de recargo {d.numero_solicitud}",
        author=identidad.INSTITUCION_COMPLETA,
        subject=CONCEPTO,
    )
    ancho = doc.width
    historia: list = []

    # ── Encabezado: logo · institución · número de oficio ──
    logo = Image(str(identidad.LOGO_SNM), width=19 * mm, height=19 * mm, kind="proportional") \
        if identidad.LOGO_SNM.exists() else ""
    institucion = [
        Paragraph("REPÚBLICA DE PANAMÁ", e_pais),
        Paragraph(identidad.INSTITUCION.upper(), e_org),
        Paragraph("Sección de Autorizaciones Marítimas", e_seccion),
    ]
    oficio = Table([[Paragraph("N.º DE OFICIO", e_rotulo)], [Paragraph(texto_pdf(d.numero_oficio), e_oficio)]],
                   colWidths=[46 * mm])
    oficio.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, MARINO),
        ("BACKGROUND", (0, 0), (-1, -1), CREMA),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    encabezado = Table([[logo, institucion, oficio]], colWidths=[23 * mm, ancho - 23 * mm - 48 * mm, 48 * mm])
    encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    franja = Table([[""]], colWidths=[ancho], rowHeights=[2.2])
    franja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMARILLO)]))
    historia += [encabezado, Spacer(1, 3 * mm), franja, Spacer(1, 6 * mm)]

    # ── Título ──
    historia += [
        Paragraph("BOLETA DE RECARGO POR ATENCIÓN<br/>FUERA DEL HORARIO LABORAL", e_titulo),
        Spacer(1, 1.5 * mm),
        # El trámite va abajo, en las casillas del tipo de operación.
        Paragraph(f"Autorización Marítima N° {texto_pdf(d.numero_solicitud)}", e_sub),
        Spacer(1, 5 * mm),
    ]

    if d.anulada_en:
        anulada = Table(
            [[Paragraph(f"BOLETA ANULADA EL {_momento(d.anulada_en).upper()} — "
                        f"MOTIVO: {texto_pdf(d.motivo_anulacion)}", e_anulada)]],
            colWidths=[ancho],
        )
        anulada.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        historia += [anulada, Spacer(1, 3 * mm)]

    # ── Tipo de operación, en casillas como en papel (2026-11-16) ──
    def casilla(marcada: bool) -> Table:
        cuadro = Table([[Paragraph("X" if marcada else "", e_marca)]], colWidths=[3.8 * mm], rowHeights=[3.8 * mm])
        cuadro.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, MARINO if marcada else GRIS),
            ("BACKGROUND", (0, 0), (-1, -1), CREMA if marcada else colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return cuadro

    def opcion(texto: str, marcada: bool) -> list:
        return [casilla(marcada), Paragraph(texto_pdf(texto), e_elegida if marcada else e_opcion)]

    sin_bordes = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    util = ancho - 14   # el recuadro lleva 7 pt de margen a cada lado
    elegibles = [opcion(tipo, marcada) for tipo, marcada in casillas_operacion(d.tipos_operacion, d.tipo_tramite)]
    if len(elegibles) % 2:
        elegibles.append(["", ""])
    opciones = Table([elegibles[i] + elegibles[i + 1] for i in range(0, len(elegibles), 2)],
                     colWidths=[6 * mm, util / 2 - 6 * mm, 6 * mm, util / 2 - 6 * mm])
    opciones.setStyle(TableStyle(sin_bordes))
    contenido = [[Paragraph("TIPO DE OPERACIÓN", e_etiqueta)], [opciones]]
    if d.subir_y_bajar is not None:
        respuesta = Table([[Paragraph("SUBIR Y BAJAR", e_etiqueta), *opcion("Sí", d.subir_y_bajar),
                            *opcion("No", not d.subir_y_bajar)]],
                          colWidths=[30 * mm, 6 * mm, 16 * mm, 6 * mm, 16 * mm], hAlign="LEFT")
        respuesta.setStyle(TableStyle(sin_bordes))
        contenido.append([respuesta])
    for rotulo, opciones_eleccion, elegida in d.elecciones:
        celdas, anchos = [Paragraph(rotulo, e_etiqueta)], [30 * mm]
        for texto in opciones_eleccion:
            celdas += opcion(texto, texto == elegida)
            anchos += [6 * mm, 30 * mm]
        fila = Table([celdas], colWidths=anchos, hAlign="LEFT")
        fila.setStyle(TableStyle(sin_bordes))
        contenido.append([fila])
    operacion = Table(contenido, colWidths=[ancho])
    operacion.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), FONDO),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        *([("LINEABOVE", (0, 2), (-1, -1), 0.4, BORDE)] if len(contenido) > 2 else []),
    ]))
    historia += [operacion, Spacer(1, 3 * mm)]

    # ── Datos de la solicitud (rejilla de dos columnas) ──
    puesto = f"{d.puesto} → {d.puesto_destino}" if d.puesto_destino else d.puesto
    buque = " · IMO ".join(x for x in (d.buque, d.imo) if x) or None
    pares = [
        ("AGENCIA NAVIERA", texto_pdf(d.agencia)),
        ("PUESTO DE CONTROL", texto_pdf(puesto)),
        ("BUQUE", texto_pdf(buque)),
        ("FECHA DE LA OPERACIÓN", f"{d.fecha_operacion:%d/%m/%Y}"),
        ("TRIPULANTES", str(d.pasajeros)),
        ("APROBADA EL", _momento(d.aprobada_en)),
        ("HORARIO LABORAL", texto_pdf(TEXTO_HORARIO)),
        ("BOLETA GENERADA EL", _momento(d.generada_en)),
    ]
    filas = [
        [[Paragraph(etiqueta, e_etiqueta), Paragraph(valor, e_valor)] for etiqueta, valor in pares[i:i + 2]]
        for i in range(0, len(pares), 2)
    ]
    datos = Table(filas, colWidths=[ancho / 2, ancho / 2])
    datos.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), FONDO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    historia += [datos, Spacer(1, 6 * mm)]

    # ── Concepto y monto ──
    monto = texto_pdf(texto_costo(d.monto))
    cobro = Table(
        [
            [Paragraph("CONCEPTO", e_cabecera), Paragraph("MONTO", e_cab_der)],
            [Paragraph(CONCEPTO, e_concepto), Paragraph(monto, e_monto)],
            [Paragraph("TOTAL A PAGAR", e_total), Paragraph(monto, e_total_m)],
        ],
        colWidths=[ancho - 40 * mm, 40 * mm],
    )
    cobro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MARINO),
        ("BACKGROUND", (0, 2), (-1, 2), CREMA),
        ("BOX", (0, 0), (-1, -1), 0.8, MARINO),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, MARINO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    historia += [
        cobro,
        Spacer(1, 2 * mm),
        Paragraph(f"La solicitud se aprobó fuera del horario laboral ({texto_pdf(TEXTO_HORARIO)}).", e_nota),
        Spacer(1, 16 * mm),
    ]

    # ── Firmas ──
    firmas = Table(
        [["", "", ""],
         [Paragraph(f"Firma y sello del {texto_pdf(identidad.INSTITUCION)}", e_firma), "",
          Paragraph("Recibido por la agencia naviera (nombre y firma)", e_firma)]],
        colWidths=[(ancho - 14 * mm) / 2, 14 * mm, (ancho - 14 * mm) / 2],
        rowHeights=[16 * mm, None],
    )
    firmas.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.8, TINTA),
        ("LINEBELOW", (2, 0), (2, 0), 0.8, TINTA),
        ("TOPPADDING", (0, 1), (-1, 1), 3),
    ]))
    historia.append(firmas)

    def pagina(canvas, documento) -> None:
        canvas.saveState()
        canvas.setStrokeColor(AMARILLO)
        canvas.setLineWidth(1.2)
        canvas.line(documento.leftMargin, 13 * mm, documento.leftMargin + documento.width, 13 * mm)
        canvas.setFont(normal, 7)
        canvas.setFillColor(GRIS)
        canvas.drawString(
            documento.leftMargin, 9 * mm,
            f"Boleta de recargo — oficio N.º {d.numero_oficio} — Autorización Marítima N° {d.numero_solicitud}",
        )
        canvas.drawRightString(documento.leftMargin + documento.width, 9 * mm, identidad.SISTEMA)
        canvas.restoreState()

    doc.build(historia, onFirstPage=pagina, onLaterPages=pagina)
    return buffer.getvalue()
