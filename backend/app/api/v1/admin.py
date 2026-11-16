"""Administración: usuarios, roles y permisos, y el uso del sistema. Las reglas viven
en los servicios (domain/services/usuario_service.py y rol_service.py, desde el
2026-11-14): aquí se orquesta y se deja la bitácora."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import auditar_admin, requerir_admin_o_sysadmin, requerir_algun_permiso
from app.core.permisos import PERMISO_SUPERVISAR_TODO
from app.domain.models.audit_log import AccionAuditoria
from app.domain.schemas.rol import (
    DatosActualizarRol, DatosAsignarPermisos, DatosAsignarRol, DatosCrearRol, SalidaPermiso, SalidaRol,
)
from app.domain.schemas.solicitud import SalidaUsoSistema
from app.domain.schemas.user import (
    DatosCambiarEstado, DatosCrearUsuario, DatosCrearUsuarioLocal, RespuestaContrasenaTemporal, SalidaUsuario,
)
from app.domain.services.rol_service import ServicioRoles
from app.domain.services.uso_service import ServicioUsoSistema
from app.domain.services.usuario_service import ServicioUsuarios
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(prefix="/admin", tags=["admin"])


# ── Usuarios ──────────────────────────────────────────────────────────────────

@enrutador.get("/usuarios/buscar-ad")
async def buscar_en_ad(
    q: str = Query(..., min_length=2, max_length=100, description="Nombre, usuario o email a buscar"),
    _: int = Depends(requerir_admin_o_sysadmin),
):
    return await ServicioUsuarios.buscar_en_ad(q)


@enrutador.get("/usuarios", response_model=list[SalidaUsuario])
async def listar_usuarios(
    _: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    return await ServicioUsuarios(sesion).listar()


@enrutador.post("/usuarios", response_model=SalidaUsuario, status_code=201)
async def crear_usuario(
    datos: DatosCrearUsuario,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Un funcionario del Active Directory."""
    usuario = await ServicioUsuarios(sesion).crear_desde_ad(datos.username)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_CREADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "origen": "ad"})
    return usuario


@enrutador.post("/usuarios/local", response_model=SalidaUsuario, status_code=201)
async def crear_usuario_local(
    datos: DatosCrearUsuarioLocal,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Una cuenta local (sin AD), para usuarios externos como los de las agencias."""
    svc = ServicioUsuarios(sesion)
    usuario = await svc.crear_local(datos)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_CREADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "origen": "local",
                         "rol_id": usuario.rol_id})
    return await svc.salida(usuario)


@enrutador.post("/usuarios/{user_id}/restablecer-contrasena", response_model=RespuestaContrasenaTemporal)
async def restablecer_contrasena(
    user_id: int,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Genera una contraseña temporal para una cuenta local (y la desbloquea).
    Se muestra una sola vez; el usuario debe cambiarla al entrar."""
    usuario, temporal = await ServicioUsuarios(sesion).restablecer_contrasena(user_id)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.CONTRASENA_RESTABLECIDA,
                        {"usuario_id": usuario.id, "usuario": usuario.username})
    return RespuestaContrasenaTemporal(contrasena_temporal=temporal)


@enrutador.patch("/usuarios/{user_id}/estado", response_model=SalidaUsuario)
async def cambiar_estado(
    user_id: int,
    datos: DatosCambiarEstado,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    usuario = await ServicioUsuarios(sesion).cambiar_estado(admin_id, user_id, datos.status)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ACTUALIZADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "estado": datos.status.value})
    return SalidaUsuario.model_validate(usuario)


@enrutador.patch("/usuarios/{user_id}/rol-personalizado", response_model=SalidaUsuario)
async def asignar_rol_a_usuario(
    user_id: int,
    datos: DatosAsignarRol,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    svc = ServicioUsuarios(sesion)
    usuario = await svc.asignar_rol(admin_id, user_id, datos.rol_id)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ACTUALIZADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "rol_id": datos.rol_id})
    return await svc.salida(usuario)


@enrutador.delete("/usuarios/{user_id}", status_code=204)
async def eliminar_usuario(
    user_id: int,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    nombre_usuario = await ServicioUsuarios(sesion).eliminar(admin_id, user_id)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ELIMINADO,
                        {"usuario_id": user_id, "usuario": nombre_usuario})


# ── Permisos (solo lectura) y roles ───────────────────────────────────────────

@enrutador.get("/permisos", response_model=list[SalidaPermiso])
async def listar_permisos(
    _: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    return await ServicioRoles(sesion).listar_permisos()


@enrutador.get("/roles", response_model=list[SalidaRol])
async def listar_roles(
    _: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    return await ServicioRoles(sesion).listar()


@enrutador.post("/roles", response_model=SalidaRol, status_code=201)
async def crear_rol(
    datos: DatosCrearRol,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    svc = ServicioRoles(sesion)
    rol = await svc.crear(datos)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_CREADO,
                        {"rol_id": rol.id, "nombre": rol.nombre})
    return await svc.salida(rol)


@enrutador.patch("/roles/{rol_id}", response_model=SalidaRol)
async def actualizar_rol(
    rol_id: int,
    datos: DatosActualizarRol,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    svc = ServicioRoles(sesion)
    rol = await svc.actualizar(rol_id, datos)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ACTUALIZADO,
                        {"rol_id": rol.id, "nombre": rol.nombre})
    return await svc.salida(rol)


@enrutador.delete("/roles/{rol_id}", status_code=204)
async def eliminar_rol(
    rol_id: int,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    nombre = await ServicioRoles(sesion).eliminar(rol_id)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ELIMINADO,
                        {"rol_id": rol_id, "nombre": nombre})


@enrutador.put("/roles/{rol_id}/permisos", response_model=SalidaRol)
async def asignar_permisos_a_rol(
    rol_id: int,
    datos: DatosAsignarPermisos,
    request: Request,
    admin_id: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    salida = await ServicioRoles(sesion).asignar_permisos(rol_id, datos.permiso_ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ACTUALIZADO,
                        {"rol_id": salida.id, "nombre": salida.nombre,
                         "permisos": [p.codigo for p in salida.permisos]})
    return salida


# ── Uso del sistema ───────────────────────────────────────────────────────────

@enrutador.get("/stats", response_model=SalidaUsoSistema)
async def obtener_estadisticas(
    # Los totales de todo el sistema (y las agencias con más solicitudes, de los dos
    # sectores): solo quien ve todos los sectores, el supervisor general y el
    # Administrador (por el atajo de usuario_tiene_permiso). Hasta el 2026-11-10
    # los veía UCVMM, cuando había un solo sector.
    _: int = Depends(requerir_algun_permiso(PERMISO_SUPERVISAR_TODO)),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Cuentas, agencias y documentos almacenados (el flujo tiene sus propias
    estadísticas en /solicitudes/estadisticas)."""
    return await ServicioUsoSistema(sesion).resumen()
