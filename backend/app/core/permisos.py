"""Permisos: los códigos, los roles fijos y las consultas. Las dependencias de
FastAPI que los exigen en cada ruta (requerir_*) están en api/v1/dependencias.py.

La fuente de verdad es `rol_personalizado` (rol_id en la tabla users), por
nombre del rol:

  - 'Administrador': acceso total. Todo el flujo de solicitudes (atajo a los
    permisos T-*), catálogos, trámites, estadísticas, bitácora, y también
    usuarios, roles y permisos (decisión del usuario del 2026-10-20).
  - 'SysAdmin': administración técnica (usuarios, roles, permisos y
    bitácora). No tiene el atajo de admin: no ve solicitudes ni expedientes.

Sin rol_personalizado asignado, el usuario no tiene acceso administrativo.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models.user import Usuario
from app.domain.models.rol import Permiso, RolPermiso

# Permisos del flujo de Autorizaciones Marítimas
PERMISO_SOLICITAR = "T-CREAR-BASICA"        # Naviera
# UCVMM: revisa las solicitudes de sus sectores (users ↔ sectores).
# El código es de cuando había un solo sector: no se cambia, lo usa el frontend.
PERMISO_REVISAR   = "T-PROCESAR-PACIFICO"
PERMISO_PUERTO    = "T-FINALIZAR-PUERTO"    # Puesto de control migratorio
# Solo lectura (2026-11-10): las de sus sectores, o las de los dos (Tocumen).
PERMISO_SUPERVISAR_SECTOR = "T-SUPERVISAR-SECTOR"
PERMISO_SUPERVISAR_TODO   = "T-SUPERVISAR-TODO"

ROL_ADMIN    = "Administrador"
ROL_SYSADMIN = "SysAdmin"


def es_admin_efectivo(usuario: Usuario) -> bool:
    """True si el usuario tiene el rol personalizado 'Administrador'."""
    return (
        usuario.rol_personalizado is not None
        and usuario.rol_personalizado.nombre == ROL_ADMIN
    )


def es_sysadmin_efectivo(usuario: Usuario) -> bool:
    """True si el usuario tiene el rol personalizado 'SysAdmin'."""
    return (
        usuario.rol_personalizado is not None
        and usuario.rol_personalizado.nombre == ROL_SYSADMIN
    )


async def usuario_tiene_permiso(
    sesion: AsyncSession,
    user_id: int,
    codigo_permiso: str,
) -> bool:
    """True si el usuario es admin efectivo o su rol tiene el permiso."""
    usuario = (await sesion.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one_or_none()
    if not usuario:
        return False
    if es_admin_efectivo(usuario):
        return True
    if usuario.rol_id is None:
        return False
    existe = await sesion.execute(
        select(Permiso.id)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == usuario.rol_id, Permiso.codigo == codigo_permiso)
        .limit(1)
    )
    return existe.scalar_one_or_none() is not None


async def codigos_permiso(sesion: AsyncSession, usuario: Usuario) -> set[str]:
    """Códigos de permiso del rol del usuario (sin el atajo de admin)."""
    if usuario.rol_id is None:
        return set()
    resultado = await sesion.execute(
        select(Permiso.codigo)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == usuario.rol_id)
    )
    return {fila[0] for fila in resultado.all()}
