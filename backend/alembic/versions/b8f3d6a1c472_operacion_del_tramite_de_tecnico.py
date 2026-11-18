"""La operación del trámite de Técnico: Embarque, Desembarque o Subir y bajar

Revision ID: b8f3d6a1c472
Revises: c4e8a2f6d915
Create Date: 2026-11-18

Pedido del usuario (2026-11-18): en la Autorización de Técnico, Superintendente o
Supernumerario, el formulario pide la operación (Embarque, Desembarque o Subir y
bajar). Es obligatoria, empieza sin elegir y solo se registra: los documentos no
cambian (decisión del usuario). Se ve en el expediente, la bandeja, el PDF de la
autorización y la boleta de recargo.

  - `tipos_tramite.pide_operacion` dice qué trámites la piden (hoy, F3-TECNICO).
  - `solicitudes.operacion` guarda la respuesta. Nula en los demás trámites y en
    las solicitudes de antes, que no la tienen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8f3d6a1c472'
down_revision: Union[str, None] = 'c4e8a2f6d915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPERACIONES = "('embarque', 'desembarque', 'subir_y_bajar')"


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('pide_operacion', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.execute("UPDATE tipos_tramite SET pide_operacion = true WHERE codigo = 'F3-TECNICO'")
    op.add_column('solicitudes', sa.Column('operacion', sa.String(length=20), nullable=True))
    op.create_check_constraint('ck_solicitudes_operacion', 'solicitudes', f"operacion IN {OPERACIONES}")


def downgrade() -> None:
    op.drop_constraint('ck_solicitudes_operacion', 'solicitudes', type_='check')
    op.drop_column('solicitudes', 'operacion')
    op.drop_column('tipos_tramite', 'pide_operacion')
