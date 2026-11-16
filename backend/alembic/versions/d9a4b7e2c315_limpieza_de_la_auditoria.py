"""Limpieza de la auditoría: filas sin uso de los técnicos, solo_panamenos y la columna formulario

Revision ID: d9a4b7e2c315
Revises: c3e8a1f5d927
Create Date: 2026-11-14

Auditoría del 2026-11-14, con las decisiones del usuario:

  - Las filas de los técnicos en Embarque y Desembarque (Carta de Responsabilidad,
    Contrato de Trabajo y el boleto opcional, de la revisión a8d4f2c6e913) no se
    alcanzan desde el 2026-11-13: esos dos trámites admiten solo Marino, Pasajero
    y Militar. Se borran. Las solicitudes ya enviadas no cambian: se juzgan con su
    foto del checklist (solicitud_casillas), que guarda el documento y no la fila.
    El Contrato de Trabajo se borra del catálogo solo si ninguna solicitud lo usó.
  - La condición `solo_panamenos` sale del código: ninguna fila la usa desde el
    2026-10-14. Si alguna la tuviera, la migración se detiene (mejor que tratarla
    en silencio como «siempre»).
  - `tipos_tramite.formulario` siempre decía «formulario_3» (se guardaba por si
    volvía el Formulario 4): sale, con su índice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd9a4b7e2c315'
down_revision: Union[str, None] = 'c3e8a1f5d927'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TECNICOS = ['tecnico', 'supernumerario', 'superintendente']
DE_LOS_TECNICOS = ('DOC-FORM7-RESPONSABILIDAD', 'DOC-CONTRATO-TRABAJO')
CON_TECNICOS = ('F3-EMBARQUE', 'F3-DESEMBARQUE')
RANGOS = postgresql.ARRAY(sa.String(length=20))


def _boleto_opcional(valor: list[str] | None) -> None:
    op.execute(sa.text("""
        UPDATE tramite_documentos SET rangos_opcional = :valor
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-DESEMBARQUE')
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-BOLETO-AEREO')
    """).bindparams(sa.bindparam('valor', value=valor, type_=RANGOS)))


def upgrade() -> None:
    con_solo_panamenos = op.get_bind().execute(
        sa.text("SELECT count(*) FROM tramite_documentos WHERE condicion = 'solo_panamenos'")
    ).scalar_one()
    if con_solo_panamenos:
        raise RuntimeError(
            f"{con_solo_panamenos} fila(s) de tramite_documentos usan la condición «solo_panamenos», que ya no "
            "existe: cámbialas antes de migrar."
        )

    op.execute(sa.text("""
        DELETE FROM tramite_documentos
         WHERE tipo_tramite_id IN (SELECT id FROM tipos_tramite WHERE codigo IN :tramites)
           AND documento_id IN (SELECT id FROM documentos_requeridos WHERE codigo IN :documentos)
    """).bindparams(sa.bindparam('tramites', value=CON_TECNICOS, expanding=True),
                    sa.bindparam('documentos', value=DE_LOS_TECNICOS, expanding=True)))
    _boleto_opcional(None)
    # El Contrato, solo si ninguna solicitud lo usó (la foto y los archivos lo referencian).
    op.execute("""
        DELETE FROM documentos_requeridos d
         WHERE d.codigo = 'DOC-CONTRATO-TRABAJO'
           AND NOT EXISTS (SELECT 1 FROM tramite_documentos t WHERE t.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
    """)

    op.drop_index('ix_tipos_tramite_formulario', table_name='tipos_tramite')
    op.drop_column('tipos_tramite', 'formulario')


def downgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('formulario', sa.String(length=20), nullable=False,
                                             server_default='formulario_3'))
    op.alter_column('tipos_tramite', 'formulario', server_default=None)
    op.create_index('ix_tipos_tramite_formulario', 'tipos_tramite', ['formulario'], unique=False)

    op.execute("""
        INSERT INTO documentos_requeridos (codigo, nombre, requiere_libreta)
        VALUES ('DOC-CONTRATO-TRABAJO', 'Contrato de Trabajo', false)
        ON CONFLICT (codigo) DO NOTHING
    """)
    for tramite in ('F3-DESEMBARQUE', 'F3-EMBARQUE'):
        for documento in DE_LOS_TECNICOS:
            op.execute(sa.text("""
                INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
                SELECT t.id, d.id, 'marino', 'siempre',
                       COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1,
                       :rangos
                  FROM tipos_tramite t, documentos_requeridos d
                 WHERE t.codigo = :tramite AND d.codigo = :documento
                ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
            """).bindparams(sa.bindparam('rangos', value=TECNICOS, type_=RANGOS), tramite=tramite, documento=documento))
    _boleto_opcional(TECNICOS)
