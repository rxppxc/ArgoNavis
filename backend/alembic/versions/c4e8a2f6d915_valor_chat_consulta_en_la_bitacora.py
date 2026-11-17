"""CHAT_CONSULTA también en las bases nuevas

El tipo `accionauditoria` de la bitácora nace en la línea base (d93ac0ca2d1c) sin
CHAT_CONSULTA: ese valor lo dejó una función de chat ya retirada, que lo agregaba
fuera de las migraciones. Lo tienen las bases viejas y el ORM lo conserva para leer
sus registros (models/audit_log.py), pero una base creada desde cero no lo tenía.
Lo encontró la revisión del esquema al arrancar (infrastructure/esquema.py,
2026-11-17), que si no habría dejado la API en 503 en cada instalación nueva.

En las bases que ya lo tienen no hace nada (IF NOT EXISTS).

Revision ID: c4e8a2f6d915
Revises: a7c2e9f4b618
Create Date: 2026-11-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c4e8a2f6d915'
down_revision: Union[str, None] = 'a7c2e9f4b618'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE no puede ir en la transacción que lo usa.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE accionauditoria ADD VALUE IF NOT EXISTS 'CHAT_CONSULTA'")


def downgrade() -> None:
    # El valor queda en el enum: PostgreSQL no quita valores de un enum, y las bases
    # viejas lo tenían desde antes de esta revisión.
    pass
