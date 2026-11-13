"""Cambio de puerto dentro de la solicitud y el Formulario No. 3 en todos los trámites

Revision ID: e5c2a8f1d376
Revises: c6f1d9a3b724
Create Date: 2026-11-13

Pedido del usuario (2026-11-13):

  - El trámite «Cambio de Puerto» deja de ser uno aparte: en cualquier trámite
    la agencia indica si hay cambio de puerto y elige el nuevo puesto de control,
    que tiene que ser del mismo sector que el primero (si el nuevo puerto es del
    otro sector, presenta una solicitud nueva y esta vence sola). El trámite se
    desactiva, no se borra: las solicitudes que ya lo usan lo conservan, y una
    devuelta se sigue pudiendo corregir.
  - `solicitudes.puesto_destino_id` y `puesto_destino_nombre` (foto, como
    `puesto_nombre`): el nuevo puesto. Nulo = sin cambio de puerto. Con cambio,
    lo ve y lo finaliza el puesto nuevo; el primero lo puede consultar.
  - El Formulario No. 3 (DOC-FORMULARIO-3) se pide en todos los trámites, uno
    por solicitud, con todos los pasajeros y para cualquier rango. Convive con
    la Lista de Tripulantes donde ya se pedía. Va primero entre los documentos
    de la solicitud. Las solicitudes ya enviadas conservan su foto del checklist;
    una devuelta lo pide al corregirse.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5c2a8f1d376'
down_revision: Union[str, None] = 'c6f1d9a3b724'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FORMULARIO_3 = (
    'DOC-FORMULARIO-3', 'Formulario No. 3',
    'Uno por solicitud, con los datos del trámite y todos los pasajeros.',
)


def upgrade() -> None:
    op.add_column('solicitudes', sa.Column('puesto_destino_id', sa.Integer(), nullable=True))
    op.add_column('solicitudes', sa.Column('puesto_destino_nombre', sa.String(length=200), nullable=True))
    op.create_foreign_key(
        'fk_solicitudes_puesto_destino', 'solicitudes', 'puestos_control',
        ['puesto_destino_id'], ['id'], ondelete='RESTRICT',
    )
    # La bandeja y la campana del puesto filtran por él; y borrar un puesto lo consulta.
    op.create_index('ix_solicitudes_puesto_destino_id', 'solicitudes', ['puesto_destino_id'])

    op.execute("UPDATE tipos_tramite SET activo = false WHERE codigo = 'F3-CAMBIO-PUERTO'")

    op.execute(sa.text("""
        INSERT INTO documentos_requeridos (codigo, nombre, descripcion, requiere_libreta)
        VALUES (:codigo, :nombre, :descripcion, false)
        ON CONFLICT (codigo) DO NOTHING
    """).bindparams(codigo=FORMULARIO_3[0], nombre=FORMULARIO_3[1], descripcion=FORMULARIO_3[2]))
    # En todos los trámites (también en el desactivado: una devuelta lo pide al
    # corregirse), primero en el checklist.
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
        SELECT t.id, d.id, 'solicitud', 'siempre',
               COALESCE((SELECT min(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 1) - 1
          FROM tipos_tramite t, documentos_requeridos d
         WHERE d.codigo = :codigo
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(codigo=FORMULARIO_3[0]))


def downgrade() -> None:
    op.execute("""
        DELETE FROM tramite_documentos
         WHERE documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-FORMULARIO-3')
    """)
    # El documento se borra solo si ninguna solicitud lo usó (la foto y los archivos lo referencian).
    op.execute("""
        DELETE FROM documentos_requeridos d
         WHERE d.codigo = 'DOC-FORMULARIO-3'
           AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
    """)
    op.execute("UPDATE tipos_tramite SET activo = true WHERE codigo = 'F3-CAMBIO-PUERTO'")
    op.drop_index('ix_solicitudes_puesto_destino_id', table_name='solicitudes')
    op.drop_constraint('fk_solicitudes_puesto_destino', 'solicitudes', type_='foreignkey')
    op.drop_column('solicitudes', 'puesto_destino_nombre')
    op.drop_column('solicitudes', 'puesto_destino_id')
