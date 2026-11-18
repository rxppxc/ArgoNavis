"""Los días del sellado de Shore Pass: 5 o 15

Revision ID: d2a7c5e9f831
Revises: b8f3d6a1c472
Create Date: 2026-11-18

Pedido del usuario (2026-11-18): en el Sellado de Shore Pass, el formulario pide si el
sellado es de 5 o de 15 días. Es obligatorio, empieza sin elegir y solo se registra: no
cambia los documentos ni la vigencia de la autorización (decisión del usuario). Se ve
donde la operación del trámite de Técnico: el expediente, la bandeja, el PDF de la
autorización y la boleta de recargo.

  - `tipos_tramite.pide_dias_sellado` dice qué trámites los piden (hoy, F3-SHORE-PASS).
  - `solicitudes.dias_sellado` guarda la respuesta. Nula en los demás trámites y en las
    solicitudes de antes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2a7c5e9f831'
down_revision: Union[str, None] = 'b8f3d6a1c472'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('pide_dias_sellado', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.execute("UPDATE tipos_tramite SET pide_dias_sellado = true WHERE codigo = 'F3-SHORE-PASS'")
    op.add_column('solicitudes', sa.Column('dias_sellado', sa.SmallInteger(), nullable=True))
    op.create_check_constraint('ck_solicitudes_dias_sellado', 'solicitudes', "dias_sellado IN (5, 15)")


def downgrade() -> None:
    op.drop_constraint('ck_solicitudes_dias_sellado', 'solicitudes', type_='check')
    op.drop_column('solicitudes', 'dias_sellado')
    op.drop_column('tipos_tramite', 'pide_dias_sellado')
