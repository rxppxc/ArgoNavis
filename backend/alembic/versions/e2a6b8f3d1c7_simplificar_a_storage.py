"""simplificar_a_storage

Simplificación grande del flujo: el sistema deja de ser un circuito de
aprobación Naviera → Sector Pacífico → Muelle y pasa a ser un storage
simple. Decisión explícita del dueño del sistema (ver CLAUDE.md):

  - Naviera sube archivos y quedan visibles de inmediato (ya no hay
    borrador/revisión).
  - Sector Pacífico ve todo lo que suben las navieras, previsualiza,
    descarga y copia el enlace — ya no procesa/edita/devuelve nada.
  - Se retira por completo el rol Muelle/Operador: cola, asignación de
    puertos, marcar procesada, devolver.
  - Se retira el catálogo de Puertos y Navieras (admin) y los campos
    puerto/marino/naviera de cada transferencia.

Dato existente: por instrucción explícita del dueño del sistema se
eliminan TODAS las transferencias actuales (archivos y BD) para probar
el nuevo flujo desde cero — no hay migración de datos históricos.

Revision ID: e2a6b8f3d1c7
Revises: c4d7f8a1b3e6
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a6b8f3d1c7'
down_revision: Union[str, None] = 'c4d7f8a1b3e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Borrón y cuenta nueva: se piden probar el flujo simplificado de 0 ──
    op.execute(sa.text("DELETE FROM transfers"))

    # ── Retirar Muelle/Operador y asignación de puertos ──
    op.execute(sa.text("DROP TABLE IF EXISTS usuarios_puertos"))
    op.execute(sa.text("""
        DELETE FROM roles_permisos
         WHERE rol_id IN (SELECT id FROM roles WHERE nombre = 'Muelle/Operador')
            OR permiso_id IN (SELECT id FROM permisos WHERE codigo IN ('T-PROCESAR-MUELLE', 'T-CREAR-COMPLETA'))
    """))
    op.execute(sa.text("DELETE FROM roles WHERE nombre = 'Muelle/Operador'"))
    op.execute(sa.text("DELETE FROM permisos WHERE codigo IN ('T-PROCESAR-MUELLE', 'T-CREAR-COMPLETA')"))

    # ── Columnas de transfers que solo tenían sentido en el flujo viejo ──
    op.drop_index(op.f('ix_transfers_puerto_id'), table_name='transfers')
    op.drop_constraint('transfers_puerto_id_fkey', 'transfers', type_='foreignkey')
    op.drop_column('transfers', 'puerto_id')
    op.drop_column('transfers', 'marino')
    op.drop_column('transfers', 'naviera')
    op.drop_column('transfers', 'titulo_original')
    op.drop_column('transfers', 'mensaje_original')
    op.drop_column('transfers', 'destinatario_original')
    op.drop_column('transfers', 'observaciones')

    # ── Catálogos Puerto / Naviera (ya no se usan en ningún formulario) ──
    op.execute(sa.text("DROP TABLE IF EXISTS navieras"))
    op.execute(sa.text("DROP TABLE IF EXISTS puertos"))

    # ── Descripciones actualizadas de los permisos/roles que sobreviven ──
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Subir archivos',
            descripcion = 'Sube archivos con título/mensaje/destinatario opcional. Queda disponible de inmediato.'
        WHERE codigo = 'T-CREAR-BASICA'
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Ver todo y descargar',
            descripcion = 'Ve todas las transferencias subidas por las navieras, las previsualiza, descarga y copia el enlace.'
        WHERE codigo = 'T-PROCESAR-PACIFICO'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Sube archivos para el Servicio Nacional de Migración. Quedan disponibles de inmediato con un enlace de descarga.'
         WHERE nombre = 'Naviera'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Ve, previsualiza y descarga todos los archivos subidos por las navieras.'
         WHERE nombre = 'Sector Pacífico'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Sube archivos en estado borrador con título/mensaje/destinatario para que el Sector Pacífico complete los datos.'
         WHERE nombre = 'Naviera'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Procesa los borradores enviados por las navieras: asigna puerto/naviera/marino, edita archivos y reenvía con notificación al destinatario.'
         WHERE nombre = 'Sector Pacífico'
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Crear borrador',
            descripcion = 'Sube archivos con título/mensaje/destinatario. No completa puerto/naviera/marino. Queda en borrador.'
        WHERE codigo = 'T-CREAR-BASICA'
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Procesar cola',
            descripcion = 'Ve cola de borradores, asigna puerto/naviera/marino, edita y reenvía.'
        WHERE codigo = 'T-PROCESAR-PACIFICO'
    """))

    op.create_table(
        'puertos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=255), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_puertos_id'), 'puertos', ['id'], unique=False)

    op.create_table(
        'navieras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=255), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_navieras_id'), 'navieras', ['id'], unique=False)

    op.add_column('transfers', sa.Column('observaciones', sa.Text(), nullable=True))
    op.add_column('transfers', sa.Column('destinatario_original', sa.String(length=255), nullable=True))
    op.add_column('transfers', sa.Column('mensaje_original', sa.Text(), nullable=True))
    op.add_column('transfers', sa.Column('titulo_original', sa.String(length=255), nullable=True))
    op.add_column('transfers', sa.Column('naviera', sa.String(length=255), nullable=True))
    op.add_column('transfers', sa.Column('marino', sa.String(length=255), nullable=True))
    op.add_column('transfers', sa.Column('puerto_id', sa.Integer(), nullable=True))
    op.create_foreign_key('transfers_puerto_id_fkey', 'transfers', 'puertos', ['puerto_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_transfers_puerto_id'), 'transfers', ['puerto_id'], unique=False)

    op.create_table(
        'usuarios_puertos',
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('puerto_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['puerto_id'], ['puertos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('usuario_id', 'puerto_id'),
    )

    # Nota: el rol Muelle/Operador y el permiso T-PROCESAR-MUELLE no se
    # recrean automáticamente — igual que en el flujo original, se crean a
    # mano desde /admin/roles si se decide revivir ese flujo. T-CREAR-COMPLETA
    # tampoco se recrea: quedó obsoleto al unificar la creación de transferencias.
