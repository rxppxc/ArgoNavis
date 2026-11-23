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


# Los códigos de cada rol, en la sesión (o sea, mientras dura el pedido): {rol_id: códigos}.
_CODIGOS = "argonavis.codigos_permiso"


async def usuario_tiene_permiso(
    sesion: AsyncSession,
    user_id: int,
    codigo_permiso: str,
) -> bool:
    """True si el usuario es admin efectivo o su rol tiene el permiso. El usuario sale de la
    sesión (ya lo cargó obtener_id_usuario_actual) y los permisos, de codigos_permiso: una
    comprobación más no vuelve a la base (2026-11-22)."""
    usuario = await sesion.get(Usuario, user_id)
    if not usuario:
        return False
    if es_admin_efectivo(usuario):
        return True
    return codigo_permiso in await codigos_permiso(sesion, usuario)


async def codigos_permiso(sesion: AsyncSession, usuario: Usuario) -> set[str]:
    """Códigos de permiso del rol del usuario (sin el atajo de admin). Se consultan una vez por
    pedido; quien cambie los permisos de un rol en el mismo pedido llama a olvidar_permisos."""
    if usuario.rol_id is None:
        return set()
    guardados: dict[int, frozenset[str]] = sesion.info.setdefault(_CODIGOS, {})
    if usuario.rol_id not in guardados:
        resultado = await sesion.execute(
            select(Permiso.codigo)
            .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
            .where(RolPermiso.rol_id == usuario.rol_id)
        )
        guardados[usuario.rol_id] = frozenset(fila[0] for fila in resultado.all())
    return set(guardados[usuario.rol_id])


def olvidar_permisos(sesion: AsyncSession) -> None:
    """Después de cambiar los permisos de un rol: la próxima consulta los vuelve a leer."""
    sesion.info.pop(_CODIGOS, None)
