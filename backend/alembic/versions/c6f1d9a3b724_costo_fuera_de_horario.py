"""Costo migratorio de las solicitudes aprobadas fuera del horario laboral

Revision ID: c6f1d9a3b724
Revises: a8d4f2c6e913
Create Date: 2026-11-11

Aprobada fuera del horario laboral (lunes a viernes, de 07:00 a 15:00), la
solicitud tiene un costo migratorio (B/.20.00, `COSTO_FUERA_DE_HORARIO`) y la
agencia lo ve en la bandeja, el expediente, el correo de aprobación y el PDF.

  - `solicitudes.costo_fuera_de_horario`: el costo de ese momento, guardado al
    aprobar (foto, como el nombre de la agencia o el checklist): si el monto
    cambia, lo ya aprobado no. Las aprobadas antes de esta revisión quedan sin
    costo: se siguen mostrando fuera del horario, sin monto.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c6f1d9a3b724'
down_revision = 'a8d4f2c6e913'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('solicitudes', sa.Column('costo_fuera_de_horario', sa.Numeric(8, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('solicitudes', 'costo_fuera_de_horario')
