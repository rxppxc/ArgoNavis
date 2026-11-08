"""documentos_por_rango

Decisión de la reunión del 2026-10-30: a los tripulantes de rango distinto de
Marino (militar, técnico, supernumerario, superintendente) se les piden solo
las Generales de pasaporte y la Copia de Boleto Aéreo. Al Marino, lo de antes.

  - `tramite_documentos.rangos`: a qué rangos se pide cada documento (nulo = a
    todos). Va por fila y no por documento: el boleto lo pide Desembarque a
    todos y los demás trámites solo a los no marinos.
  - Los documentos por tripulante que no son las Generales, el Boleto ni la
    Libreta (esta ya va solo al Marino por `requiere_libreta`) pasan a ser solo
    del Marino: Visa Especial de Marino, Carta Form. 7, Reporte médico, cita
    del consulado y Form. No. 6.
  - El Boleto Aéreo se pide a los no marinos en los trámites que no lo pedían.
  - Técnico (que solo admite rangos no marinos) deja la Carta: ya no se le
    pediría a nadie.

Las solicitudes ya enviadas conservan su checklist (`solicitud_casillas`); una
corrección se valida con las reglas nuevas.

Revision ID: f7a2c9e4b136
Revises: c4e9a2f7b815
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f7a2c9e4b136'
down_revision: Union[str, None] = 'c4e9a2f7b815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NO_MARINOS = ['militar', 'tecnico', 'supernumerario', 'superintendente']
# Lo que se pide a todo rango (la Libreta queda fuera por `requiere_libreta`).
COMUNES = ['DOC-GENERALES-PASAPORTE', 'DOC-BOLETO-AEREO']


def upgrade() -> None:
    op.add_column('tramite_documentos', sa.Column('rangos', postgresql.ARRAY(sa.String(length=20)), nullable=True))

    op.execute("""
        DELETE FROM tramite_documentos
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-TECNICO')
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-FORM7-RESPONSABILIDAD')
    """)
    op.execute(
        sa.text("""
            UPDATE tramite_documentos td SET rangos = ARRAY['marino']::varchar[]
              FROM documentos_requeridos d
             WHERE d.id = td.documento_id AND td.alcance = 'marino'
               AND NOT d.requiere_libreta AND d.codigo NOT IN :comunes
        """).bindparams(sa.bindparam('comunes', value=COMUNES, expanding=True))
    )
    op.execute(
        sa.text("""
            INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
            SELECT t.id, d.id, 'marino', 'siempre',
                   COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1,
                   :rangos
              FROM tipos_tramite t
              JOIN documentos_requeridos d ON d.codigo = 'DOC-BOLETO-AEREO'
             WHERE NOT EXISTS (
                   SELECT 1 FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id AND x.documento_id = d.id)
        """).bindparams(sa.bindparam('rangos', value=NO_MARINOS, type_=postgresql.ARRAY(sa.String(length=20))))
    )


def downgrade() -> None:
    # Los boletos agregados son los que tienen rangos (el de Desembarque es de todos).
    op.execute("""
        DELETE FROM tramite_documentos
         WHERE rangos IS NOT NULL
           AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-BOLETO-AEREO')
    """)
    op.execute("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
        SELECT t.id, d.id, 'marino', 'siempre', 1
          FROM tipos_tramite t
          JOIN documentos_requeridos d ON d.codigo = 'DOC-FORM7-RESPONSABILIDAD'
         WHERE t.codigo = 'F3-TECNICO'
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """)
    op.drop_column('tramite_documentos', 'rangos')
