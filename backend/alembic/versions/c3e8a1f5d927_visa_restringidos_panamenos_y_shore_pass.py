"""Visa para las nacionalidades restringidas, panameños sin visa ni boleto y Shore Pass solo para marinos

Revision ID: c3e8a1f5d927
Revises: f8b3d1e6a492
Create Date: 2026-11-14

Pedido del usuario (2026-11-14):

  - A todo pasajero de nacionalidad restringida, en cualquier trámite y rango, se
    le exige un documento nuevo, «Visa» (DOC-VISA), uno por pasajero. Quien además
    deba presentar la Visa Especial de Marino (el marino y el pasajero en Embarque y
    Cambio de nave) sube las dos.
  - A los panameños no se les pide visa ni boleto aéreo en Embarque y Desembarque,
    ni la Visa Especial de Marino en Cambio de nave: condición nueva
    `solo_extranjeros` en esas filas. El marino panameño presenta Generales de
    pasaporte y Libreta; el pasajero y el militar panameños, solo Generales.
  - El Sellado de Shore Pass admite solo el rango Marino.

Las solicitudes ya enviadas conservan su foto del checklist; una devuelta se corrige
con las reglas nuevas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3e8a1f5d927'
down_revision: Union[str, None] = 'f8b3d1e6a492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VISA = ('DOC-VISA', 'Visa', 'Para el pasajero de nacionalidad restringida.')
# (trámite, documento) que ya no se piden a los panameños.
SIN_PANAMENOS = (
    ('F3-EMBARQUE', 'DOC-VISA-MARINO'),
    ('F3-EMBARQUE', 'DOC-BOLETO-AEREO'),
    ('F3-DESEMBARQUE', 'DOC-BOLETO-AEREO'),
    ('F3-CAMBIO-NAVE', 'DOC-VISA-MARINO'),
)
RANGOS = postgresql.ARRAY(sa.String(length=20))


def _condicion(antes: str, despues: str) -> None:
    for tramite, documento in SIN_PANAMENOS:
        op.execute(sa.text("""
            UPDATE tramite_documentos SET condicion = :despues
             WHERE condicion = :antes
               AND tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = :tramite)
               AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = :documento)
        """).bindparams(antes=antes, despues=despues, tramite=tramite, documento=documento))


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO documentos_requeridos (codigo, nombre, descripcion, requiere_libreta)
        VALUES (:codigo, :nombre, :descripcion, false)
        ON CONFLICT (codigo) DO NOTHING
    """).bindparams(codigo=VISA[0], nombre=VISA[1], descripcion=VISA[2]))
    # En todos los trámites (también en el desactivado: una devuelta la pide al
    # corregirse), para cualquier rango, al final del checklist.
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
        SELECT t.id, d.id, 'marino', 'nacionalidad_restringida',
               COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1
          FROM tipos_tramite t, documentos_requeridos d
         WHERE d.codigo = :codigo
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(codigo=VISA[0]))

    _condicion('siempre', 'solo_extranjeros')

    op.execute(sa.text("UPDATE tipos_tramite SET rangos_permitidos = :rangos WHERE codigo = 'F3-SHORE-PASS'")
               .bindparams(sa.bindparam('rangos', value=['marino'], type_=RANGOS)))


def downgrade() -> None:
    op.execute("UPDATE tipos_tramite SET rangos_permitidos = NULL WHERE codigo = 'F3-SHORE-PASS'")
    _condicion('solo_extranjeros', 'siempre')
    op.execute("""
        DELETE FROM tramite_documentos
         WHERE documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-VISA')
    """)
    # El documento se borra solo si ninguna solicitud lo usó (la foto y los archivos lo referencian).
    op.execute("""
        DELETE FROM documentos_requeridos d
         WHERE d.codigo = 'DOC-VISA'
           AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
    """)
