"""Rutas de los documentos relativas a STORAGE_PATH.

`solicitud_documentos.ruta` guardaba la ruta absoluta de cada archivo (p. ej.
C:\\...\\backend\\storage\\...\\solicitud-12\\abc.pdf). Mover o renombrar la
carpeta de documentos, o la del proyecto, dejaba los documentos inaccesibles.
Desde aquí se guarda relativa a STORAGE_PATH ("solicitud-12/abc.pdf"): la
carpeta se puede mover cambiando solo STORAGE_PATH.

Revision ID: b5c2e8f4a713
Revises: 7e3f1a9c2d64
Create Date: 2026-10-16
"""
from pathlib import Path, PurePosixPath, PureWindowsPath

import sqlalchemy as sa
from alembic import op

revision = "b5c2e8f4a713"
down_revision = "7e3f1a9c2d64"
branch_labels = None
depends_on = None


def _relativa(ruta: str) -> str | None:
    """«…/solicitud-12/abc.pdf» → «solicitud-12/abc.pdf», venga con barras de
    Windows o de Linux. None si no tiene esa forma (se deja como está)."""
    partes = (PureWindowsPath(ruta) if "\\" in ruta else PurePosixPath(ruta)).parts
    if len(partes) >= 2 and partes[-2].startswith("solicitud-"):
        return f"{partes[-2]}/{partes[-1]}"
    return None


def upgrade() -> None:
    cx = op.get_bind()
    for id_, ruta in cx.execute(sa.text("SELECT id, ruta FROM solicitud_documentos")).all():
        relativa = _relativa(ruta)
        if relativa and relativa != ruta:
            cx.execute(sa.text("UPDATE solicitud_documentos SET ruta = :ruta WHERE id = :id"),
                       {"ruta": relativa, "id": id_})


def downgrade() -> None:
    # La versión anterior espera rutas absolutas: se arman con la STORAGE_PATH actual.
    from app.core.config import obtener_configuracion

    raiz = Path(obtener_configuracion().STORAGE_PATH).resolve()
    cx = op.get_bind()
    for id_, ruta in cx.execute(sa.text("SELECT id, ruta FROM solicitud_documentos")).all():
        if not (PurePosixPath(ruta).is_absolute() or PureWindowsPath(ruta).is_absolute()):
            cx.execute(sa.text("UPDATE solicitud_documentos SET ruta = :ruta WHERE id = :id"),
                       {"ruta": str(raiz / ruta), "id": id_})
