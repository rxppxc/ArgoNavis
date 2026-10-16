"""Dependencia FastAPI para validar permisos del usuario actual.

La fuente de verdad es `rol_personalizado` (rol_id en la tabla users), por
nombre del rol:

  - 'Administrador': administración funcional (catálogos, trámites,
    estadísticas, bitácora) y todo el flujo de solicitudes.
  - 'SysAdmin': administración técnica (usuarios, roles, permisos y
    bitácora). No tiene el atajo de admin: no ve solicitudes ni expedientes.

Sin rol_personalizado asignado, el usuario no tiene acceso administrativo.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database import obtener_sesion_bd
from app.core.security import obtener_id_usuario_actual
from app.domain.models.user import Usuario
from app.domain.models.rol import Permiso, RolPermiso

# Permisos del flujo de Autorizaciones Marítimas
PERMISO_SOLICITAR = "T-CREAR-BASICA"        # Naviera
PERMISO_REVISAR   = "T-PROCESAR-PACIFICO"   # UCVMM (Sector Pacífico)
PERMISO_PUERTO    = "T-FINALIZAR-PUERTO"    # Puesto de control migratorio

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


async def requerir_admin(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Dependencia: solo administradores."""
    usuario = (await sesion.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one_or_none()
    if not usuario or not es_admin_efectivo(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador para acceder a esta función.",
        )
    return user_id


async def requerir_sysadmin(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Dependencia: solo SysAdmin (usuarios, roles y permisos)."""
    usuario = (await sesion.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one_or_none()
    if not usuario or not es_sysadmin_efectivo(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere el rol SysAdmin para administrar usuarios, roles y permisos.",
        )
    return user_id


async def requerir_admin_o_sysadmin(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Dependencia: Administrador o SysAdmin (bitácora y consultas de usuarios/roles)."""
    usuario = (await sesion.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one_or_none()
    if not usuario or not (es_admin_efectivo(usuario) or es_sysadmin_efectivo(usuario)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador para acceder a esta función.",
        )
    return user_id


def requerir_permiso(codigo_permiso: str):
    """Genera una dependencia FastAPI que valida que el usuario tenga el permiso."""
    async def _dep(
        user_id: int = Depends(obtener_id_usuario_actual),
        sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
    ) -> int:
        if not await usuario_tiene_permiso(sesion, user_id, codigo_permiso):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes el permiso requerido: {codigo_permiso}.",
            )
        return user_id
    return _dep


def requerir_algun_permiso(*codigos: str):
    """Dependencia que requiere al menos uno de los permisos listados."""
    async def _dep(
        user_id: int = Depends(obtener_id_usuario_actual),
        sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
    ) -> int:
        for codigo in codigos:
            if await usuario_tiene_permiso(sesion, user_id, codigo):
                return user_id
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes ninguno de los permisos requeridos: {', '.join(codigos)}.",
        )
    return _dep
