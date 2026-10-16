"""catalogo_segun_formulario_3

El catálogo queda tal cual el Formulario No. 3 oficial (con su instructivo) y
el documento de UCVMM "Documentación requerida para las autorizaciones
marítimas", sin interpretaciones propias:

  - Desembarque vuelve a pedir "Generales de Pasaporte": el recuadro de
    Desembarque del Form. 3 la lista.
  - El Form. No. 6 de custodia se adjunta solo en Desembarque ("cuando
    aplique"): es el único trámite donde lo listan el Form. 3 y los adjuntos
    del proceso.
  - `tipos_tramite.aviso_custodia`: trámites cuyo proceso dice que, al
    aprobar, se le informa a la agencia que debe realizar el trámite de
    solicitud de custodia (Desembarque, Urgencias, Renovación y Shore Pass).
  - La Carta de Responsabilidad y el Reporte Médico se suben por tripulante:
    cada proceso dice "para cada tripulante el agente naviero debe subir…";
    la única excepción escrita es la Lista de Tripulantes, que va al trámite.

Revision ID: b9e4d17a3c52
Revises: f3b8c51a9d27
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9e4d17a3c52'
down_revision: Union[str, None] = 'f3b8c51a9d27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Trámites que dejan de pedir el Form. No. 6, con el orden que tenía la casilla
# (d4f1a8c27e90 y f3b8c51a9d27) para que el downgrade la deje igual.
CUSTODIA_RETIRADA = [
    ('F3-EMBARQUE', 4),
    ('F3-CAMBIO-PUERTO', 3),
    ('F3-CAMBIO-NAVE', 3),
    ('F3-TECNICO', 3),
    ('F3-RENOV-PASAPORTE', 6),
    ('F3-SHORE-PASS', 4),
    ('F3-URGENCIA-MEDICA', 5),
]
# Procesos que, al aprobar, informan a la agencia que debe tramitar la custodia.
AVISO_CUSTODIA = ['F3-DESEMBARQUE', 'F3-URGENCIA-MEDICA', 'F3-RENOV-PASAPORTE', 'F3-SHORE-PASS']
# Documentos que pasan de uno por solicitud a uno por tripulante.
POR_TRIPULANTE = [
    ('F3-URGENCIA-MEDICA', 'DOC-FORM7-RESPONSABILIDAD'),
    ('F3-URGENCIA-MEDICA', 'DOC-REPORTE-MEDICO'),
    ('F3-RENOV-PASAPORTE', 'DOC-FORM7-RESPONSABILIDAD'),
    ('F3-TECNICO', 'DOC-FORM7-RESPONSABILIDAD'),
]

DESCRIPCION_CUSTODIA_NUEVA = 'En Desembarque, a cada tripulante de nacionalidad restringida (cuando aplique).'
DESCRIPCION_CUSTODIA_ANTERIOR = 'Se exige a cada tripulante de nacionalidad restringida, en cualquier trámite.'


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


def _cambiar_alcance(tramite: str, documento: str, alcance: str):
    return sa.text("""
        UPDATE tramite_documentos SET alcance = :a
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = :t)
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = :d)
    """).bindparams(t=tramite, d=documento, a=alcance)


def _descripcion_custodia(descripcion: str):
    return sa.text(
        "UPDATE documentos_requeridos SET descripcion = :d WHERE codigo = 'DOC-FORM6-CUSTODIA'"
    ).bindparams(d=descripcion)


def upgrade() -> None:
    op.execute(_fila_tramite_documento('F3-DESEMBARQUE', 'DOC-GENERALES-PASAPORTE', 'marino', 'siempre', 2))

    for tramite, _ in CUSTODIA_RETIRADA:
        op.execute(_borrar_tramite_documento(tramite, 'DOC-FORM6-CUSTODIA'))
    op.execute(_descripcion_custodia(DESCRIPCION_CUSTODIA_NUEVA))

    for tramite, documento in POR_TRIPULANTE:
        op.execute(_cambiar_alcance(tramite, documento, 'marino'))

    op.add_column('tipos_tramite', sa.Column('aviso_custodia', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        sa.text("UPDATE tipos_tramite SET aviso_custodia = true WHERE codigo IN :c")
        .bindparams(sa.bindparam('c', value=AVISO_CUSTODIA, expanding=True))
    )


def downgrade() -> None:
    op.drop_column('tipos_tramite', 'aviso_custodia')

    for tramite, documento in POR_TRIPULANTE:
        op.execute(_cambiar_alcance(tramite, documento, 'solicitud'))

    op.execute(_descripcion_custodia(DESCRIPCION_CUSTODIA_ANTERIOR))
    for tramite, orden in CUSTODIA_RETIRADA:
        op.execute(_fila_tramite_documento(tramite, 'DOC-FORM6-CUSTODIA', 'marino', 'nacionalidad_restringida', orden))

    op.execute(_borrar_tramite_documento('F3-DESEMBARQUE', 'DOC-GENERALES-PASAPORTE'))
