"""checklist_por_solicitud

`solicitud_casillas`: la foto del checklist con el que se envió (o se corrigió
por última vez) cada solicitud. El expediente se evalúa contra esta foto y no
contra el catálogo de hoy: así un cambio del catálogo (como el de
`b9e4d17a3c52`, que pasó la Carta de Responsabilidad y el Reporte Médico a
"por tripulante") no deja como incompletas solicitudes que cumplían cuando se
enviaron, ni altera expedientes ya cerrados. Una corrección de la agencia se
valida con las reglas del día y vuelve a tomar la foto.

Relleno: para las solicitudes existentes, las casillas son los documentos del
checklist que de verdad se presentaron (al enviar se exigía el checklist
completo de ese momento), con el orden del catálogo.

Revision ID: 7e3f1a9c2d64
Revises: 0a1c93f169d4
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7e3f1a9c2d64'
down_revision: Union[str, None] = '0a1c93f169d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RELLENO = """
INSERT INTO solicitud_casillas (solicitud_id, documento_id, tripulante_id, orden)
SELECT x.solicitud_id, x.documento_id, x.tripulante_id,
       ROW_NUMBER() OVER (
           PARTITION BY x.solicitud_id
           ORDER BY COALESCE(td.orden, 1000), COALESCE(st.orden, -1), x.documento_id
       ) - 1
FROM (
    SELECT DISTINCT solicitud_id, documento_id, tripulante_id
    FROM solicitud_documentos
    WHERE documento_id IS NOT NULL
) x
JOIN solicitudes s ON s.id = x.solicitud_id
LEFT JOIN tramite_documentos td ON td.tipo_tramite_id = s.tipo_tramite_id AND td.documento_id = x.documento_id
LEFT JOIN solicitud_tripulantes st ON st.id = x.tripulante_id
"""


def upgrade() -> None:
    op.create_table(
        'solicitud_casillas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('solicitud_id', sa.Integer(), nullable=False),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('tripulante_id', sa.Integer(), nullable=True),
        sa.Column('orden', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['solicitud_id'], ['solicitudes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos_requeridos.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tripulante_id'], ['solicitud_tripulantes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitud_casillas_id'), 'solicitud_casillas', ['id'], unique=False)
    for columna in ('solicitud_id', 'tripulante_id'):
        op.create_index(op.f(f'ix_solicitud_casillas_{columna}'), 'solicitud_casillas', [columna], unique=False)
    op.execute(RELLENO)


def downgrade() -> None:
    for columna in ('tripulante_id', 'solicitud_id', 'id'):
        op.drop_index(op.f(f'ix_solicitud_casillas_{columna}'), table_name='solicitud_casillas')
    op.drop_table('solicitud_casillas')
