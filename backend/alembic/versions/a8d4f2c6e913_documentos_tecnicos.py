"""documentos_tecnicos

Pedido del usuario (2026-11-11): a los pasajeros de rango técnico,
supernumerario y superintendente se les piden, en Desembarque, la Carta de
Responsabilidad, las Generales de pasaporte, el Contrato de Trabajo y, como
opcional, la Copia de Boleto Aéreo; en Embarque, lo mismo sin el boleto. El
rango militar y los demás trámites quedan como estaban (Generales y boleto).

  - `documentos_requeridos`: el Contrato de Trabajo (DOC-CONTRATO-TRABAJO).
  - `tramite_documentos.rangos_opcional`: los rangos para los que el documento
    de esa fila es opcional (nulo = obligatorio para todos a los que se pide).
    Va en una columna y no en una segunda fila porque cada documento aparece una
    sola vez por trámite (uq_tramite_documento): el boleto de Desembarque sigue
    siendo obligatorio para el Marino y el militar.
  - `solicitud_casillas.obligatoria`: la foto del checklist recuerda si la
    casilla era opcional; una solicitud enviada se sigue juzgando con su foto.

Revision ID: a8d4f2c6e913
Revises: d5b8e2f1a9c3
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a8d4f2c6e913'
down_revision: Union[str, None] = 'd5b8e2f1a9c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TECNICOS = ['tecnico', 'supernumerario', 'superintendente']
NO_MARINOS = ['militar', 'tecnico', 'supernumerario', 'superintendente']
# Sin descripción: el pedido dice solo «contrato de trabajo» y el catálogo no pone
# condiciones propias (las que hay, «Sellada y firmada» o «En español», son del Form. 3).
CONTRATO = ('DOC-CONTRATO-TRABAJO', 'Contrato de Trabajo')
RANGOS = postgresql.ARRAY(sa.String(length=20))


def _agregar_fila(tramite: str, documento: str) -> None:
    """La fila (trámite, documento) por tripulante, solo para los rangos técnicos, al final del checklist."""
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
        SELECT t.id, d.id, 'marino', 'siempre',
               COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1,
               :rangos
          FROM tipos_tramite t, documentos_requeridos d
         WHERE t.codigo = :tramite AND d.codigo = :documento
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(sa.bindparam('rangos', value=TECNICOS, type_=RANGOS), tramite=tramite, documento=documento))


def _boleto(tramite: str, columna: str, valor: list[str] | None) -> None:
    op.execute(sa.text(f"""
        UPDATE tramite_documentos SET {columna} = :valor
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = :tramite)
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-BOLETO-AEREO')
    """).bindparams(sa.bindparam('valor', value=valor, type_=RANGOS), tramite=tramite))


def upgrade() -> None:
    op.add_column('tramite_documentos', sa.Column('rangos_opcional', RANGOS, nullable=True))
    op.add_column('solicitud_casillas',
                  sa.Column('obligatoria', sa.Boolean(), nullable=False, server_default=sa.true()))

    op.execute(sa.text("""
        INSERT INTO documentos_requeridos (codigo, nombre, requiere_libreta)
        VALUES (:codigo, :nombre, false)
        ON CONFLICT (codigo) DO NOTHING
    """).bindparams(codigo=CONTRATO[0], nombre=CONTRATO[1]))

    # Desembarque: Carta y Contrato para los técnicos; su boleto, opcional.
    _agregar_fila('F3-DESEMBARQUE', 'DOC-FORM7-RESPONSABILIDAD')
    _agregar_fila('F3-DESEMBARQUE', 'DOC-CONTRATO-TRABAJO')
    _boleto('F3-DESEMBARQUE', 'rangos_opcional', TECNICOS)
    # Embarque: lo mismo sin el boleto (queda solo para el militar).
    _agregar_fila('F3-EMBARQUE', 'DOC-FORM7-RESPONSABILIDAD')
    _agregar_fila('F3-EMBARQUE', 'DOC-CONTRATO-TRABAJO')
    _boleto('F3-EMBARQUE', 'rangos', ['militar'])


def downgrade() -> None:
    _boleto('F3-EMBARQUE', 'rangos', NO_MARINOS)
    op.execute("""
        DELETE FROM tramite_documentos
         WHERE tipo_tramite_id IN (SELECT id FROM tipos_tramite WHERE codigo IN ('F3-DESEMBARQUE', 'F3-EMBARQUE'))
           AND documento_id IN (SELECT id FROM documentos_requeridos
                                 WHERE codigo IN ('DOC-FORM7-RESPONSABILIDAD', 'DOC-CONTRATO-TRABAJO'))
    """)
    # El Contrato se borra solo si ninguna solicitud lo usó (la foto y los archivos lo referencian).
    op.execute("""
        DELETE FROM documentos_requeridos d
         WHERE d.codigo = 'DOC-CONTRATO-TRABAJO'
           AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
    """)
    op.drop_column('solicitud_casillas', 'obligatoria')
    op.drop_column('tramite_documentos', 'rangos_opcional')
