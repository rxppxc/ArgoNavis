"""validaciones_sysadmin_finalizacion

Ajustes pedidos por el usuario sobre la lectura literal de los documentos:

  - Ningún documento vencido: `valida_vigencia` pasa a true en los 8 trámites
    (antes solo Embarque, Visita médica y Shore Pass, por la Nota de la pág. 9).
  - Libreta de Marino en Embarque para todo tripulante de rango Marino, sin
    importar la nacionalidad (antes solo panameños).
  - `solicitud_tripulantes.con_impedimento`: verificación de impedimentos por
    persona (NULL = sin verificar).
  - `solicitudes.puesto_finalizacion_id/_nombre`: puesto donde terminó la
    operación (puede ser otro que el autorizado). Las ya finalizadas toman el
    puesto autorizado.
  - Rol `SysAdmin`: administración técnica (usuarios, roles y bitácora), sin
    acceso a solicitudes; separado del Administrador.

Revision ID: c7a2e94b1f30
Revises: b9e4d17a3c52
Create Date: 2026-10-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a2e94b1f30'
down_revision: Union[str, None] = 'b9e4d17a3c52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Trámites que no validaban la vigencia (para el downgrade).
SIN_VIGENCIA_ANTES = ['F3-DESEMBARQUE', 'F3-CAMBIO-PUERTO', 'F3-CAMBIO-NAVE', 'F3-RENOV-PASAPORTE', 'F3-TECNICO']

DESCRIPCION_SYSADMIN = (
    'Administración técnica del sistema: usuarios, roles, permisos y bitácora. '
    'No ve solicitudes ni expedientes.'
)


def _condicion_libreta_embarque(condicion: str):
    return sa.text("""
        UPDATE tramite_documentos SET condicion = :c
         WHERE tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-EMBARQUE')
           AND documento_id   = (SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-LIBRETA-MARINO')
    """).bindparams(c=condicion)


def upgrade() -> None:
    op.execute("UPDATE tipos_tramite SET valida_vigencia = true")
    op.execute(_condicion_libreta_embarque('siempre'))

    op.add_column('solicitud_tripulantes', sa.Column('con_impedimento', sa.Boolean(), nullable=True))

    op.add_column('solicitudes', sa.Column('puesto_finalizacion_id', sa.Integer(), nullable=True))
    op.add_column('solicitudes', sa.Column('puesto_finalizacion_nombre', sa.String(length=200), nullable=True))
    op.create_foreign_key(
        'fk_solicitudes_puesto_finalizacion', 'solicitudes', 'puestos_control',
        ['puesto_finalizacion_id'], ['id'], ondelete='RESTRICT',
    )
    op.execute("""
        UPDATE solicitudes
           SET puesto_finalizacion_id = puesto_control_id, puesto_finalizacion_nombre = puesto_nombre
         WHERE estado = 'finalized'
    """)

    op.execute(
        sa.text("""
            INSERT INTO roles (nombre, descripcion, es_sistema) VALUES ('SysAdmin', :d, TRUE)
            ON CONFLICT (nombre) DO NOTHING
        """).bindparams(d=DESCRIPCION_SYSADMIN)
    )


def downgrade() -> None:
    # Los SysAdmin vuelven a ser Administrador antes de borrar el rol.
    op.execute("""
        UPDATE users SET rol_id = (SELECT id FROM roles WHERE nombre = 'Administrador')
         WHERE rol_id = (SELECT id FROM roles WHERE nombre = 'SysAdmin')
    """)
    op.execute("DELETE FROM roles_permisos WHERE rol_id = (SELECT id FROM roles WHERE nombre = 'SysAdmin')")
    op.execute("DELETE FROM roles WHERE nombre = 'SysAdmin'")

    op.drop_constraint('fk_solicitudes_puesto_finalizacion', 'solicitudes', type_='foreignkey')
    op.drop_column('solicitudes', 'puesto_finalizacion_nombre')
    op.drop_column('solicitudes', 'puesto_finalizacion_id')

    op.drop_column('solicitud_tripulantes', 'con_impedimento')

    op.execute(_condicion_libreta_embarque('solo_panamenos'))
    op.execute(
        sa.text("UPDATE tipos_tramite SET valida_vigencia = false WHERE codigo IN :c")
        .bindparams(sa.bindparam('c', value=SIN_VIGENCIA_ANTES, expanding=True))
    )
