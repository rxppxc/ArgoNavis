"""Consultar las autorizaciones muchos años después

Revision ID: c6e2a9f1d438
Revises: b5e1c8d4f207
Create Date: 2026-11-22

Pedido del usuario (2026-11-22): las solicitudes aprobadas y finalizadas se tienen que
poder consultar muchos años después.

  - `busqueda`, en la solicitud y en cada tripulante: lo que se busca en un solo texto, sin
    tildes y en minúsculas. Lo calcula PostgreSQL y lleva un índice de trigramas, que sirve
    para buscar en cualquier parte del texto. Con 10 años de datos simulados, buscar un
    pasaporte recorría la tabla entera: 12 segundos.
  - Un índice por la fecha de la operación.
  - `sector_revision_id`: el sector de UCVMM que revisó (aprobó, devolvió o denegó) la
    solicitud, que la conserva aunque el puesto cambie de sector. Nulo mientras nadie la ha
    revisado: es del sector del puesto. Las que ya existen quedan con el sector de hoy.

`pg_trgm` viene con PostgreSQL y es una extensión de confianza: la crea la dueña de la base,
sin ser superusuario. Al bajar no se quita: puede usarla otra cosa de la base.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6e2a9f1d438'
down_revision: Union[str, None] = 'b5e1c8d4f207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (tabla, lo que se busca en ella): separado por espacios, para que una palabra no coincida
# a caballo entre dos datos.
BUSQUEDA = {
    'solicitudes': ("coalesce(numero, '') || ' ' || titulo || ' ' || coalesce(nombre_buque, '') || ' ' || "
                    "coalesce(imo, '') || ' ' || agencia_nombre || ' ' || puesto_nombre || ' ' || "
                    "coalesce(puesto_destino_nombre, '')"),
    'solicitud_tripulantes': "nombre || ' ' || apellido || ' ' || pasaporte || ' ' || coalesce(libreta_marino, '')",
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for tabla, texto in BUSQUEDA.items():
        # Sin tildes: se separan de su letra (NFD) y se quitan (U+0300 a U+036F). Lo mismo
        # hace la consulta con lo que se escribe (RepositorioSolicitud, `_plano`).
        op.execute(rf"""
            ALTER TABLE {tabla} ADD COLUMN busqueda text GENERATED ALWAYS AS (
                lower(regexp_replace(normalize({texto}, NFD), '[̀-ͯ]', '', 'g'))
            ) STORED
        """)
        op.execute(f"CREATE INDEX ix_{tabla}_busqueda ON {tabla} USING gin (busqueda gin_trgm_ops)")
    op.create_index('ix_solicitudes_fecha_operacion', 'solicitudes', ['fecha_operacion'])

    op.add_column('solicitudes', sa.Column('sector_revision_id', sa.Integer(), nullable=True))
    op.execute("""
        UPDATE solicitudes s SET sector_revision_id = p.sector_id
          FROM puestos_control p
         WHERE p.id = s.puesto_control_id AND s.estado <> 'review'
    """)
    op.create_foreign_key('fk_solicitudes_sector_revision', 'solicitudes', 'sectores',
                          ['sector_revision_id'], ['id'], ondelete='RESTRICT')
    # Con el puesto: los puestos de los que un sector conserva solicitudes salen del índice.
    op.create_index('ix_solicitudes_sector_revision', 'solicitudes', ['sector_revision_id', 'puesto_control_id'])


def downgrade() -> None:
    op.drop_index('ix_solicitudes_sector_revision', table_name='solicitudes')
    op.drop_constraint('fk_solicitudes_sector_revision', 'solicitudes', type_='foreignkey')
    op.drop_column('solicitudes', 'sector_revision_id')
    op.drop_index('ix_solicitudes_fecha_operacion', table_name='solicitudes')
    for tabla in BUSQUEDA:   # el índice se va con la columna
        op.drop_column(tabla, 'busqueda')
