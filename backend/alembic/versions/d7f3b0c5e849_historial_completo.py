"""El historial completo de una solicitud

Revision ID: d7f3b0c5e849
Revises: c6e2a9f1d438
Create Date: 2026-11-22

Pedido del usuario (2026-11-22): todavía no se sabe cuántos años se conservan las
solicitudes, «pero debe haber un margen e historial completos».

  - `solicitud_documentos`: un documento que la agencia reemplaza o quita al corregir ya no se
    borra, queda retirado (`retirado_en`), con el nombre de su tripulante por si también salió
    de la solicitud. Por eso la llave del tripulante pasa de CASCADE a SET NULL. Cada archivo
    lleva su huella (`sha256`); a los de antes se les calcula una vez (huellas.py).
  - `solicitud_versiones`: la foto de lo que se había enviado, guardada al corregir.
  - `documentos_emitidos`: el PDF de la autorización tal como se emitió, al aprobar y al
    finalizar.

La aplicación solo agrega a las dos tablas nuevas y no borra documentos (permisos_bd.py).

Al bajar, los documentos retirados dejan de existir para el sistema, como antes; sus
archivos quedan en el disco.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'd7f3b0c5e849'
down_revision: Union[str, None] = 'c6e2a9f1d438'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LLAVE_TRIPULANTE = 'solicitud_documentos_tripulante_id_fkey'


def _llave_del_tripulante(al_borrar: str) -> None:
    op.drop_constraint(LLAVE_TRIPULANTE, 'solicitud_documentos', type_='foreignkey')
    op.create_foreign_key(LLAVE_TRIPULANTE, 'solicitud_documentos', 'solicitud_tripulantes',
                          ['tripulante_id'], ['id'], ondelete=al_borrar)


def upgrade() -> None:
    op.add_column('solicitud_documentos', sa.Column('sha256', sa.String(64), nullable=True))
    op.add_column('solicitud_documentos', sa.Column('retirado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('solicitud_documentos', sa.Column('tripulante_nombre', sa.String(301), nullable=True))
    _llave_del_tripulante('SET NULL')

    op.create_table(
        'solicitud_versiones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('solicitud_id', sa.Integer(), sa.ForeignKey('solicitudes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('numero', sa.SmallInteger(), nullable=False),
        sa.Column('enviada_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enviada_por', sa.String(255), nullable=True),
        sa.Column('devuelta_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('devuelta_por', sa.String(255), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('corregida_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('corregida_por', sa.String(255), nullable=True),
        sa.Column('datos', JSONB(), nullable=False),
        sa.UniqueConstraint('solicitud_id', 'numero', name='uq_solicitud_versiones_numero'),
    )
    op.create_table(
        'documentos_emitidos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('solicitud_id', sa.Integer(), sa.ForeignKey('solicitudes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('ruta', sa.String(1000), nullable=False),
        sa.Column('tamano', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('emitido_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('solicitud_id', 'tipo', name='uq_documentos_emitidos_tipo'),
        sa.CheckConstraint("tipo IN ('aprobada', 'finalizada')", name='ck_documentos_emitidos_tipo'),
    )


def downgrade() -> None:
    op.drop_table('documentos_emitidos')
    op.drop_table('solicitud_versiones')
    op.execute("DELETE FROM solicitud_documentos WHERE retirado_en IS NOT NULL")
    _llave_del_tripulante('CASCADE')
    for columna in ('tripulante_nombre', 'retirado_en', 'sha256'):
        op.drop_column('solicitud_documentos', columna)
