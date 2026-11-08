"""novedades_vistas

Notificaciones internas (reunión del 2026-10-30): la campana de la cabecera
muestra lo que le toca hacer a cada rol (sale de las bandejas) y las novedades
de sus solicitudes (sale del historial, `solicitud_eventos`).

  - `users.novedades_vistas_hasta`: hasta cuándo vio cada usuario sus
    novedades. Las cuentas existentes empiezan sin novedades sin leer.
  - Índice en `solicitud_eventos.creado_en`: las novedades se buscan por fecha.
  - Texto de T-FINALIZAR-PUERTO: decía «indicando dónde terminó la operación»;
    desde la misma reunión se finaliza siempre en el puesto autorizado.

Revision ID: b2e7d4c9a160
Revises: f7a2c9e4b136
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2e7d4c9a160'
down_revision: Union[str, None] = 'f7a2c9e4b136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISO_PUESTO = 'T-FINALIZAR-PUERTO'
TEXTO_PUESTO = ('Ve las autorizaciones aprobadas de los puestos de control que tiene asignados '
                'y las finaliza en el puesto autorizado.')
TEXTO_PUESTO_ANTES = ('Ve las autorizaciones aprobadas de los puestos de control que tiene asignados '
                      'y las finaliza, indicando dónde terminó la operación.')


def _texto_permiso(descripcion: str):
    return sa.text("UPDATE permisos SET descripcion = :d WHERE codigo = :c").bindparams(d=descripcion, c=PERMISO_PUESTO)


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'novedades_vistas_hasta', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
    ))
    op.create_index('ix_solicitud_eventos_creado_en', 'solicitud_eventos', ['creado_en'])
    op.execute(_texto_permiso(TEXTO_PUESTO))


def downgrade() -> None:
    op.execute(_texto_permiso(TEXTO_PUESTO_ANTES))
    op.drop_index('ix_solicitud_eventos_creado_en', table_name='solicitud_eventos')
    op.drop_column('users', 'novedades_vistas_hasta')
