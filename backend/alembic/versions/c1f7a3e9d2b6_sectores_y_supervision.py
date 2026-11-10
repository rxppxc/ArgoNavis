"""sectores_y_supervision

Sectores de UCVMM (pedido del usuario del 2026-11-10): Sector Pacífico y Sector
Atlántico. Cada puesto de control pertenece a un sector. Los revisores de UCVMM
y los supervisores de sector quedan asignados a uno o más sectores, y solo ven
(y los revisores, revisan) las solicitudes de los puestos de sus sectores.

  - `sectores`, con el buzón que recibe el aviso de cada solicitud nueva de su
    sector (sin buzón, va al general, CORREO_UCVMM). Se siembran los dos.
  - `puestos_control.sector_id`, obligatorio. Los puestos que ya existen quedan
    en el Sector Pacífico, que es como funciona hoy; el administrador pasa a
    Atlántico los suyos.
  - `usuarios_sectores`. Quien hoy tiene el rol de revisión queda en el Sector
    Pacífico, para que nada cambie al desplegar.
  - El rol «Sector Pacífico» pasa a llamarse «UCVMM»: el sector ya no va en el
    rol, sino en la asignación. El permiso conserva su código
    (T-PROCESAR-PACIFICO): lo usan el backend y el frontend.
  - Dos permisos y dos roles de solo lectura: «Supervisor de sector»
    (T-SUPERVISAR-SECTOR, las de sus sectores) y «Supervisor general»
    (T-SUPERVISAR-TODO, las de los dos; UCVMM en Tocumen).
  - Bitácora: SECTOR_ACTUALIZADO (buzón o funcionarios de un sector).

Revision ID: c1f7a3e9d2b6
Revises: e7b2d5a9c4f1
Create Date: 2026-11-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c1f7a3e9d2b6'
down_revision: Union[str, None] = 'e7b2d5a9c4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PACIFICO = 'Sector Pacífico'
ATLANTICO = 'Sector Atlántico'

ROL_REVISION_ANTES = 'Sector Pacífico'
ROL_REVISION = 'UCVMM'
DESCRIPCION_ROL_ANTES = ('Sección de autorizaciones marítimas (UCVMM): revisa, aprueba, niega o devuelve las '
                         'solicitudes de las navieras.')
DESCRIPCION_ROL = ('Sección de autorizaciones marítimas (UCVMM): revisa, aprueba, deniega o devuelve las solicitudes '
                   'de los puestos de su sector (Pacífico o Atlántico, según su asignación).')

PERMISO_REVISION = 'T-PROCESAR-PACIFICO'
PERMISO_REVISION_ANTES = ('Revisar autorizaciones',
                          'Revisa las solicitudes de autorización marítima: verifica impedimentos, aprueba, niega '
                          'o devuelve a corrección.')
PERMISO_REVISION_AHORA = ('Revisar autorizaciones de su sector',
                          'Revisa las solicitudes de los puestos de su sector: verifica impedimentos, aprueba, deniega '
                          'o devuelve a corrección.')

SUPERVISION = [
    # (permiso, nombre, descripción del permiso, rol, descripción del rol)
    ('T-SUPERVISAR-SECTOR', 'Supervisar su sector',
     'Consulta, sin decidir nada, las solicitudes de los puestos de su sector: bandeja, expedientes con sus '
     'documentos, autorizaciones y estadísticas.',
     'Supervisor de sector',
     'Supervisor de UCVMM: ve las solicitudes de su sector (Pacífico o Atlántico, según su asignación), sin '
     'aprobar, devolver ni denegar.'),
    ('T-SUPERVISAR-TODO', 'Supervisión general',
     'Consulta, sin decidir nada, las solicitudes de los dos sectores: bandeja, expedientes con sus documentos, '
     'autorizaciones y estadísticas.',
     'Supervisor general',
     'Supervisión general de UCVMM (Tocumen): ve las solicitudes de los dos sectores, sin aprobar, devolver ni '
     'denegar.'),
]


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE no puede ir en la transacción que lo usa.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE accionauditoria ADD VALUE IF NOT EXISTS 'SECTOR_ACTUALIZADO'")

    op.create_table(
        'sectores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(100), nullable=False, unique=True),
        sa.Column('correo', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(sa.text("INSERT INTO sectores (nombre) VALUES (:p), (:a)").bindparams(p=PACIFICO, a=ATLANTICO))

    op.add_column('puestos_control', sa.Column(
        'sector_id', sa.Integer(), sa.ForeignKey('sectores.id', ondelete='RESTRICT'), nullable=True,
    ))
    op.execute(sa.text(
        "UPDATE puestos_control SET sector_id = (SELECT id FROM sectores WHERE nombre = :p)"
    ).bindparams(p=PACIFICO))
    op.alter_column('puestos_control', 'sector_id', nullable=False)
    op.create_index('ix_puestos_control_sector_id', 'puestos_control', ['sector_id'], unique=False)

    op.create_table(
        'usuarios_sectores',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('sector_id', sa.Integer(), sa.ForeignKey('sectores.id', ondelete='CASCADE'), primary_key=True),
    )
    # Quien hoy revisa sigue revisando lo mismo: todo es del Sector Pacífico. El
    # Administrador no necesita sector (ve todo).
    op.execute(sa.text("""
        INSERT INTO usuarios_sectores (usuario_id, sector_id)
        SELECT u.id, (SELECT id FROM sectores WHERE nombre = :p)
          FROM users u
          JOIN roles r ON r.id = u.rol_id
          JOIN roles_permisos rp ON rp.rol_id = r.id
          JOIN permisos p ON p.id = rp.permiso_id
         WHERE p.codigo = :permiso AND r.nombre <> 'Administrador'
    """).bindparams(p=PACIFICO, permiso=PERMISO_REVISION))

    op.execute(sa.text("""
        UPDATE roles SET nombre = :nuevo, descripcion = :descripcion
         WHERE nombre = :antes AND NOT EXISTS (SELECT 1 FROM roles WHERE nombre = :nuevo)
    """).bindparams(nuevo=ROL_REVISION, descripcion=DESCRIPCION_ROL, antes=ROL_REVISION_ANTES))
    op.execute(sa.text("UPDATE permisos SET nombre = :n, descripcion = :d WHERE codigo = :c").bindparams(
        n=PERMISO_REVISION_AHORA[0], d=PERMISO_REVISION_AHORA[1], c=PERMISO_REVISION))

    for codigo, nombre, descripcion, rol, descripcion_rol in SUPERVISION:
        op.execute(sa.text("""
            INSERT INTO permisos (codigo, nombre, descripcion) VALUES (:c, :n, :d)
            ON CONFLICT (codigo) DO NOTHING
        """).bindparams(c=codigo, n=nombre, d=descripcion))
        op.execute(sa.text("""
            INSERT INTO roles (nombre, descripcion, es_sistema) VALUES (:r, :d, FALSE)
            ON CONFLICT (nombre) DO NOTHING
        """).bindparams(r=rol, d=descripcion_rol))
        op.execute(sa.text("""
            INSERT INTO roles_permisos (rol_id, permiso_id)
            SELECT r.id, p.id FROM roles r JOIN permisos p ON p.codigo = :c
             WHERE r.nombre IN (:r, 'Administrador')
            ON CONFLICT ON CONSTRAINT uq_roles_permisos_rol_permiso DO NOTHING
        """).bindparams(c=codigo, r=rol))


def downgrade() -> None:
    # El valor SECTOR_ACTUALIZADO queda en el enum (PostgreSQL no quita valores de un enum).
    for codigo, _nombre, _descripcion, rol, _descripcion_rol in SUPERVISION:
        op.execute(sa.text(
            "DELETE FROM roles_permisos WHERE permiso_id IN (SELECT id FROM permisos WHERE codigo = :c)"
        ).bindparams(c=codigo))
        # Sus usuarios quedan sin rol (users.rol_id es ON DELETE SET NULL).
        op.execute(sa.text("DELETE FROM roles WHERE nombre = :r").bindparams(r=rol))
        op.execute(sa.text("DELETE FROM permisos WHERE codigo = :c").bindparams(c=codigo))

    op.execute(sa.text("UPDATE permisos SET nombre = :n, descripcion = :d WHERE codigo = :c").bindparams(
        n=PERMISO_REVISION_ANTES[0], d=PERMISO_REVISION_ANTES[1], c=PERMISO_REVISION))
    op.execute(sa.text("""
        UPDATE roles SET nombre = :antes, descripcion = :descripcion
         WHERE nombre = :nuevo AND NOT EXISTS (SELECT 1 FROM roles WHERE nombre = :antes)
    """).bindparams(antes=ROL_REVISION_ANTES, descripcion=DESCRIPCION_ROL_ANTES, nuevo=ROL_REVISION))

    op.drop_table('usuarios_sectores')
    op.drop_index('ix_puestos_control_sector_id', table_name='puestos_control')
    op.drop_column('puestos_control', 'sector_id')
    op.drop_table('sectores')
