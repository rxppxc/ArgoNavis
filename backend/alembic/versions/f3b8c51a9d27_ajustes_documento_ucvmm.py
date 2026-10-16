"""ajustes_documento_ucvmm

Ajustes del catálogo tras validar otra vez el documento de UCVMM
("Documentación requerida para las autorizaciones marítimas"):

  - Custodia (Form. No. 6) en TODOS los trámites para los tripulantes de
    nacionalidad restringida (Nota 2 de los requisitos del sistema). Antes
    solo estaba en Desembarque, Urgencias, Renovación y Shore Pass.
  - Desembarque deja de pedir "Generales de Pasaporte": el documento no lo
    incluye en su lista de adjuntos.
  - `tipos_tramite.rangos_permitidos`: rangos admitidos en el trámite (nulo =
    cualquiera). La Autorización de Técnico, Superintendente o Supernumerario
    solo admite esos tres.

Revision ID: f3b8c51a9d27
Revises: d4f1a8c27e90
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f3b8c51a9d27'
down_revision: Union[str, None] = 'd4f1a8c27e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Trámites que ganan la custodia, con el orden de la casilla en su checklist.
CUSTODIA_NUEVA = [
    ('F3-EMBARQUE', 4),
    ('F3-CAMBIO-PUERTO', 3),
    ('F3-CAMBIO-NAVE', 3),
    ('F3-TECNICO', 3),
]
RANGOS_TECNICO = ['tecnico', 'superintendente', 'supernumerario']

DESCRIPCION_CUSTODIA_NUEVA = 'Se exige a cada tripulante de nacionalidad restringida, en cualquier trámite.'
DESCRIPCION_CUSTODIA_ANTERIOR = 'Se exige a cada tripulante de nacionalidad restringida.'


def _fila_tramite_documento(tramite: str, documento: str, alcance: str, condicion: str, orden: int):
    return sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
        SELECT t.id, d.id, :a, :c, :o
          FROM tipos_tramite t, documentos_requeridos d
         WHERE t.codigo = :t AND d.codigo = :d
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(t=tramite, d=documento, a=alcance, c=condicion, o=orden)


def _borrar_tramite_documento(tramite: str, documento: str):
    return sa.text("""
        DELETE FROM tramite_documentos
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = :t)
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = :d)
    """).bindparams(t=tramite, d=documento)


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('rangos_permitidos', postgresql.ARRAY(sa.String(length=20)), nullable=True))
    op.execute(
        sa.text("UPDATE tipos_tramite SET rangos_permitidos = :r WHERE codigo = 'F3-TECNICO'")
        .bindparams(sa.bindparam('r', value=RANGOS_TECNICO, type_=postgresql.ARRAY(sa.String(length=20))))
    )

    for tramite, orden in CUSTODIA_NUEVA:
        op.execute(_fila_tramite_documento(tramite, 'DOC-FORM6-CUSTODIA', 'marino', 'nacionalidad_restringida', orden))
    op.execute(
        sa.text("UPDATE documentos_requeridos SET descripcion = :d WHERE codigo = 'DOC-FORM6-CUSTODIA'")
        .bindparams(d=DESCRIPCION_CUSTODIA_NUEVA)
    )

    op.execute(_borrar_tramite_documento('F3-DESEMBARQUE', 'DOC-GENERALES-PASAPORTE'))


def downgrade() -> None:
    op.execute(_fila_tramite_documento('F3-DESEMBARQUE', 'DOC-GENERALES-PASAPORTE', 'marino', 'siempre', 2))

    op.execute(
        sa.text("UPDATE documentos_requeridos SET descripcion = :d WHERE codigo = 'DOC-FORM6-CUSTODIA'")
        .bindparams(d=DESCRIPCION_CUSTODIA_ANTERIOR)
    )
    for tramite, _ in CUSTODIA_NUEVA:
        op.execute(_borrar_tramite_documento(tramite, 'DOC-FORM6-CUSTODIA'))

    op.drop_column('tipos_tramite', 'rangos_permitidos')
