"""PDF de la boleta de recargo por atención fuera del horario laboral (2026-11-16).

Desde el 2026-11-26 sigue el modelo en papel de UCVMM, el Formulario No. 4 «Autorización
fuera del horario laboral», con el encabezado y el pie del formato de documentos de la DTI
(los de los manuales). Lo pidió el usuario. Arriba van el número de oficio, que escribe el
funcionario, y el número de la solicitud. El tipo de operación va en casillas: los trámites
del sistema, con la X en el de la solicitud y, entre paréntesis, lo que eligió la agencia (la
operación de Técnico, los días del sellado). La firma es del jefe encargado del sector de
UCVMM de la solicitud, sin su nombre: la boleta la imprime el SNM y se la entrega a la agencia.
Una boleta anulada sale con el sello ANULADA y el motivo.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core import identidad
from app.core.horario import ZONA_PANAMA, texto_costo
from app.informes.comun import COLOR_DENEGADA, fecha_larga
from app.informes.pdf import color_pdf, obtener_fuentes, texto_pdf

TINTA = color_pdf(identidad.TEXTO)
AZUL = color_pdf(identidad.AZUL)   # el detalle bajo la casilla marcada (2026-11-27)
ROJO  = color_pdf(COLOR_DENEGADA)

CONCEPTO = "Recargo por atención fuera del horario laboral"
# Cómo se paga, como lo dice el papel (antes del 2026-11-26: «Efectivo, tarjeta o cheque a favor
# del…», pedido del 2026-11-18). El sistema no registra el pago.
PAGO = f"(PAGO EN EFECTIVO, TARJETA O CHEQUE A FAVOR DEL {identidad.INSTITUCION.upper()})."
CAMBIO_DE_PUERTO = "Cambio de Puerto"
# Las cursivas del papel (la fecha, el oficio y el título): las de la PDF estándar, que cubren
# Latin-1. Un oficio con otros caracteres va en la negrita con cobertura Unicode.
CURSIVA = "Helvetica-Oblique"
NEGRITA_CURSIVA = "Helvetica-BoldOblique"


@dataclass
class DatosPdfBoleta:
    numero_oficio:    str
    monto:            Decimal
    numero_solicitud: str
    tipo_tramite:     str
    agencia:          str
    buque:            str | None
    puesto:           str
    puesto_destino:   str | None   # cambio de puerto: el nuevo
    aprobada_en:      datetime     # la atención fuera del horario: fecha y hora
    generada_en:      datetime
    # El sector de UCVMM de la solicitud («Sector Pacífico»): firma su jefe encargado (2026-11-26).
    sector:           str | None = None
    anulada_en:       datetime | None = None
    motivo_anulacion: str | None = None
    # El tipo de operación en casillas (2026-11-16): los trámites activos del catálogo, en
    # su orden; la X va en `tipo_tramite`.
    tipos_operacion:  list[str] = field(default_factory=list)
    # Bajo la casilla marcada, una línea cada una (2026-11-27; del 2026-11-26 al 27, entre paréntesis):
    # la operación de Técnico, los días del sellado o, en las de antes que respondieron «Sí», «Subir y
    # bajar». El cambio de puerto lo suma `casillas_operacion` con `puesto` y `puesto_destino`.
    detalles:         list[str] = field(default_factory=list)


def casillas_operacion(
    tipos: list[str], elegido: str, *, detalles: list[str] | None = None,
    cambio_de_puerto: tuple[str, str] | None = None,
) -> list[tuple[str, bool, list[str]]]:
    """Cada tipo de operación con su marca y, en el de la solicitud, sus líneas de detalle, como las
    casillas de un formulario en papel. Si el de la solicitud ya no está entre los activos (Cambio de
    Puerto, desde el 2026-11-13), va al final, marcado. El cambio de puerto (el puesto de antes y el
    nuevo) va bajo la casilla del trámite, de cuál a cuál, y no marca otra casilla (2026-11-27)."""
    lineas = list(detalles or [])
    if cambio_de_puerto and elegido != CAMBIO_DE_PUERTO:
        de, a = cambio_de_puerto
        lineas.append(f"Cambio de puerto: de {de} a {a}")
    casillas = [(tipo, tipo == elegido, lineas if tipo == elegido else []) for tipo in tipos]
    if elegido not in tipos:
        casillas.append((elegido, True, lineas))
    return casillas


def _cabe_en_latin(texto: str) -> bool:
    try:
        texto.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


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
        base = {"fontName": normal, "fontSize": 10.5, "leading": 13.5, "textColor": TINTA, "spaceAfter": 3.5}
        base.update(kw)
        return ParagraphStyle(nombre, **base)

    def neg(texto: str) -> str:
        return f'<font name="{negrita}">{texto}</font>'

    e_texto    = estilo("texto")
    e_fecha    = estilo("fecha", fontName=CURSIVA, alignment=TA_RIGHT, spaceAfter=1)
    e_oficio   = estilo("oficio", fontName=NEGRITA_CURSIVA if _cabe_en_latin(d.numero_oficio) else negrita,
                        alignment=TA_RIGHT, spaceAfter=1)
    e_solicitud = estilo("solicitud", fontSize=9, leading=12, alignment=TA_RIGHT, spaceAfter=0)
    e_titulo   = estilo("titulo", fontName=NEGRITA_CURSIVA, fontSize=11.5, leading=15, alignment=TA_CENTER,
                        spaceAfter=0)
    e_casilla  = estilo("casilla", fontName=negrita, fontSize=10, leading=12.5, spaceAfter=0)
    e_marca    = estilo("marca", fontName=negrita, fontSize=9, leading=10, alignment=TA_CENTER, spaceAfter=0)
    e_detalle  = estilo("detalle", fontSize=9.5, leading=12, textColor=AZUL, spaceAfter=0)
    e_firma    = estilo("firma", fontSize=9.5, leading=12, alignment=TA_CENTER, spaceAfter=0)
    e_valida   = estilo("valida", fontName=negrita, fontSize=10.5, leading=14, alignment=TA_CENTER, spaceAfter=0)
    e_anulada  = estilo("anulada", fontName=negrita, fontSize=9, leading=12, textColor=ROJO, alignment=TA_CENTER,
                        spaceAfter=0)

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
    # Arriba, el espacio de la franja del encabezado (hasta su punta); abajo, el del pie (como los manuales).
    doc = _Documento(
        buffer, pagesize=letter, encima=sello_anulada if d.anulada_en else None,
        leftMargin=24 * mm, rightMargin=24 * mm, topMargin=35 * mm, bottomMargin=14 * mm,
        title=f"Boleta de recargo {d.numero_solicitud}",
        author=identidad.INSTITUCION_COMPLETA,
        subject=CONCEPTO,
    )
    ancho = doc.width
    historia: list = []
    generada = d.generada_en.astimezone(ZONA_PANAMA)
    aprobada = d.aprobada_en.astimezone(ZONA_PANAMA)
    jefe = f"del jefe encargado del {texto_pdf(d.sector)}" if d.sector else "del jefe encargado del sector"

    # ── Arriba a la derecha: la fecha, el oficio (lo escribe el funcionario) y la solicitud ──
    historia += [
        Paragraph(f"Panamá, <u>{fecha_larga(generada.date())}</u>.", e_fecha),
        Paragraph(f"Oficio N.º <u>{texto_pdf(d.numero_oficio)}</u>.", e_oficio),
        Paragraph(f"Autorización Marítima N.º {texto_pdf(d.numero_solicitud)}", e_solicitud),
        Spacer(1, 3.5 * mm),
        Paragraph("FORMULARIO No. 4.<br/>AUTORIZACIÓN FUERA DEL HORARIO LABORAL.", e_titulo),
        Spacer(1, 4 * mm),
    ]

    if d.anulada_en:
        anulada = Table(
            [[Paragraph(f"BOLETA ANULADA EL {d.anulada_en.astimezone(ZONA_PANAMA):%d/%m/%Y, %H:%M} — "
                        f"MOTIVO: {texto_pdf(d.motivo_anulacion)}", e_anulada)]],
            colWidths=[ancho],
        )
        anulada.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        historia += [anulada, Spacer(1, 3 * mm)]

    # ── La nota de cobro ──
    puesto = f"{d.puesto} → {d.puesto_destino}" if d.puesto_destino else d.puesto
    atencion = Table(
        [[Paragraph(f"{neg('Fecha de la Atención:')} <u>{aprobada:%d/%m/%Y}</u>", e_texto),
          Paragraph(f"{neg('Hora:')} <u>{aprobada:%H:%M}</u>", e_texto)]],
        colWidths=[ancho * 0.55, ancho * 0.45], hAlign="LEFT",
    )
    atencion.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    historia += [
        Paragraph(f"Agencia Naviera solicitante del servicio: {neg(texto_pdf(d.agencia))}", e_texto),
        Paragraph("Respetado representante de Agencia Naviera:", e_texto),
        Paragraph("Por este medio le hacemos llegar a su despacho nota de cobro por servicio prestado de la "
                  "siguiente unidad:", e_texto),
        Paragraph(f"{neg('A Favor de:')}&nbsp;&nbsp;&nbsp;&nbsp;<u>{identidad.INSTITUCION.upper()}</u>", e_texto),
        Paragraph(f"{neg('Moto Nave:')} <u>{texto_pdf(d.buque)}</u>", e_texto),
        atencion,
        Paragraph(f"{neg('Lugar:')} {texto_pdf(puesto)}", e_texto),
        Paragraph(f"{neg('Pago por Servicio:')} <u>{texto_pdf(texto_costo(d.monto))}</u>&nbsp;&nbsp;&nbsp;"
                  f"{neg(PAGO)}", e_texto),
        Paragraph(f"Tipo de autorización y aprobación fuera de horario laboral. Marque con una {neg('X')} el "
                  "cuadrante que requiere su solicitud.", e_texto),
        Spacer(1, 1 * mm),
    ]

    # ── Tipo de operación, en casillas como en papel ──
    def cuadro(marcada: bool) -> Table:
        caja = Table([[Paragraph("X" if marcada else "", e_marca)]], colWidths=[4.2 * mm], rowHeights=[4.2 * mm])
        caja.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, TINTA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return caja

    # Lo que eligió la agencia y el cambio de puerto, bajo la casilla marcada (2026-11-27): una línea
    # cada uno, en azul y con una raya a la izquierda, como las notas del sistema. Sin color (impresa en
    # blanco y negro) se sigue leyendo por la sangría y la raya. «Rótulo: valor», el rótulo en negrita.
    def linea_de_detalle(linea: str) -> Paragraph:
        rotulo, _, valor = linea.partition(": ")
        return Paragraph(f"{neg(texto_pdf(rotulo) + ':')} {texto_pdf(valor)}" if valor else texto_pdf(linea),
                         e_detalle)

    filas, estilo_filas = [], []
    cambio = (d.puesto, d.puesto_destino) if d.puesto_destino else None
    for tipo, marcada, lineas in casillas_operacion(d.tipos_operacion, d.tipo_tramite, detalles=d.detalles,
                                                    cambio_de_puerto=cambio):
        filas.append([cuadro(marcada), Paragraph(texto_pdf(tipo.upper()), e_casilla)])
        for linea in lineas:
            fila = len(filas)
            filas.append(["", linea_de_detalle(linea)])
            estilo_filas += [
                ("LINEBEFORE", (1, fila), (1, fila), 1.6, AZUL),
                ("LEFTPADDING", (1, fila), (1, fila), 6),
                ("TOPPADDING", (0, fila), (-1, fila), 0.4), ("BOTTOMPADDING", (0, fila), (-1, fila), 1.2),
            ]
    casillas = Table(filas, colWidths=[8 * mm, ancho - 8 * mm], hAlign="LEFT")
    casillas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        *estilo_filas,
    ]))
    historia += [casillas, Spacer(1, 3 * mm)]

    # ── Firma del jefe encargado del sector de UCVMM de la solicitud (2026-11-26) ──
    firma = Table(
        [[""], [Paragraph(f"Nombre, apellido y firma {jefe} (UCVMM)", e_firma)]],
        colWidths=[ancho * 0.8], rowHeights=[12 * mm, None], hAlign="CENTER",
    )
    firma.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.8, TINTA),
        ("TOPPADDING", (0, 1), (-1, 1), 3),
    ]))
    valida = Table(
        [[Paragraph(f"Esta autorización será únicamente válida, siempre que tenga nombre, firma y sello {jefe} "
                    "de UCVMM.", e_valida)]],
        colWidths=[ancho * 0.86], hAlign="CENTER",
    )
    valida.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, TINTA),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    historia += [
        Paragraph("Sin más que agregar, de ustedes,", e_texto),
        Paragraph("Firma del Agente Naviero que Solicita la Atención.", e_texto),
        firma,
        Spacer(1, 4 * mm),
        valida,
    ]

    def pagina(canvas, documento) -> None:
        # El encabezado y el pie de los manuales, donde los pone el modelo de la DTI (en puntos
        # desde la esquina de la hoja): la franja de 623 de ancho, 3 a la izquierda y 13 arriba de
        # la hoja; el pie de 527, a 42 del borde y a 757 de arriba.
        alto = documento.pagesize[1]
        canvas.saveState()
        if identidad.ENCABEZADO_SNM.exists():
            alto_franja = 623 * 295 / 1731
            canvas.drawImage(str(identidad.ENCABEZADO_SNM), -3, alto + 13 - alto_franja, width=623,
                             height=alto_franja, mask="auto")
        if identidad.PIE_SNM.exists():
            alto_pie = 527 * 57 / 1463
            canvas.drawImage(str(identidad.PIE_SNM), 42, alto - 757 - alto_pie, width=527, height=alto_pie,
                             mask="auto")
        canvas.restoreState()

    # Como el papel, en una hoja: si no cabe, se encoge lo justo (2026-11-27). Lo que mide depende de
    # la fuente (DejaVu en el servidor es más ancha que la Arial de Windows) y de los textos libres
    # (la agencia, la nave, los puestos y el motivo de la anulación); con los de siempre no se encoge.
    doc.build([KeepInFrame(ancho, doc.height, historia, mode="shrink")], onFirstPage=pagina, onLaterPages=pagina)
    return buffer.getvalue()
