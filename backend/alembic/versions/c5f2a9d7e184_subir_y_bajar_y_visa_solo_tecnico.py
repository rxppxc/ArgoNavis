"""«Subir y bajar» y la «Visa», solo en el trámite de Técnico

Revision ID: c5f2a9d7e184
Revises: a6d2f8c3e417
Create Date: 2026-11-26

Pedido del usuario (2026-11-26):

  - La operación «Subir y bajar» va solo en la Autorización de Técnico, Superintendente o
    Supernumerario. Urgencia médica, que pide la operación desde a6d2f8c3e417, ofrece solo
    Embarque o Desembarque. `tipos_tramite.operaciones` dice cuáles ofrece cada trámite que la
    pide (nulo en los que no la piden).
  - La «Visa» (DOC-VISA) de los restringidos va solo en el trámite de Técnico: se quitan sus
    filas de los demás (desde el 2026-11-18 se le pedía al Militar de esos trámites). Al Marino
    y al Pasajero restringidos se les sigue pidiendo la Visa Especial de Marino.

Las solicitudes ya enviadas conservan la foto de su checklist (`solicitud_casillas`) y su
operación: nada de esto las cambia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c5f2a9d7e184'
down_revision: Union[str, None] = 'a6d2f8c3e417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPERACIONES = postgresql.ARRAY(sa.String(length=20))
VISA = "(SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-VISA')"
# Las filas de la «Visa» del Militar fuera del trámite de Técnico, con su orden (para volver atrás).
VISA_DEL_MILITAR = {
    'F3-EMBARQUE': 7, 'F3-DESEMBARQUE': 8, 'F3-URGENCIA-MEDICA': 6, 'F3-RENOV-PASAPORTE': 7,
    'F3-CAMBIO-NAVE': 4, 'F3-CAMBIO-PUERTO': 4,
}


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('operaciones', OPERACIONES, nullable=True))
    op.execute("UPDATE tipos_tramite SET operaciones = ARRAY['embarque', 'desembarque', 'subir_y_bajar']::varchar[] "
               "WHERE codigo = 'F3-TECNICO'")
    op.execute("UPDATE tipos_tramite SET operaciones = ARRAY['embarque', 'desembarque']::varchar[] "
               "WHERE codigo = 'F3-URGENCIA-MEDICA'")
    op.execute(f"DELETE FROM tramite_documentos WHERE documento_id = {VISA} "
               "AND tipo_tramite_id IN (SELECT id FROM tipos_tramite WHERE codigo <> 'F3-TECNICO')")


def downgrade() -> None:
    for codigo, orden in VISA_DEL_MILITAR.items():
        op.execute(sa.text(f"""
            INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
            SELECT t.id, {VISA}, 'marino', 'nacionalidad_restringida', :orden, ARRAY['militar']::varchar[]
              FROM tipos_tramite t WHERE t.codigo = :codigo
        """).bindparams(codigo=codigo, orden=orden))
    op.drop_column('tipos_tramite', 'operaciones')
