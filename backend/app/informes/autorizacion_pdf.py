"""PDF de la Autorización Marítima, verificable con código QR.

Recibe datos planos (no objetos ORM) porque se genera en un hilo aparte, con
turno (infrastructure/trabajo_pesado.py): armar el PDF es CPU-bound y no debe
frenar el loop.
El QR apunta a /verificar/{codigo}, una página pública que confirma que la
autorización existe y si sigue vigente — sin exponer el expediente.

Hay dos versiones: la de la agencia ("Aprobada por: Servicio Nacional de
Migración", sin unidades internas desde el 2026-11-11) y la copia interna del
personal del SNM, con el nombre de quien aprobó, el de quien finalizó (desde el
2026-11-14) y una leyenda que la distingue si alguien la reenvía (reunión del
2026-10-30). Quien escanea el QR ve la de la agencia (2026-11-14).
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core import identidad
from app.core.horario import ZONA_PANAMA, aviso_fuera_de_horario
from app.informes.pdf import color_pdf, obtener_fuentes, texto_pdf

# La paleta del SNM (core/identidad.py) y, en los estados, el color de su insignia
# en la pantalla: aprobada en verde, finalizada en verde azulado.
TINTA    = color_pdf(identidad.TEXTO)
GRIS     = color_pdf(identidad.GRIS)
MARINO   = color_pdf(identidad.MARINO)
AMARILLO = color_pdf(identidad.AMARILLO)
BORDE    = color_pdf(identidad.BORDE)
FONDO    = color_pdf(identidad.FONDO)
CREMA    = color_pdf(identidad.CREMA)
VERDE    = color_pdf("#15803D")
TURQUESA = color_pdf("#0F766E")
# Fuera del horario: el morado de su insignia en la pantalla (--acc-purple del tema claro).
MORADO   = color_pdf("#7E22CE")
LILA     = color_pdf("#F2E9FA")   # el morado al 10 % sobre blanco

RANGOS = {
    "marino": "Marino", "pasajero": "Pasajero", "militar": "Militar", "tecnico": "Técnico",
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
    # Solo la traen las solicitudes enviadas antes del 2026-11-16 (salió del formulario).
    ocupacion:    str | None = None
    restringida:  bool = False


def titulo_columna_rango(tripulantes: list[TripulantePdf]) -> str:
    """«Rango / Ocupación» si algún tripulante la tiene (una solicitud de antes del
    2026-11-16); si no, «Rango»."""
    return "Rango / Ocupación" if any(t.ocupacion for t in tripulantes) else "Rango"


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
    aprobada_por:        str | None    # la institución para la agencia; el nombre, en la copia interna
    vigente_hasta:       datetime | None
    finalizada_en:       datetime | None
    # Donde se finalizó: desde el 2026-10-30, siempre el autorizado (antes podía ser otro).
    puesto_finalizacion: str | None
    url_verificacion:    str
    codigo_verificacion: str
    # Cuándo venció sin finalizarse (2026-11-22): esa solo la descarga el SNM.
    expirada_en:         datetime | None = None
    copia_interna:       bool = False  # la descarga el personal del SNM
    # Quien finalizó, solo en la copia interna (2026-11-14): la agencia no ve nombres.
    finalizada_por:      str | None = None
    # Cambio de puerto (2026-11-13): el nuevo puesto, donde vale y se finaliza.
    puesto_destino:      str | None = None
    # «¿Subir y bajar?» (2026-11-16): None si el trámite no hace la pregunta.
    subir_y_bajar:       bool | None = None
    # La operación del trámite de Técnico y los días del sellado de Shore Pass, ya en
    # palabras (2026-11-18): None en los demás.
    operacion:           str | None = None
    dias_sellado:        str | None = None
    # Aprobada fuera del horario laboral, con su recargo (2026-11-11).
    fuera_de_horario:       bool = False
    costo_fuera_de_horario: Decimal | None = None
    tripulantes:         list[TripulantePdf] = field(default_factory=list)


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
        valor = valor.astimezone(ZONA_PANAMA)
        return valor.strftime("%d/%m/%Y %I:%M %p" if con_hora else "%d/%m/%Y")
    return valor.strftime("%d/%m/%Y")


def generar_pdf_autorizacion(d: DatosPdfAutorizacion) -> bytes:
    normal, negrita = obtener_fuentes()

    def estilo(nombre: str, **kw) -> ParagraphStyle:
        base = {"fontName": normal, "fontSize": 9, "leading": 12, "textColor": TINTA}
        base.update(kw)
        return ParagraphStyle(nombre, **base)

    e_pais     = estilo("pais", fontSize=8, leading=10, textColor=GRIS)
    e_org      = estilo("org", fontName=negrita, fontSize=12.5, leading=15)
    e_seccion  = estilo("seccion", fontSize=8.5, leading=11, textColor=GRIS)
    e_titulo   = estilo("titulo", fontName=negrita, fontSize=15, leading=19, alignment=TA_CENTER)
    e_numero   = estilo("numero", fontName=negrita, fontSize=12, leading=15, alignment=TA_CENTER, textColor=MARINO)
    e_tramite  = estilo("tramite", fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=GRIS)
    e_etiqueta = estilo("etiqueta", fontName=negrita, fontSize=7, leading=9, textColor=GRIS)
    e_valor    = estilo("valor", fontSize=9.5, leading=12)
    e_subtit   = estilo("subtitulo", fontName=negrita, fontSize=10, leading=13, textColor=MARINO, spaceBefore=12, spaceAfter=5)
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
        author=identidad.INSTITUCION_COMPLETA,
        subject=d.tipo_tramite,
    )
    ancho = doc.width
    historia: list = []

    # ── Encabezado: logo · institución · QR ──
    logo = Image(str(identidad.LOGO_SNM), width=19 * mm, height=19 * mm, kind="proportional") \
        if identidad.LOGO_SNM.exists() else ""
    institucion = [
        Paragraph("REPÚBLICA DE PANAMÁ", e_pais),
        Paragraph(identidad.INSTITUCION.upper(), e_org),
        Paragraph("Sección de Autorizaciones Marítimas", e_seccion),
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
        Paragraph(texto_pdf(d.tipo_tramite), e_tramite),
        Spacer(1, 4 * mm),
    ]

    if d.estado == "finalized":
        lugar = f"EN {d.puesto_finalizacion.upper()} " if d.puesto_finalizacion else "EN PUERTO "
        texto_estado, color_estado = f"FINALIZADA {lugar}EL {_f(d.finalizada_en, True)}", TURQUESA
    elif d.estado == "expired":
        # Se aprobó y nadie la finalizó (2026-11-22): consta, pero ya no autoriza nada.
        texto_estado, color_estado = f"EXPIRADA — NO SE FINALIZÓ ANTES DEL {_f(d.vigente_hasta)}", GRIS
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

    if d.copia_interna:
        interna = Table(
            [[Paragraph("COPIA INTERNA DEL SNM — NO ENTREGAR A LA AGENCIA",
                        estilo("interna", fontName=negrita, fontSize=8, leading=10, alignment=TA_CENTER))]],
            colWidths=[ancho],
        )
        interna.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CREMA),
            ("BOX", (0, 0), (-1, -1), 0.8, AMARILLO),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        historia += [interna, Spacer(1, 2 * mm)]

    # ── Fuera del horario laboral: el aviso y el costo (2026-11-11) ──
    if d.fuera_de_horario:
        fuera = Table(
            [[Paragraph(escape(" ".join(aviso_fuera_de_horario(d.costo_fuera_de_horario))),
                        estilo("fuera", fontName=negrita, fontSize=8.5, leading=11, alignment=TA_CENTER))]],
            colWidths=[ancho],
        )
        fuera.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LILA),
            ("BOX", (0, 0), (-1, -1), 0.8, MORADO),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        historia += [fuera, Spacer(1, 2 * mm)]

    # ── Datos del trámite (rejilla de dos columnas) ──
    pares: list[tuple[str, str]] = [
        ("AGENCIA NAVIERA", texto_pdf(d.agencia_naviera)),
        ("PUESTO DE CONTROL MIGRATORIO", texto_pdf(d.puesto_control)),
        *([("CAMBIO DE PUERTO A", texto_pdf(d.puesto_destino))] if d.puesto_destino else []),
        *([("SUBIR Y BAJAR", "Sí" if d.subir_y_bajar else "No")] if d.subir_y_bajar is not None else []),
        *([("OPERACIÓN", texto_pdf(d.operacion))] if d.operacion else []),
        *([("DÍAS DEL SELLADO", texto_pdf(d.dias_sellado))] if d.dias_sellado else []),
        ("BUQUE", texto_pdf(d.nombre_buque)),
        ("IMO", texto_pdf(d.imo)),
        ("BANDERA", texto_pdf(d.bandera)),
        ("FECHA DE LA OPERACIÓN", _f(d.fecha_operacion)),
    ]
    if d.nombre_puerto:
        pares.append(("PUERTO", texto_pdf(d.nombre_puerto)))
    if d.puerto_desembarque:
        pares.append(("PUERTO DE DESEMBARQUE", texto_pdf(d.puerto_desembarque)))
    if d.clinica_hospital:
        pares.append(("CLÍNICA U HOSPITAL", texto_pdf(d.clinica_hospital)))
    if d.motivo:
        pares.append(("MOTIVO", texto_pdf(d.motivo)))
    pares += [
        ("FECHA DE LA SOLICITUD", _f(d.fecha_solicitud, True)),
        ("FECHA DE APROBACIÓN", _f(d.aprobada_en, True)),
        ("APROBADA POR", texto_pdf(d.aprobada_por)),
        ("TRIPULANTES AUTORIZADOS", str(len(d.tripulantes))),
    ]
    if d.estado == "finalized":
        pares += [
            ("FINALIZADA EN", texto_pdf(d.puesto_finalizacion or d.puesto_destino or d.puesto_control)),
            ("FECHA DE FINALIZACIÓN", _f(d.finalizada_en, True)),
        ]
        if d.finalizada_por:
            pares.append(("FINALIZADA POR", texto_pdf(d.finalizada_por)))
    if d.estado == "expired":
        pares.append(("FECHA DE EXPIRACIÓN", _f(d.expirada_en, True)))
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
    # Desde el 2026-10-30 no se finaliza en otro puesto: la operación en otro
    # puerto es una solicitud nueva.
    if d.estado == "expired":
        historia += [
            Spacer(1, 2 * mm),
            Paragraph("Esta autorización se aprobó, pero venció sin finalizarse en el puesto de control: no "
                      "autoriza la operación. Se conserva como constancia.", e_nota),
        ]
    elif d.estado != "finalized":
        donde = (f"para el cambio de puerto a {escape(d.puesto_destino)}, donde se finaliza" if d.puesto_destino
                 else "únicamente para el puesto de control indicado")
        historia += [
            Spacer(1, 2 * mm),
            Paragraph(
                f"Esta autorización vale {donde}. Si la operación se realiza en otro puesto, la agencia naviera "
                "debe presentar una nueva solicitud.",
                e_nota,
            ),
        ]

    # ── Tripulantes ──
    historia.append(Paragraph("TRIPULANTES", e_subtit))
    cabecera = ["N°", "Apellidos", "Nombres", "Nacionalidad", "Pasaporte", "Seamanbook", titulo_columna_rango(d.tripulantes)]
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
            Paragraph(texto_pdf(m.apellido), e_celda),
            Paragraph(texto_pdf(m.nombre), e_celda),
            Paragraph(nacionalidad, e_celda),
            Paragraph(texto_pdf(m.pasaporte), e_celda),
            Paragraph(texto_pdf(m.libreta) if m.libreta else "No aplica", e_celda),
            Paragraph(f"{escape(rango)}<br/>{texto_pdf(m.ocupacion)}" if m.ocupacion else escape(rango), e_celda),
        ])
    proporciones = [0.05, 0.17, 0.17, 0.15, 0.14, 0.14, 0.18]
    tabla_tripulantes = Table(filas_tripulantes, colWidths=[ancho * p for p in proporciones], repeatRows=1)
    tabla_tripulantes.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MARINO),
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
        historia += [Paragraph("NOTA", e_subtit), Paragraph(texto_pdf(d.nota_tramite), e_texto)]

    # ── Verificación ──
    historia += [
        Spacer(1, 6 * mm),
        Paragraph(
            f"Este documento fue emitido electrónicamente por el {identidad.INSTITUCION}. "
            "Verifique su autenticidad escaneando el código QR o ingresando a:",
            e_nota,
        ),
        Paragraph(f'<link href="{escape(d.url_verificacion)}">{escape(d.url_verificacion)}</link>', e_nota),
    ]

    generado = datetime.now(ZONA_PANAMA).strftime("%d/%m/%Y %I:%M %p")
    marca = " — copia interna del SNM" if d.copia_interna else ""

    def pie(canvas, documento) -> None:
        canvas.saveState()
        canvas.setStrokeColor(AMARILLO)
        canvas.setLineWidth(1.2)
        canvas.line(documento.leftMargin, 13 * mm, documento.leftMargin + documento.width, 13 * mm)
        canvas.setFont(normal, 7)
        canvas.setFillColor(GRIS)
        canvas.drawString(
            documento.leftMargin, 9 * mm,
            f"Autorización Marítima N° {d.numero} — generada el {generado} — código {d.codigo_verificacion[:12]}…{marca}",
        )
        canvas.drawRightString(documento.leftMargin + documento.width, 9 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()
