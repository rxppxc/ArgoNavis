"""Boleta de recargo por atención fuera del horario laboral y alcance del supervisor general

Revision ID: e5c1a7d3b902
Revises: d9a4b7e2c315
Create Date: 2026-11-16

Pedido del usuario del 2026-11-16:

  - Boleta de recargo (`boletas_recargo`): la generan UCVMM, el supervisor de
    sector y el puesto de control para las solicitudes aprobadas fuera del
    horario, con un número de oficio que escribe el funcionario. El número es
    único entre todas las boletas, también las anuladas, sin distinguir
    mayúsculas. Como en un talonario: una boleta mal hecha se anula (con motivo)
    y se genera otra; hay una sola vigente por solicitud. La agencia no la ve: la
    imprime el SNM y se la entrega. La cuenta de la aplicación no puede borrar
    filas de esta tabla (permisos_bd.TABLAS_SIN_BORRAR).
  - El supervisor general (UCVMM en Tocumen) ve solo el trámite de Técnico,
    Superintendente o Supernumerario, de los dos sectores, y ya no ve
    estadísticas ni la consulta histórica. Qué trámites ve lo marca el catálogo
    (`tipos_tramite.supervision_general`): otro se suma con una migración.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5c1a7d3b902'
down_revision: Union[str, None] = 'd9a4b7e2c315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCIONES = ('BOLETA_GENERADA', 'BOLETA_ANULADA', 'BOLETA_DESCARGADA')
PERMISO = 'T-SUPERVISAR-TODO'
ROL = 'Supervisor general'
TEXTO_PERMISO = ('Consulta, sin decidir nada, las solicitudes del trámite de Técnico, Superintendente o '
                 'Supernumerario de los dos sectores: bandeja, expedientes con sus documentos, autorizaciones '
                 'y boletas de recargo.')
TEXTO_ROL = ('Supervisión general de UCVMM (Tocumen): ve las solicitudes del trámite de Técnico, '
             'Superintendente o Supernumerario de los dos sectores, sin aprobar, devolver ni denegar.')
# Los de c1f7a3e9d2b6.
TEXTO_PERMISO_ANTES = ('Consulta, sin decidir nada, las solicitudes de los dos sectores: bandeja, expedientes '
                       'con sus documentos, autorizaciones y estadísticas.')
TEXTO_ROL_ANTES = ('Supervisión general de UCVMM (Tocumen): ve las solicitudes de los dos sectores, sin aprobar, '
                   'devolver ni denegar.')


def _textos(permiso: str, rol: str) -> None:
    op.execute(sa.text("UPDATE permisos SET descripcion = :d WHERE codigo = :c").bindparams(d=permiso, c=PERMISO))
    op.execute(sa.text("UPDATE roles SET descripcion = :d WHERE nombre = :r").bindparams(d=rol, r=ROL))


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE no puede ir en la transacción que lo usa.
    with op.get_context().autocommit_block():
        for accion in ACCIONES:
            op.execute(f"ALTER TYPE accionauditoria ADD VALUE IF NOT EXISTS '{accion}'")

    op.create_table(
        'boletas_recargo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('solicitud_id', sa.Integer(), sa.ForeignKey('solicitudes.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('numero_oficio', sa.String(length=40), nullable=False),
        sa.Column('monto', sa.Numeric(8, 2), nullable=False),
        sa.Column('generada_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('generada_por_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('anulada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('anulada_por_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('motivo_anulacion', sa.String(length=500), nullable=True),
        sa.CheckConstraint('(anulada_en IS NULL) = (motivo_anulacion IS NULL)', name='ck_boletas_recargo_anulacion'),
        sa.CheckConstraint('monto > 0', name='ck_boletas_recargo_monto'),
    )
    op.create_index('ix_boletas_recargo_solicitud_id', 'boletas_recargo', ['solicitud_id'])
    op.create_index('ux_boletas_recargo_numero', 'boletas_recargo', [sa.text('lower(numero_oficio)')], unique=True)
    op.create_index('ux_boletas_recargo_vigente', 'boletas_recargo', ['solicitud_id'], unique=True,
                    postgresql_where=sa.text('anulada_en IS NULL'))

    op.add_column('tipos_tramite', sa.Column('supervision_general', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.execute("UPDATE tipos_tramite SET supervision_general = true WHERE codigo = 'F3-TECNICO'")
    _textos(TEXTO_PERMISO, TEXTO_ROL)


def downgrade() -> None:
    # Los valores BOLETA_* quedan en el enum (PostgreSQL no quita valores de un enum).
    _textos(TEXTO_PERMISO_ANTES, TEXTO_ROL_ANTES)
    op.drop_column('tipos_tramite', 'supervision_general')
    op.drop_index('ux_boletas_recargo_vigente', table_name='boletas_recargo')
    op.drop_index('ux_boletas_recargo_numero', table_name='boletas_recargo')
    op.drop_index('ix_boletas_recargo_solicitud_id', table_name='boletas_recargo')
    op.drop_table('boletas_recargo')
