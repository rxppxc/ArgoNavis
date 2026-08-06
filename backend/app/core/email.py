import base64
import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib

from app.core.config import obtener_configuracion

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()


def _esc(texto: str) -> str:
    """Escapa contenido controlado por el usuario antes de interpolarlo en las
    plantillas HTML. Sin esto, un título/mensaje/motivo con etiquetas HTML se
    renderizaría dentro de un correo oficial del SNM (inyección de HTML)."""
    return html.escape(texto, quote=True)


def _esc_multilinea(texto: str) -> str:
    """Igual que _esc pero conserva los saltos de línea como <br>."""
    return _esc(texto).replace("\r\n", "\n").replace("\n", "<br>")


def _sanear_subject(texto: str) -> str:
    """Elimina CR/LF de valores que van en cabeceras del correo (evita
    inyección de cabeceras vía título con saltos de línea)."""
    return texto.replace("\r", " ").replace("\n", " ").strip()

_LOGO_PATH = Path(__file__).parent.parent.parent / "frontend" / "public" / "images" / "logo-snm.png"
_LOGO_B64: str = ""
if _LOGO_PATH.exists():
    _LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()


def _logo_src() -> str:
    if _LOGO_B64:
        return f"data:image/png;base64,{_LOGO_B64}"
    return f"{configuracion.app_base_url}/images/logo-snm.png"


def _construir_html(nombre_remitente: str, titulo: str | None, mensaje: str | None,
                    url_descarga: str, cantidad_archivos: int, fecha_expiracion: str) -> str:

    titulo_texto  = _esc(titulo or "Transferencia de archivos")
    primer_nombre = _esc(nombre_remitente.split()[0] if nombre_remitente else "Alguien")

    bloque_mensaje = ""
    if mensaje:
        bloque_mensaje = f"""
    <tr>
      <td style="padding:0 32px 24px;">
        <div style="background:#F4F4F4;border-left:4px solid #F5C800;
                    padding:16px 20px;font-size:14px;color:#444444;
                    line-height:1.8;font-style:italic;border-radius:0 4px 4px 0;">
          &#8220;{_esc_multilinea(mensaje)}&#8221;
        </div>
      </td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
</head>
<body style="margin:0;padding:0;background:#E8E8E8;font-family:'Segoe UI',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#E8E8E8">
<tr><td align="center" style="padding:36px 16px 52px;">

  <table width="560" cellpadding="0" cellspacing="0"
         style="max-width:560px;width:100%;box-shadow:0 4px 24px rgba(0,0,0,.13);">

    <!-- CABECERA -->
    <tr>
      <td bgcolor="#111111" style="padding:28px 32px 24px;text-align:center;">
        <img src="{_logo_src()}" width="58" height="58" alt="SNM"
             style="display:block;margin:0 auto 12px;" />
        <div style="color:#FFFFFF;font-size:20px;font-weight:800;
                    letter-spacing:.3px;line-height:1.2;margin-bottom:4px;">
          Servicio Nacional de Migraci&oacute;n
        </div>
        <div style="color:#999999;font-size:11px;font-weight:500;
                    letter-spacing:2px;text-transform:uppercase;">
          FileDrop &nbsp;|&nbsp; SNM
        </div>
      </td>
    </tr>

    <!-- Franja amarilla -->
    <tr>
      <td bgcolor="#F5C800" height="4" style="font-size:0;line-height:0;">&nbsp;</td>
    </tr>

    <!-- INTRO -->
    <tr>
      <td bgcolor="#FAFAFA" style="padding:28px 32px 8px;">
        <div style="font-size:13px;color:#555555;margin-bottom:6px;">
          <span style="font-weight:700;color:#111111;">{primer_nombre}</span>
          &nbsp;te ha compartido los siguientes archivos:
        </div>
        <div style="font-size:22px;font-weight:800;color:#111111;
                    line-height:1.3;padding-bottom:20px;
                    border-bottom:2px solid #F5C800;margin-bottom:20px;">
          {titulo_texto}
        </div>
      </td>
    </tr>

    <!-- MENSAJE / COMENTARIOS -->
    {bloque_mensaje}

    <!-- BOTÓN DE DESCARGA -->
    <tr>
      <td bgcolor="#FAFAFA" style="padding:0 32px 32px;text-align:center;">
        <a href="{url_descarga}"
           style="display:inline-block;background:#F5C800;color:#111111;
                  font-size:15px;font-weight:800;padding:14px 36px;
                  border-radius:4px;text-decoration:none;letter-spacing:.3px;">
          Ver y descargar archivos
        </a>
        <div style="font-size:13px;font-weight:600;color:#333333;margin-top:18px;">
          Enlace disponible hasta: <span style="color:#111111;">{fecha_expiracion}</span>
        </div>
        <div style="font-size:12px;color:#555555;margin-top:8px;word-break:break-all;">
          <a href="{url_descarga}" style="color:#0066CC;text-decoration:underline;">{url_descarga}</a>
        </div>
      </td>
    </tr>

    <!-- Franja amarilla inferior -->
    <tr>
      <td bgcolor="#F5C800" height="4" style="font-size:0;line-height:0;">&nbsp;</td>
    </tr>

    <!-- PIE -->
    <tr>
      <td bgcolor="#1A1A1A" style="padding:18px 32px;text-align:center;">
        <p style="margin:0;font-size:13px;color:#EEEEEE;font-weight:700;line-height:1.8;">
          Servicio Nacional de Migraci&oacute;n
          &mdash; Direcci&oacute;n de Tecnolog&iacute;a e Innovaci&oacute;n
        </p>
        <p style="margin:4px 0 0;font-size:11px;color:#AAAAAA;line-height:1.6;">
          Correo generado autom&aacute;ticamente &mdash; Por favor no responder.
        </p>
      </td>
    </tr>

  </table>
</td></tr>
</table>
</body>
</html>"""


async def enviar_notificacion_transferencia(
    recipient_email: str,
    sender_name:     str,
    title:           str | None,
    message:         str | None,
    token:           str,
    expires_at:      str,
    cantidad_archivos: int = 0,
) -> None:
    if not configuracion.MAIL_HOST:
        logger.warning("SMTP no configurado — se omite el envío de correo.")
        return

    url_descarga   = f"{configuracion.app_base_url}/t/{token}"
    titulo_subject = _sanear_subject(title or "Transferencia de archivos")

    raiz = MIMEMultipart("alternative")
    raiz["Subject"] = f"[SNM FileDrop] {titulo_subject} — de {_sanear_subject(sender_name)}"
    raiz["From"]    = f"{configuracion.MAIL_FROM_NAME} <{configuracion.MAIL_FROM}>"
    raiz["To"]      = recipient_email

    html = _construir_html(sender_name, title, message, url_descarga, cantidad_archivos, expires_at)
    raiz.attach(MIMEText(html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            raiz,
            hostname=configuracion.MAIL_HOST,
            port=configuracion.MAIL_PORT,
            use_tls=False,
            start_tls=False,
            username=configuracion.MAIL_USERNAME or None,
            password=configuracion.MAIL_PASSWORD or None,
        )
        logger.info(f"Correo enviado a {recipient_email} — token {token}")
    except Exception as e:
        logger.error(f"Error al enviar correo a {recipient_email}: {e}")
