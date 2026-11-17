"""Subir y bajar en Embarque y Desembarque (la Carta Form. 7 de cada pasajero) y ocupación opcional

Revision ID: a7c2e9f4b618
Revises: e5c1a7d3b902
Create Date: 2026-11-16

Pedido del usuario (2026-11-16):

  - En Embarque y Desembarque el formulario pregunta «¿Subir y bajar?» (Sí / No):
    `tipos_tramite.permite_subir_y_bajar` dice qué trámites lo ofrecen y
    `solicitudes.subir_y_bajar` guarda la respuesta.
  - Con «Sí», cada pasajero (marino, pasajero o militar) adjunta la Carta de
    Responsabilidad (Form. No. 7): una fila del catálogo con la condición nueva
    `subir_y_bajar`. Lo demás del trámite se sigue pidiendo.
  - La ocupación del pasajero sale del formulario: la columna admite nulo y las
    solicitudes ya enviadas conservan la suya.

Las solicitudes ya enviadas conservan su foto del checklist; una devuelta se corrige
con las reglas nuevas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c2e9f4b618'
down_revision: Union[str, None] = 'e5c1a7d3b902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CON_SUBIR_Y_BAJAR = ('F3-EMBARQUE', 'F3-DESEMBARQUE')
CARTA = 'DOC-FORM7-RESPONSABILIDAD'


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('permite_subir_y_bajar', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.execute(sa.text("UPDATE tipos_tramite SET permite_subir_y_bajar = true WHERE codigo IN :codigos")
               .bindparams(sa.bindparam('codigos', value=CON_SUBIR_Y_BAJAR, expanding=True)))
    op.add_column('solicitudes', sa.Column('subir_y_bajar', sa.Boolean(), nullable=False, server_default=sa.false()))

    # La Carta de cada pasajero, al final del checklist (como la Visa del 2026-11-14), para
    # cualquier rango del trámite: Embarque y Desembarque admiten Marino, Pasajero y Militar.
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
        SELECT t.id, d.id, 'marino', 'subir_y_bajar',
               COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1
          FROM tipos_tramite t, documentos_requeridos d
         WHERE t.codigo IN :codigos AND d.codigo = :carta
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(sa.bindparam('codigos', value=CON_SUBIR_Y_BAJAR, expanding=True), carta=CARTA))

    op.alter_column('solicitud_tripulantes', 'ocupacion', existing_type=sa.String(length=150), nullable=True)


def downgrade() -> None:
    # Sin el dato, la columna vuelve a ser obligatoria: los pasajeros sin ocupación quedan en blanco.
    op.execute("UPDATE solicitud_tripulantes SET ocupacion = '' WHERE ocupacion IS NULL")
    op.alter_column('solicitud_tripulantes', 'ocupacion', existing_type=sa.String(length=150), nullable=False)
    op.execute("DELETE FROM tramite_documentos WHERE condicion = 'subir_y_bajar'")
    op.drop_column('solicitudes', 'subir_y_bajar')
    op.drop_column('tipos_tramite', 'permite_subir_y_bajar')
