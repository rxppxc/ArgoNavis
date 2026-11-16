"""Lo común a los PDF (reportlab): las fuentes, los colores y el texto seguro para
un Paragraph. Lo usan la autorización y el informe de estadísticas."""
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Sin ASCII85 (2026-11-10): reportlab, por defecto, pasa cada imagen y cada página
# comprimidas a texto ASCII85, un paso en Python puro que no hace falta (el PDF admite
# binario). Sin él, el PDF de las estadísticas tarda ~0,6 s en vez de ~0,7, el de la
# autorización ~0,19 en vez de ~0,23, y los dos pesan menos. Vale para todo el
# proceso: lo fija este módulo, que importan los dos.
rl_config.useA85 = 0

# Fuentes TrueType con cobertura Unicode amplia (nombres con ş, ł, ğ...). Si no
# hay ninguna en el servidor se usa Helvetica, que solo cubre Latin-1.
_CANDIDATOS_FUENTE = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
]
_fuentes: tuple[str, str] | None = None


def obtener_fuentes() -> tuple[str, str]:
    """(normal, negrita), registradas una vez por proceso."""
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


def color_pdf(hexa: str) -> colors.Color:
    """"#10233F" → el color de reportlab."""
    return colors.HexColor(hexa)


def texto_pdf(texto: str | None) -> str:
    """Texto (de un usuario o de la BD) listo para un Paragraph, que interpreta
    marcado: escapado, o "—" si no hay."""
    return escape(texto) if texto else "—"
