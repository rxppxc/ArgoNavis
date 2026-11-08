"""cola_de_correos

`correos_salida`: la cola de los avisos por correo. Cada aviso se guarda en la
misma transacción que la operación que lo genera y lo envía la cola
(infrastructure/cola_correos.py), que lo reintenta unas 24 horas. Antes los
reintentos vivían en memoria (30 s y 2 min): con el servidor de correo caído
más tiempo, o con un reinicio del backend, el aviso se perdía.

Solo agrega la tabla: no toca las demás ni la API.

Revision ID: c4e9a2f7b815
Revises: e6b1d4a9c372
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e9a2f7b815'
down_revision: Union[str, None] = 'e6b1d4a9c372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'correos_salida',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(length=20), nullable=False),
        sa.Column('asunto', sa.String(length=300), nullable=False),
        sa.Column('aviso', sa.JSON(), nullable=False),
        sa.Column('estado', sa.String(length=10), server_default='pendiente', nullable=False),
        sa.Column('intentos', sa.Integer(), server_default='0', nullable=False),
        sa.Column('proximo_intento', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ultimo_error', sa.String(length=500), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('enviado_en', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estado IN ('pendiente', 'enviado', 'fallido')", name='ck_correos_salida_estado'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Lo que busca la tarea de correos: los pendientes que ya tocan.
    op.create_index('ix_correos_salida_pendientes', 'correos_salida', ['proximo_intento'], unique=False,
                    postgresql_where=sa.text("estado = 'pendiente'"))


def downgrade() -> None:
    op.drop_index('ix_correos_salida_pendientes', table_name='correos_salida',
                  postgresql_where=sa.text("estado = 'pendiente'"))
    op.drop_table('correos_salida')
