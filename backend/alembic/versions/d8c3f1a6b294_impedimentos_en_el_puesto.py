"""impedimentos_en_el_puesto

El puesto de control también verifica los impedimentos en SIMPLUS antes de
finalizar (pedido del usuario del 2026-11-06). Es una verificación aparte de
la de UCVMM, con sus propias columnas, para que una no pise a la otra:

  - `solicitud_tripulantes.con_impedimento_puesto`: el resultado de cada
    tripulante en el puesto (nulo = sin verificar).
  - `solicitudes.impedimentos_puesto_verificados`, `comentario_impedimentos_puesto`,
    `impedimentos_puesto_en` e `impedimentos_puesto_por_id`: como las de UCVMM.
  - Texto de T-FINALIZAR-PUERTO: suma la verificación.

Las finalizadas antes del cambio quedan sin verificación del puesto; las
aprobadas pendientes la piden antes de finalizarse.

Revision ID: d8c3f1a6b294
Revises: b2e7d4c9a160
Create Date: 2026-11-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8c3f1a6b294'
down_revision: Union[str, None] = 'b2e7d4c9a160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISO_PUESTO = 'T-FINALIZAR-PUERTO'
TEXTO_PUESTO = ('Ve las autorizaciones aprobadas de los puestos de control que tiene asignados, '
                'verifica los impedimentos en SIMPLUS y las finaliza en el puesto autorizado.')
TEXTO_PUESTO_ANTES = ('Ve las autorizaciones aprobadas de los puestos de control que tiene asignados '
                      'y las finaliza en el puesto autorizado.')


def _texto_permiso(descripcion: str):
    return sa.text("UPDATE permisos SET descripcion = :d WHERE codigo = :c").bindparams(d=descripcion, c=PERMISO_PUESTO)


def upgrade() -> None:
    op.add_column('solicitud_tripulantes', sa.Column('con_impedimento_puesto', sa.Boolean(), nullable=True))
    op.add_column('solicitudes', sa.Column(
        'impedimentos_puesto_verificados', sa.Boolean(), server_default='false', nullable=False,
    ))
    op.add_column('solicitudes', sa.Column('comentario_impedimentos_puesto', sa.Text(), nullable=True))
    op.add_column('solicitudes', sa.Column('impedimentos_puesto_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('solicitudes', sa.Column(
        'impedimentos_puesto_por_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True,
    ))
    op.execute(_texto_permiso(TEXTO_PUESTO))


def downgrade() -> None:
    op.execute(_texto_permiso(TEXTO_PUESTO_ANTES))
    # La FK hacia users se va con su columna.
    op.drop_column('solicitudes', 'impedimentos_puesto_por_id')
    op.drop_column('solicitudes', 'impedimentos_puesto_en')
    op.drop_column('solicitudes', 'comentario_impedimentos_puesto')
    op.drop_column('solicitudes', 'impedimentos_puesto_verificados')
    op.drop_column('solicitud_tripulantes', 'con_impedimento_puesto')
