"""indices_de_rendimiento

Índices que faltaban para las consultas que más crecen con el tiempo (revisión
del 2026-11-08):

  - `solicitudes.created_at`: el periodo de las estadísticas filtra por él
    (como rango de instantes desde esta misma revisión, para que lo use).
  - `solicitudes.puesto_finalizacion_id`: es una FK sin índice. Al borrar un
    puesto, PostgreSQL recorría la tabla entera para comprobar el RESTRICT.
  - `audit_logs (accion, creado_en)`: la bitácora filtrada por acción, lo más
    reciente primero. Es la tabla que más crece (cada documento visto, cada
    login).

Revision ID: e7b2d5a9c4f1
Revises: d8c3f1a6b294
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e7b2d5a9c4f1'
down_revision: Union[str, None] = 'd8c3f1a6b294'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_solicitudes_created_at', 'solicitudes', ['created_at'], unique=False)
    op.create_index('ix_solicitudes_puesto_finalizacion_id', 'solicitudes', ['puesto_finalizacion_id'], unique=False)
    op.create_index('ix_audit_logs_accion_creado_en', 'audit_logs', ['accion', 'creado_en'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_logs_accion_creado_en', table_name='audit_logs')
    op.drop_index('ix_solicitudes_puesto_finalizacion_id', table_name='solicitudes')
    op.drop_index('ix_solicitudes_created_at', table_name='solicitudes')
