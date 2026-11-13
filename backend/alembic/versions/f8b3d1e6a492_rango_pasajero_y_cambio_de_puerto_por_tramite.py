"""Rango Pasajero, y el cambio de puerto solo en Embarque y Desembarque

Revision ID: f8b3d1e6a492
Revises: e5c2a8f1d376
Create Date: 2026-11-13

Pedido del usuario (2026-11-13, segundo lote):

  - Rango nuevo, «Pasajero» (`pasajero`): un Marino sin libreta. En cada trámite
    se le piden los documentos del Marino (las filas de `tramite_documentos` cuyo
    `rangos` incluye `marino`) salvo la Libreta, que es solo de quien porta
    seamanbook (`requiere_libreta`). Se puede elegir en todos los trámites salvo
    el de Técnico, que solo admite sus tres rangos.
  - Embarque y Desembarque admiten solo Marino, Pasajero y Militar
    (`rangos_permitidos`). Los técnicos, supernumerarios y superintendentes van
    por el trámite de Técnico. Las filas de sus documentos en esos dos trámites
    (Carta, Contrato y boleto opcional, del 2026-11-11) quedan sin uso: no se
    borran, por las solicitudes que ya las tienen en su foto del checklist.
  - `tipos_tramite.permite_cambio_puerto`: el cambio de puerto (revisión
    e5c2a8f1d376) queda solo en Embarque y Desembarque.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f8b3d1e6a492'
down_revision: Union[str, None] = 'e5c2a8f1d376'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CON_CAMBIO = ('F3-EMBARQUE', 'F3-DESEMBARQUE')
RANGOS_ANTES = ['marino', 'militar', 'tecnico', 'supernumerario', 'superintendente']
RANGOS_AHORA = ['marino', 'pasajero', 'militar', 'tecnico', 'supernumerario', 'superintendente']
RANGOS = postgresql.ARRAY(sa.String(length=20))


def _check_de_rangos(rangos: list[str]) -> None:
    op.drop_constraint('ck_solicitud_tripulantes_rango', 'solicitud_tripulantes', type_='check')
    op.create_check_constraint(
        'ck_solicitud_tripulantes_rango', 'solicitud_tripulantes',
        "rango IN (" + ", ".join(f"'{r}'" for r in rangos) + ")",
    )


def upgrade() -> None:
    _check_de_rangos(RANGOS_AHORA)

    # Al Pasajero, lo del Marino.
    op.execute("""
        UPDATE tramite_documentos SET rangos = array_append(rangos, 'pasajero')
         WHERE 'marino' = ANY(rangos) AND NOT 'pasajero' = ANY(rangos)
    """)
    op.execute(sa.text("""
        UPDATE tipos_tramite SET rangos_permitidos = :rangos WHERE codigo IN :codigos
    """).bindparams(sa.bindparam('rangos', value=['marino', 'pasajero', 'militar'], type_=RANGOS),
                    sa.bindparam('codigos', value=CON_CAMBIO, expanding=True)))

    op.add_column('tipos_tramite', sa.Column('permite_cambio_puerto', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.execute(sa.text("UPDATE tipos_tramite SET permite_cambio_puerto = true WHERE codigo IN :codigos")
               .bindparams(sa.bindparam('codigos', value=CON_CAMBIO, expanding=True)))


def downgrade() -> None:
    op.drop_column('tipos_tramite', 'permite_cambio_puerto')
    op.execute(sa.text("UPDATE tipos_tramite SET rangos_permitidos = NULL WHERE codigo IN :codigos")
               .bindparams(sa.bindparam('codigos', value=CON_CAMBIO, expanding=True)))
    op.execute("UPDATE tramite_documentos SET rangos = array_remove(rangos, 'pasajero') WHERE 'pasajero' = ANY(rangos)")
    # Sin el rango, un Pasajero ya registrado vuelve como Marino (el más parecido): sin esto,
    # la restricción de abajo no se podría crear.
    op.execute("UPDATE solicitud_tripulantes SET rango = 'marino' WHERE rango = 'pasajero'")
    _check_de_rangos(RANGOS_ANTES)
