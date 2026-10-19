"""Descripción de cada tipo de trámite.

Una línea que dice cuándo se usa el trámite. La agencia la ve en las tarjetas
del paso 1 de «Nueva solicitud» (antes era una lista desplegable con los
nombres solos). Vive en el catálogo, como el resto del checklist. Es una
primera versión, a validar con UCVMM: se apoya en los documentos que pide
cada trámite (p. ej. el boleto aéreo del Desembarque, la cita del consulado
de la Renovación de Pasaporte).

Revision ID: a3d9c6e1f584
Revises: b5c2e8f4a713
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from alembic import op

revision = "a3d9c6e1f584"
down_revision = "b5c2e8f4a713"
branch_labels = None
depends_on = None

DESCRIPCIONES = {
    "F3-EMBARQUE":        "Tripulantes que suben a un buque en un puerto de Panamá.",
    "F3-DESEMBARQUE":     "Tripulantes que bajan del buque y salen del país.",
    "F3-CAMBIO-PUERTO":   "La operación pasa a otro puerto de Panamá.",
    "F3-CAMBIO-NAVE":     "Tripulantes que pasan a otra nave.",
    "F3-RENOV-PASAPORTE": "Tripulantes que bajan a renovar el pasaporte en su consulado.",
    "F3-TECNICO":         "Técnicos, superintendentes o supernumerarios que suben al buque.",
    "F3-SHORE-PASS":      "Para que la tripulación baje a tierra mientras el buque está en puerto.",
    "F3-URGENCIA-MEDICA": "Traslado de un tripulante a una clínica u hospital.",
}


def upgrade() -> None:
    op.add_column("tipos_tramite", sa.Column("descripcion", sa.String(length=300), nullable=True))
    cx = op.get_bind()
    for codigo, descripcion in DESCRIPCIONES.items():
        cx.execute(sa.text("UPDATE tipos_tramite SET descripcion = :descripcion WHERE codigo = :codigo"),
                   {"descripcion": descripcion, "codigo": codigo})


def downgrade() -> None:
    op.drop_column("tipos_tramite", "descripcion")
