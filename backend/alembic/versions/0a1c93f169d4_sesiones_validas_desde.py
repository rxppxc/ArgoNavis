"""sesiones_validas_desde

`users.sesiones_validas_desde`: los tokens emitidos antes de este momento ya
no sirven. Se fija al cerrar sesión y al cambiar o restablecer la contraseña,
para que un token copiado no siga funcionando hasta vencer. NULL = ningún
cierre registrado (todos los tokens vigentes valen).

Revision ID: 0a1c93f169d4
Revises: c7a2e94b1f30
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0a1c93f169d4'
down_revision: Union[str, None] = 'c7a2e94b1f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('sesiones_validas_desde', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'sesiones_validas_desde')
