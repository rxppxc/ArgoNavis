"""Avisos por correo del flujo de Autorizaciones Marítimas.

Diseño "pase marítimo": una tarjeta azul marino con el logo de ARGO NAVIS, el
número de la solicitud, un sello con el estado y los datos de la operación;
debajo, el detalle y el botón. HTML con tablas y estilos en línea (Outlook de
escritorio ignora las esquinas redondeadas y la inclinación del sello, y se ve
igual de claro).

  - Asunto: "Autorizaciones Marítimas · AM-2026-000011 · Aprobada".
  - El logo va incrustado en el mensaje (Content-ID): se ve aunque el cliente
    bloquee las imágenes externas.
  - Lleva versión en texto plano y una vista previa para la bandeja.
"""
import html
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import aiosmtplib

from app.core.config import obtener_configuracion

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

NAVY, ORO = "#14213D", "#D9A62E"
_FUENTE   = "'Segoe UI',Arial,sans-serif"
_MONO     = "Consolas,'Courier New',monospace"
_SOPORTE  = "mesadeayuda@migracion.gob.pa"

# Logo de ARGO NAVIS (PNG de 141 px que se muestra a 70): Outlook de escritorio no
# muestra WebP, por eso no se usa el del frontend.
_LOGO     = Path(__file__).parent.parent / "recursos" / "logo-argo-navis-correo.png"
_LOGO_PNG = _LOGO.read_bytes() if _LOGO.exists() else b""
_CID_LOGO = "logo-argo-navis@argonavis.snm"

# Etiquetas de los propios avisos que van en negrita al inicio de una línea del
# recuadro destacado (el resto, lo que escribió el usuario, va tal cual, escapado).
_ETIQUETAS = ("Motivo:", "Plazo para corregir:", "Nacionalidad restringida:")

# Color del sello (sobre el azul marino) y del recuadro destacado (fondo, borde) por tono.
_SELLO = {"verde": "#4ADE80", "rojo": "#F87171", "amarillo": "#FBBF24", "azul": "#93C5FD"}
_DESTACADO = {
    "verde":    ("#EAF6EE", "#15803D"),
    "rojo":     ("#FDECEC", "#B91C1C"),
    "amarillo": ("#FFF6DD", "#B45309"),
    "azul":     ("#E8F0FE", "#1D4ED8"),
}


@dataclass
class Aviso:
    """Un correo del flujo, ya armado con texto plano (no objetos ORM): se
    envía en segundo plano, cuando la sesión de BD ya se cerró."""
    destinatarios: list[str]
    numero:        str                       # "AM-2026-000011": asunto y pase
    estado:        str                       # "Aprobada", "Devuelta a corrección"...: asunto y sello
    titulo:        str
    intro:         str
    vista_previa:  str = ""                  # lo que muestra la bandeja junto al asunto
    campos:        list[tuple[str, str]] = field(default_factory=list)   # datos del pase (los vacíos no van)
    destacado:     str | None = None
    tono:          str = "azul"              # verde | rojo | amarillo | azul
    boton_texto:   str | None = None
    boton_url:     str | None = None

    @property
    def asunto(self) -> str:
        return f"Autorizaciones Marítimas · {self.numero} · {self.estado}"


def _esc(texto: str) -> str:
    """Escapa contenido controlado por el usuario antes de interpolarlo en las
    plantillas HTML. Sin esto, un motivo o comentario con etiquetas HTML se
    renderizaría dentro de un correo oficial del SNM (inyección de HTML)."""
    return html.escape(texto, quote=True)


def _esc_multilinea(texto: str) -> str:
    """Igual que _esc pero conserva los saltos de línea como <br>."""
    return _esc(texto).replace("\r\n", "\n").replace("\n", "<br>")


def _destacado_html(texto: str) -> str:
    """Recuadro destacado: escapado, con saltos de línea y las etiquetas propias en negrita."""
    lineas = _esc(texto).replace("\r\n", "\n").split("\n")
    for i, linea in enumerate(lineas):
        etiqueta = next((e for e in _ETIQUETAS if linea.startswith(e)), None)
        if etiqueta:
            lineas[i] = f"<b>{etiqueta}</b>{linea[len(etiqueta):]}"
    return "<br>".join(lineas)


def _sanear_subject(texto: str) -> str:
    """Elimina CR/LF de valores que van en cabeceras del correo (evita
    inyección de cabeceras vía título con saltos de línea)."""
    return texto.replace("\r", " ").replace("\n", " ").strip()


# ── HTML ─────────────────────────────────────────────────────────────────────

def _grilla(campos: list[tuple[str, str]]) -> str:
    """Datos del pase en filas de tres; un dato solo en la última fila ocupa el ancho."""
    llenos = [(e, v) for e, v in campos if v]
    filas = ""
    for i in range(0, len(llenos), 3):
        fila = llenos[i:i + 3]
        ancho = ' colspan="3"' if len(fila) == 1 else ""
        celdas = "".join(
            f"""<td width="33%" valign="top"{ancho} style="padding:6px 8px 10px 0;">
<div style="font:700 10px {_FUENTE};letter-spacing:1.2px;color:{ORO};text-transform:uppercase;">{_esc(e)}</div>
<div style="font:600 14px {_FUENTE};color:#FFFFFF;margin-top:3px;">{_esc(v)}</div></td>"""
            for e, v in fila
        )
        filas += f"<tr>{celdas}</tr>"
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas}</table>'


def _construir_html_aviso(aviso: Aviso) -> str:
    sello = _SELLO.get(aviso.tono, _SELLO["azul"])
    logo = (
        f'<img src="cid:{_CID_LOGO}" width="70" height="62" alt="ARGO NAVIS" style="display:block;border:0;">'
        if _LOGO_PNG else ""
    )
    destacado = ""
    if aviso.destacado:
        fondo, borde = _DESTACADO.get(aviso.tono, _DESTACADO["azul"])
        destacado = f"""<div style="margin-top:14px;background:{fondo};border-left:4px solid {borde};padding:13px 16px;
font:14px/1.6 {_FUENTE};color:#1F2937;">{_destacado_html(aviso.destacado)}</div>"""
    boton = ""
    if aviso.boton_texto and aviso.boton_url:
        url = _esc(aviso.boton_url)
        boton = f"""<tr><td style="padding:22px 6px 24px;text-align:center;">
  <table role="presentation" cellpadding="0" cellspacing="0" align="center"><tr><td bgcolor="{ORO}" style="border-radius:6px;">
    <a href="{url}" style="display:inline-block;padding:13px 30px;font:700 15px {_FUENTE};color:{NAVY};text-decoration:none;">{_esc(aviso.boton_texto)}</a>
  </td></tr></table>
  <div style="font:12px/1.5 {_FUENTE};color:#7A8594;margin-top:12px;">Si el botón no abre, copie este enlace:<br>
    <a href="{url}" style="color:#005293;word-break:break-all;">{url}</a></div>
</td></tr>"""
    # Relleno tras la vista previa: evita que la bandeja muestre después el texto del pase.
    relleno = "&nbsp;&zwnj;" * 80

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting"><title>{_esc(aviso.asunto)}</title></head>
<body style="margin:0;padding:0;background:#EEF1F5;">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#EEF1F5;">{_esc(aviso.vista_previa)}{relleno}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#EEF1F5"><tr>
<td align="center" style="padding:28px 12px 36px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr><td bgcolor="{NAVY}" style="border-radius:14px 14px 0 0;padding:20px 24px 16px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="72" valign="middle">{logo}</td>
      <td valign="middle" style="font:700 11px {_FUENTE};letter-spacing:2px;color:{ORO};text-transform:uppercase;">Pase de autorización marítima
        <div style="font:600 13px {_FUENTE};letter-spacing:.4px;color:#FFFFFF;text-transform:none;margin-top:3px;">Servicio Nacional de Migración</div></td>
      <td align="right" valign="top" style="font:12px {_MONO};color:#9FB0CC;white-space:nowrap;">09° 01′ N<br>079° 32′ O</td>
    </tr></table>
    <div style="margin-top:16px;">
      <div style="display:inline-block;vertical-align:middle;margin:0 18px 8px 0;font:800 26px {_MONO};color:{ORO};
        letter-spacing:1px;white-space:nowrap;">{_esc(aviso.numero)}</div>
      <div style="display:inline-block;vertical-align:middle;margin-bottom:8px;"><span style="display:inline-block;
        border:2px solid {sello};color:{sello};border-radius:6px;padding:5px 10px;font:800 13px {_FUENTE};
        letter-spacing:1.6px;text-transform:uppercase;transform:rotate(-4deg);white-space:nowrap;">{_esc(aviso.estado)}</span></div>
    </div>
  </td></tr>
  <tr><td bgcolor="{NAVY}" style="padding:0 16px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="border-top:2px dashed #40527A;font-size:0;line-height:0;height:1px;">&nbsp;</td></tr></table>
  </td></tr>
  <tr><td bgcolor="{NAVY}" style="border-radius:0 0 14px 14px;padding:14px 24px 20px;">{_grilla(aviso.campos)}</td></tr>
  <tr><td style="padding:24px 6px 0;">
    <div style="font:800 20px/1.3 {_FUENTE};color:{NAVY};margin-bottom:8px;">{_esc(aviso.titulo)}</div>
    <div style="font:14px/1.65 {_FUENTE};color:#3F4A59;">{_esc_multilinea(aviso.intro)}</div>{destacado}
  </td></tr>
  {boton}
  <tr><td style="border-top:1px solid #DDE3EA;padding:14px 6px 0;text-align:center;font:12px/1.6 {_FUENTE};color:#5B6676;">
    <b style="color:{NAVY};">Servicio Nacional de Migración · República de Panamá</b><br>
    Mensaje automático de ARGO NAVIS: no responda a este correo. ¿Necesita ayuda?
    <a href="mailto:{_SOPORTE}" style="color:#005293;">{_SOPORTE}</a></td></tr>
</table>
</td></tr></table>
</body>
</html>"""


def _texto_plano(aviso: Aviso) -> str:
    """Versión sin formato (clientes de solo texto, lectores de pantalla y filtros de spam)."""
    lineas = [aviso.asunto, "", aviso.titulo, "", aviso.intro, ""]
    lineas += [f"{e}: {v}" for e, v in aviso.campos if v]
    if aviso.destacado:
        lineas += ["", aviso.destacado]
    if aviso.boton_texto and aviso.boton_url:
        lineas += ["", f"{aviso.boton_texto}: {aviso.boton_url}"]
    lineas += [
        "", "--",
        "Servicio Nacional de Migración · República de Panamá",
        f"Mensaje automático de ARGO NAVIS: no responda a este correo. ¿Necesita ayuda? {_SOPORTE}",
    ]
    return "\n".join(lineas)


def construir_mensaje(aviso: Aviso, destinatarios: list[str]) -> EmailMessage:
    """El correo listo para enviar: texto plano + HTML con el logo incrustado."""
    mensaje = EmailMessage()
    mensaje["Subject"] = _sanear_subject(aviso.asunto)
    mensaje["From"]    = formataddr((configuracion.MAIL_FROM_NAME, configuracion.MAIL_FROM))
    mensaje["To"]      = ", ".join(destinatarios)
    # Aviso automático (RFC 3834): que los "fuera de la oficina" no le respondan.
    mensaje["Auto-Submitted"] = "auto-generated"
    mensaje.set_content(_texto_plano(aviso))
    mensaje.add_alternative(_construir_html_aviso(aviso), subtype="html")
    if _LOGO_PNG:
        mensaje.get_payload()[1].add_related(
            _LOGO_PNG, maintype="image", subtype="png", cid=f"<{_CID_LOGO}>", disposition="inline",
        )
    return mensaje


async def enviar_aviso(aviso: Aviso) -> None:
    """Envía un aviso del flujo (se llama como tarea en segundo plano: un
    fallo de SMTP se registra y no rompe la operación)."""
    asunto = _sanear_subject(aviso.asunto)
    destinatarios = list(dict.fromkeys(d.strip() for d in aviso.destinatarios if d and d.strip()))
    if not destinatarios:
        return
    if not configuracion.MAIL_HOST:
        logger.warning("SMTP no configurado — se omite el aviso '%s'.", asunto)
        return

    try:
        await aiosmtplib.send(
            construir_mensaje(aviso, destinatarios),
            hostname=configuracion.MAIL_HOST,
            port=configuracion.MAIL_PORT,
            use_tls=False,
            start_tls=False,
            username=configuracion.MAIL_USERNAME or None,
            password=configuracion.MAIL_PASSWORD or None,
        )
        logger.info("Aviso '%s' enviado a %d destinatario(s).", asunto, len(destinatarios))
    except Exception as e:
        logger.error("Error al enviar el aviso '%s': %s", asunto, e)
