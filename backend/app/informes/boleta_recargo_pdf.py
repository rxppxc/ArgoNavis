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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core import identidad
from app.core.horario import ZONA_PANAMA, texto_costo
from app.informes.comun import COLOR_DENEGADA, fecha_larga
from app.informes.pdf import color_pdf, obtener_fuentes, texto_pdf

TINTA = color_pdf(identidad.TEXTO)
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
    # Junto a la casilla marcada, entre paréntesis (2026-11-26): la operación de Técnico, los días
    # del sellado de Shore Pass o, en las de antes que respondieron «Sí», «subir y bajar».
    detalle:          str | None = None


def casillas_operacion(
    tipos: list[str], elegido: str, *, detalle: str | None = None, cambio_de_puerto: bool = False,
) -> list[tuple[str, bool, str | None]]:
    """Cada tipo de operación con su marca y, en el de la solicitud, `detalle`, como las casillas
    de un formulario en papel. Si el de la solicitud ya no está entre los activos (Cambio de
    Puerto, desde el 2026-11-13), va al final, marcado. Con cambio de puerto, la X también va en
    «Cambio de Puerto»."""
    casillas = [(tipo, tipo == elegido, detalle if tipo == elegido else None) for tipo in tipos]
    if elegido not in tipos:
        casillas.append((elegido, True, detalle))
    if cambio_de_puerto and elegido != CAMBIO_DE_PUERTO:
        if CAMBIO_DE_PUERTO in tipos:
            casillas = [(t, marcada or t == CAMBIO_DE_PUERTO, d) for t, marcada, d in casillas]
        else:
            casillas.append((CAMBIO_DE_PUERTO, True, None))
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

    filas = []
    for tipo, marcada, detalle in casillas_operacion(d.tipos_operacion, d.tipo_tramite, detalle=d.detalle,
                                                     cambio_de_puerto=bool(d.puesto_destino)):
        texto = texto_pdf(tipo.upper())
        if detalle:
            texto += f' <font name="{normal}">({texto_pdf(detalle)})</font>'
        filas.append([cuadro(marcada), Paragraph(texto, e_casilla)])
    casillas = Table(filas, colWidths=[8 * mm, ancho - 8 * mm], hAlign="LEFT")
    casillas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
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

    doc.build(historia, onFirstPage=pagina, onLaterPages=pagina)
    return buffer.getvalue()
