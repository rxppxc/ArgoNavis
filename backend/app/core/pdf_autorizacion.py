"""PDF de la Autorización Marítima, verificable con código QR.

Recibe datos planos (no objetos ORM) porque se genera en un hilo aparte
(`asyncio.to_thread`): armar el PDF es CPU-bound y no debe frenar el loop.
El QR apunta a /verificar/{codigo}, una página pública que confirma que la
autorización existe y si sigue vigente — sin exponer el expediente.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

_LOGO = Path(__file__).resolve().parent.parent / "recursos" / "logo-snm.png"
_TZ_PANAMA = ZoneInfo("America/Panama")

# Fuentes TrueType con cobertura Unicode amplia (nombres con ş, ł, ğ...). Si no
# hay ninguna en el servidor se usa Helvetica, que solo cubre Latin-1.
_CANDIDATOS_FUENTE = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
]
_fuentes: tuple[str, str] | None = None

NEGRO    = colors.HexColor("#111111")
GRIS     = colors.HexColor("#555B66")
AZUL     = colors.HexColor("#12395C")
AMARILLO = colors.HexColor("#F5C800")
VERDE    = colors.HexColor("#15803D")
BORDE    = colors.HexColor("#CBD5E1")
FONDO    = colors.HexColor("#F4F6F9")

RANGOS = {
    "marino": "Marino", "militar": "Militar", "tecnico": "Técnico",
    "supernumerario": "Supernumerario", "superintendente": "Superintendente",
}


@dataclass
class TripulantePdf:
    nombre:       str
    apellido:     str
    nacionalidad: str
    pasaporte:    str
    libreta:      str
    rango:        str
    ocupacion:    str
    restringida:  bool = False


@dataclass
class DatosPdfAutorizacion:
    numero:              str
    estado:              str
    tipo_tramite:        str
    nota_tramite:        str | None
    aviso_custodia:      bool          # el proceso del trámite pide avisar la custodia
    agencia_naviera:     str | None
    nombre_buque:        str | None
    imo:                 str | None
    bandera:             str | None
    puesto_control:      str | None
    fecha_operacion:     date | None
    nombre_puerto:       str | None
    puerto_desembarque:  str | None
    clinica_hospital:    str | None
    motivo:              str | None
    fecha_solicitud:     datetime
    aprobada_en:         datetime
    aprobada_por:        str | None
    vigente_hasta:       datetime | None
    finalizada_en:       datetime | None
    puesto_finalizacion: str | None   # donde terminó la operación (puede no ser el autorizado)
    url_verificacion:    str
    codigo_verificacion: str
    tripulantes:         list[TripulantePdf] = field(default_factory=list)


def _obtener_fuentes() -> tuple[str, str]:
    global _fuentes
    if _fuentes is None:
        _fuentes = ("Helvetica", "Helvetica-Bold")
        for normal, negrita in _CANDIDATOS_FUENTE:
            if Path(normal).exists() and Path(negrita).exists():
                try:
                    pdfmetrics.registerFont(TTFont("SNM", normal))
                    pdfmetrics.registerFont(TTFont("SNM-Negrita", negrita))
                    _fuentes = ("SNM", "SNM-Negrita")
                    break
                except Exception as exc:  # fuente dañada o ilegible: probar la siguiente
                    logger.warning("[pdf] No se pudo registrar la fuente %s: %s", normal, exc)
    return _fuentes


def _qr(url: str, tamano: float) -> Drawing:
    widget = QrCodeWidget(url, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    dibujo = Drawing(tamano, tamano, transform=[tamano / (x2 - x1), 0, 0, tamano / (y2 - y1), 0, 0])
    dibujo.add(widget)
    return dibujo


def _f(valor: date | datetime | None, con_hora: bool = False) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, datetime):
        valor = valor.astimezone(_TZ_PANAMA)
        return valor.strftime("%d/%m/%Y %I:%M %p" if con_hora else "%d/%m/%Y")
    return valor.strftime("%d/%m/%Y")


def _t(texto: str | None) -> str:
    """Texto de usuario listo para un Paragraph (que interpreta marcado)."""
    return escape(texto) if texto else "—"


def generar_pdf_autorizacion(d: DatosPdfAutorizacion) -> bytes:
    normal, negrita = _obtener_fuentes()

    def estilo(nombre: str, **kw) -> ParagraphStyle:
        base = {"fontName": normal, "fontSize": 9, "leading": 12, "textColor": NEGRO}
        base.update(kw)
        return ParagraphStyle(nombre, **base)

    e_pais     = estilo("pais", fontSize=8, leading=10, textColor=GRIS)
    e_org      = estilo("org", fontName=negrita, fontSize=12.5, leading=15)
    e_seccion  = estilo("seccion", fontSize=8.5, leading=11, textColor=GRIS)
    e_titulo   = estilo("titulo", fontName=negrita, fontSize=15, leading=19, alignment=TA_CENTER)
    e_numero   = estilo("numero", fontName=negrita, fontSize=12, leading=15, alignment=TA_CENTER, textColor=AZUL)
    e_tramite  = estilo("tramite", fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=GRIS)
    e_etiqueta = estilo("etiqueta", fontName=negrita, fontSize=7, leading=9, textColor=GRIS)
    e_valor    = estilo("valor", fontSize=9.5, leading=12)
    e_subtit   = estilo("subtitulo", fontName=negrita, fontSize=10, leading=13, textColor=AZUL, spaceBefore=12, spaceAfter=5)
    e_celda    = estilo("celda", fontSize=8, leading=10)
    e_cabecera = estilo("cabecera", fontName=negrita, fontSize=7.5, leading=9.5, textColor=colors.white)
    e_texto    = estilo("texto", fontSize=9, leading=12.5)
    e_nota     = estilo("nota", fontSize=7.5, leading=10, textColor=GRIS)
    e_qr       = estilo("qr", fontSize=6.5, leading=8, textColor=GRIS, alignment=TA_CENTER)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=17 * mm, rightMargin=17 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
        title=f"Autorización Marítima {d.numero}",
        author="Servicio Nacional de Migración de Panamá",
        subject=d.tipo_tramite,
    )
    ancho = doc.width
    historia: list = []

    # ── Encabezado: logo · institución · QR ──
    logo = Image(str(_LOGO), width=19 * mm, height=19 * mm, kind="proportional") if _LOGO.exists() else ""
    institucion = [
        Paragraph("REPÚBLICA DE PANAMÁ", e_pais),
        Paragraph("SERVICIO NACIONAL DE MIGRACIÓN", e_org),
        Paragraph("Sección de Autorizaciones Marítimas — UCVMM", e_seccion),
    ]
    bloque_qr = [_qr(d.url_verificacion, 26 * mm), Paragraph("Escanee para verificar", e_qr)]
    encabezado = Table([[logo, institucion, bloque_qr]], colWidths=[23 * mm, ancho - 23 * mm - 30 * mm, 30 * mm])
    encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    historia.append(encabezado)
    franja = Table([[""]], colWidths=[ancho], rowHeights=[2.2])
    franja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMARILLO)]))
    historia += [Spacer(1, 3 * mm), franja, Spacer(1, 6 * mm)]

    # ── Título ──
    historia += [
        Paragraph("AUTORIZACIÓN MARÍTIMA", e_titulo),
        Paragraph(f"N° {escape(d.numero)}", e_numero),
        Paragraph(_t(d.tipo_tramite), e_tramite),
        Spacer(1, 4 * mm),
    ]

    if d.estado == "finalized":
        lugar = f"EN {d.puesto_finalizacion.upper()} " if d.puesto_finalizacion else "EN PUERTO "
        texto_estado, color_estado = f"FINALIZADA {lugar}EL {_f(d.finalizada_en, True)}", AZUL
    else:
        texto_estado = "APROBADA" + (f" — VIGENTE HASTA EL {_f(d.vigente_hasta)}" if d.vigente_hasta else "")
        color_estado = VERDE
    estado = Table(
        [[Paragraph(escape(texto_estado), estilo("estado", fontName=negrita, fontSize=9.5, alignment=TA_CENTER, textColor=colors.white))]],
        colWidths=[ancho],
    )
    estado.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color_estado),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    historia += [estado, Spacer(1, 2 * mm)]

    # ── Datos del trámite (rejilla de dos columnas) ──
    pares: list[tuple[str, str]] = [
        ("AGENCIA NAVIERA", _t(d.agencia_naviera)),
        ("PUESTO DE CONTROL MIGRATORIO", _t(d.puesto_control)),
        ("BUQUE", _t(d.nombre_buque)),
        ("IMO", _t(d.imo)),
        ("BANDERA", _t(d.bandera)),
        ("FECHA DE LA OPERACIÓN", _f(d.fecha_operacion)),
    ]
    if d.nombre_puerto:
        pares.append(("PUERTO", _t(d.nombre_puerto)))
    if d.puerto_desembarque:
        pares.append(("PUERTO DE DESEMBARQUE", _t(d.puerto_desembarque)))
    if d.clinica_hospital:
        pares.append(("CLÍNICA U HOSPITAL", _t(d.clinica_hospital)))
    if d.motivo:
        pares.append(("MOTIVO", _t(d.motivo)))
    pares += [
        ("FECHA DE LA SOLICITUD", _f(d.fecha_solicitud, True)),
        ("FECHA DE APROBACIÓN", _f(d.aprobada_en, True)),
        ("APROBADA POR", _t(d.aprobada_por)),
        ("TRIPULANTES AUTORIZADOS", str(len(d.tripulantes))),
    ]
    if d.estado == "finalized":
        pares += [
            ("FINALIZADA EN", _t(d.puesto_finalizacion or d.puesto_control)),
            ("FECHA DE FINALIZACIÓN", _f(d.finalizada_en, True)),
        ]
    if len(pares) % 2:
        pares.append(("", ""))
    filas = []
    for i in range(0, len(pares), 2):
        fila = []
        for etiqueta, valor in pares[i:i + 2]:
            fila.append([Paragraph(etiqueta, e_etiqueta), Paragraph(valor, e_valor)] if etiqueta else "")
        filas.append(fila)
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
    historia.append(datos)

    # ── Tripulantes ──
    historia.append(Paragraph("TRIPULANTES", e_subtit))
    cabecera = ["N°", "Apellidos", "Nombres", "Nacionalidad", "Pasaporte", "Seamanbook", "Rango / Ocupación"]
    filas_tripulantes = [[Paragraph(c, e_cabecera) for c in cabecera]]
    hay_restringidos = False
    for i, m in enumerate(d.tripulantes, start=1):
        nacionalidad = escape(m.nacionalidad or "—")
        if m.restringida and d.aviso_custodia:
            hay_restringidos = True
            nacionalidad += " *"
        rango = RANGOS.get(m.rango, m.rango or "")
        filas_tripulantes.append([
            Paragraph(str(i), e_celda),
            Paragraph(_t(m.apellido), e_celda),
            Paragraph(_t(m.nombre), e_celda),
            Paragraph(nacionalidad, e_celda),
            Paragraph(_t(m.pasaporte), e_celda),
            Paragraph(_t(m.libreta) if m.libreta else "No aplica", e_celda),
            Paragraph(f"{escape(rango)}<br/>{_t(m.ocupacion)}", e_celda),
        ])
    proporciones = [0.05, 0.17, 0.17, 0.15, 0.14, 0.14, 0.18]
    tabla_tripulantes = Table(filas_tripulantes, colWidths=[ancho * p for p in proporciones], repeatRows=1)
    tabla_tripulantes.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FONDO]),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(tabla_tripulantes)
    if hay_restringidos:
        historia += [
            Spacer(1, 2 * mm),
            Paragraph(
                "* Nacionalidad restringida: la agencia naviera debe realizar el trámite de solicitud de custodia.",
                e_nota,
            ),
        ]

    # ── Nota del trámite (la observación de UCVMM es interna: no va en el PDF) ──
    if d.nota_tramite:
        historia += [Paragraph("NOTA", e_subtit), Paragraph(_t(d.nota_tramite), e_texto)]

    # ── Verificación ──
    historia += [
        Spacer(1, 6 * mm),
        Paragraph(
            "Este documento fue emitido electrónicamente por el Servicio Nacional de Migración. "
            "Verifique su autenticidad escaneando el código QR o ingresando a:",
            e_nota,
        ),
        Paragraph(f'<link href="{escape(d.url_verificacion)}">{escape(d.url_verificacion)}</link>', e_nota),
    ]

    generado = datetime.now(_TZ_PANAMA).strftime("%d/%m/%Y %I:%M %p")

    def pie(canvas, documento) -> None:
        canvas.saveState()
        canvas.setStrokeColor(AMARILLO)
        canvas.setLineWidth(1.2)
        canvas.line(documento.leftMargin, 13 * mm, documento.leftMargin + documento.width, 13 * mm)
        canvas.setFont(normal, 7)
        canvas.setFillColor(GRIS)
        canvas.drawString(
            documento.leftMargin, 9 * mm,
            f"Autorización Marítima N° {d.numero} — generada el {generado} — código {d.codigo_verificacion[:12]}…",
        )
        canvas.drawRightString(documento.leftMargin + documento.width, 9 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()
