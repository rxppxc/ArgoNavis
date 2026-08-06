"""agregar_catalogo_navieras

Vuelve a agregar un catálogo de navieras (tabla `navieras`), esta vez SIN FK
desde `transfers`: solo alimenta el desplegable de selección en el frontend.
`transfers.naviera` sigue siendo texto libre — decisión explícita para no
reintroducir la complejidad de la relación que se quitó en
a1f3c9d7e2b4_eliminar_catalogo_navieras.

Revision ID: c4d7f8a1b3e6
Revises: b7e5a2f1c8d9
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d7f8a1b3e6'
down_revision: Union[str, None] = 'b7e5a2f1c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'navieras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=255), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_navieras_id'), 'navieras', ['id'], unique=False)

    # Siembra el catálogo con los nombres de naviera ya usados en
    # transferencias existentes, para no perder lo que ya se venía escribiendo
    # como texto libre.
    op.execute(sa.text("""
        INSERT INTO navieras (nombre)
        SELECT DISTINCT naviera FROM transfers
        WHERE naviera IS NOT NULL AND btrim(naviera) <> ''
        ORDER BY naviera
    """))


def downgrade() -> None:
    op.drop_index(op.f('ix_navieras_id'), table_name='navieras')
    op.drop_table('navieras')
