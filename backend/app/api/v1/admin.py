import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ldap3.core.exceptions import LDAPException
from app.infrastructure.database import obtener_sesion_bd
from app.core.config import obtener_configuracion
from app.core.security import cerrar_sesiones, generar_contrasena_temporal, hashear_password
from app.core.permisos import (
    ROL_ADMIN, ROL_SYSADMIN, requerir_admin_o_sysadmin, requerir_algun_permiso, requerir_sysadmin,
)
from app.api.v1.dependencias import auditar_admin
from app.domain.models.audit_log import AccionAuditoria
from app.core.ldap import servicio_ldap
from app.domain.models.user import Usuario, EstadoUsuario, TipoUsuario
from app.domain.models.rol import Rol, Permiso, RolPermiso
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.solicitud import FilaTopAgencia, SalidaUsoSistema
from app.domain.schemas.user import (
    SalidaUsuario, DatosCrearUsuario, DatosCambiarEstado, DatosCrearUsuarioLocal, RespuestaContrasenaTemporal,
)
from app.domain.schemas.rol import (
    SalidaPermiso,
    SalidaRol, RolMini, DatosCrearRol, DatosActualizarRol, DatosAsignarPermisos, DatosAsignarRol,
)

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()
enrutador     = APIRouter(prefix="/admin", tags=["admin"])


# ── Protección del último SysAdmin ───────────────────────────────────────────

async def _impedir_quedar_sin_sysadmin(sesion: AsyncSession, usuario: Usuario) -> None:
    """409 si `usuario` es el último SysAdmin activo: nadie podría administrar
    usuarios ni roles (el primero se asigna con app.infrastructure.asignar_rol)."""
    if not (usuario.rol_personalizado and usuario.rol_personalizado.nombre == ROL_SYSADMIN
            and usuario.status == EstadoUsuario.ACTIVO):
        return
    activos = (await sesion.execute(
        select(func.count()).select_from(Usuario).join(Rol, Rol.id == Usuario.rol_id)
        .where(Rol.nombre == ROL_SYSADMIN, Usuario.status == EstadoUsuario.ACTIVO)
    )).scalar() or 0
    if activos <= 1:
        raise HTTPException(
            status_code=409,
            detail="Es el único SysAdmin activo: asigna el rol SysAdmin a otra persona antes de quitárselo.",
        )


# ── Búsqueda en Active Directory ──────────────────────────────────────────────

@enrutador.get("/usuarios/buscar-ad")
async def buscar_en_ad(
    q: str = Query(..., min_length=2, description="Nombre, usuario o email a buscar"),
    _: int = Depends(requerir_sysadmin),
):
    try:
        resultados = await asyncio.to_thread(servicio_ldap.buscar_usuarios_ad, q)
        return resultados
    except LDAPException as e:
        logger.error(f"Error buscando en AD: {e}")
        raise HTTPException(status_code=503, detail="No se pudo conectar al Active Directory.")


# ── Listado de usuarios ───────────────────────────────────────────────────────

@enrutador.get("/usuarios", response_model=list[SalidaUsuario])
async def listar_usuarios(
    _: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioUsuario(sesion)
    return await repo.listar_todos()


# ── Crear usuario desde AD ────────────────────────────────────────────────────

@enrutador.post("/usuarios", response_model=SalidaUsuario, status_code=201)
async def crear_usuario(
    datos: DatosCrearUsuario,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    try:
        ldap_usuario = await asyncio.to_thread(servicio_ldap.buscar_usuario, datos.username)
    except LDAPException as e:
        logger.error(f"Error buscando usuario en AD: {e}")
        raise HTTPException(status_code=503, detail="No se pudo conectar al Active Directory.")

    if not ldap_usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en Active Directory.")

    repo = RepositorioUsuario(sesion)
    existente = await repo.buscar_por_nombre_usuario(ldap_usuario["username"])
    if existente:
        raise HTTPException(status_code=409, detail="El usuario ya existe en el sistema.")

    usuario = await repo.crear_desde_ldap(ldap_usuario)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_CREADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "origen": "ad"})
    return usuario


# ── Cuentas locales (sin AD) ──────────────────────────────────────────────────
# Para usuarios externos, como los de las agencias navieras. Requieren
# PERMITIR_LOGIN_LOCAL. Entran con la contraseña que les da el admin y el
# sistema les pide cambiarla.

@enrutador.post("/usuarios/local", response_model=SalidaUsuario, status_code=201)
async def crear_usuario_local(
    datos: DatosCrearUsuarioLocal,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    if not configuracion.PERMITIR_LOGIN_LOCAL:
        raise HTTPException(status_code=403, detail="Las cuentas locales están deshabilitadas (PERMITIR_LOGIN_LOCAL).")

    repo = RepositorioUsuario(sesion)
    existente = await repo.buscar_por_nombre_usuario(datos.username)
    if existente:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese nombre.")

    if datos.rol_id is not None:
        rol_q = await sesion.execute(select(Rol).where(Rol.id == datos.rol_id))
        if not rol_q.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Rol no encontrado.")

    usuario = await repo.crear_local(
        username=datos.username,
        password_hash=hashear_password(datos.password),
        name=datos.name, last_name=datos.last_name, email=datos.email,
        rol_id=datos.rol_id,
    )
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_CREADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "origen": "local",
                         "rol_id": usuario.rol_id})
    salida = SalidaUsuario.model_validate(usuario)
    if usuario.rol_id is not None:
        rol = (await sesion.execute(select(Rol).where(Rol.id == usuario.rol_id))).scalar_one_or_none()
        if rol:
            salida.rol_personalizado = RolMini.model_validate(rol)
    return salida


@enrutador.post("/usuarios/{user_id}/restablecer-contrasena", response_model=RespuestaContrasenaTemporal)
async def restablecer_contrasena(
    user_id: int,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Genera una contraseña temporal para una cuenta local (y la desbloquea).
    Se muestra una sola vez; el usuario debe cambiarla al entrar."""
    if not configuracion.PERMITIR_LOGIN_LOCAL:
        raise HTTPException(status_code=403, detail="Las cuentas locales están deshabilitadas (PERMITIR_LOGIN_LOCAL).")
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if usuario.user_type != TipoUsuario.LOCAL:
        raise HTTPException(status_code=400, detail="Es una cuenta del Active Directory: su contraseña la gestiona TI.")

    temporal = generar_contrasena_temporal()
    usuario.password_hash = hashear_password(temporal)
    usuario.debe_cambiar_password = True
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    cerrar_sesiones(usuario)   # quien tuviera la sesión abierta vuelve a entrar con la temporal
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.CONTRASENA_RESTABLECIDA,
                        {"usuario_id": usuario.id, "usuario": usuario.username})
    return RespuestaContrasenaTemporal(contrasena_temporal=temporal)


# ── Cambiar estado (activo / inactivo) ────────────────────────────────────────

@enrutador.patch("/usuarios/{user_id}/estado", response_model=SalidaUsuario)
async def cambiar_estado(
    user_id: int,
    datos: DatosCambiarEstado,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    if user_id == admin_id and datos.status != EstadoUsuario.ACTIVO:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")

    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if datos.status != EstadoUsuario.ACTIVO:
        await _impedir_quedar_sin_sysadmin(sesion, usuario)
        cerrar_sesiones(usuario)   # al reactivarla, los tokens de antes ya no valen

    usuario.status = datos.status
    await sesion.flush()
    await sesion.refresh(usuario)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ACTUALIZADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "estado": datos.status.value})
    return SalidaUsuario.model_validate(usuario)


# ── Eliminar usuario ──────────────────────────────────────────────────────────

@enrutador.delete("/usuarios/{user_id}", status_code=204)
async def eliminar_usuario(
    user_id: int,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta.")

    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    await _impedir_quedar_sin_sysadmin(sesion, usuario)
    # Las solicitudes que creó son registros del flujo: la BD impide borrar
    # al usuario (FK RESTRICT). Se desactiva en su lugar.
    if await RepositorioSolicitud(sesion).contar_creadas_por(user_id):
        raise HTTPException(
            status_code=409,
            detail="El usuario tiene solicitudes de autorización registradas: desactívalo en lugar de eliminarlo.",
        )
    nombre_usuario = usuario.username
    await sesion.delete(usuario)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ELIMINADO,
                        {"usuario_id": user_id, "usuario": nombre_usuario})


# ── Permisos ──────────────────────────────────────────────────────────────────
# Solo lectura: los siembran las migraciones y el código revisa esos códigos
# (T-CREAR-BASICA, T-PROCESAR-PACIFICO, T-FINALIZAR-PUERTO). Crearlos desde la
# UI no servía de nada y borrar uno dejaba el flujo sin acceso.

@enrutador.get("/permisos", response_model=list[SalidaPermiso])
async def listar_permisos(
    _: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Permiso).order_by(Permiso.codigo))
    return list(resultado.scalars().all())


# ── Roles ─────────────────────────────────────────────────────────────────────

async def _construir_salida_rol(sesion: AsyncSession, rol: Rol) -> SalidaRol:
    permisos_q = await sesion.execute(
        select(Permiso)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == rol.id)
        .order_by(Permiso.codigo)
    )
    permisos = [SalidaPermiso.model_validate(p) for p in permisos_q.scalars().all()]
    total_usuarios = (await sesion.execute(
        select(func.count()).select_from(Usuario).where(Usuario.rol_id == rol.id)
    )).scalar() or 0
    # Construimos a mano: model_validate(rol) intentaría leer rol.permisos
    # (relación a RolPermiso, no a SalidaPermiso) y revienta.
    return SalidaRol(
        id=rol.id,
        nombre=rol.nombre,
        descripcion=rol.descripcion,
        es_sistema=rol.es_sistema,
        created_at=rol.created_at,
        permisos=permisos,
        total_usuarios=total_usuarios,
    )


@enrutador.get("/roles", response_model=list[SalidaRol])
async def listar_roles(
    _: int = Depends(requerir_admin_o_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Rol).order_by(Rol.nombre))
    roles = list(resultado.scalars().all())
    salida = []
    for r in roles:
        salida.append(await _construir_salida_rol(sesion, r))
    return salida


@enrutador.post("/roles", response_model=SalidaRol, status_code=201)
async def crear_rol(
    datos: DatosCrearRol,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    existente = await sesion.execute(select(Rol).where(Rol.nombre == datos.nombre))
    if existente.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre.")
    rol = Rol(nombre=datos.nombre, descripcion=datos.descripcion, es_sistema=False)
    sesion.add(rol)
    await sesion.flush()
    await sesion.refresh(rol)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_CREADO,
                        {"rol_id": rol.id, "nombre": rol.nombre})
    return await _construir_salida_rol(sesion, rol)


@enrutador.patch("/roles/{rol_id}", response_model=SalidaRol)
async def actualizar_rol(
    rol_id: int,
    datos: DatosActualizarRol,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Rol).where(Rol.id == rol_id))
    rol = resultado.scalar_one_or_none()
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if datos.nombre is not None:
        nuevo_nombre = datos.nombre.strip()
        if not nuevo_nombre:
            raise HTTPException(status_code=400, detail="El nombre no puede estar vacío.")
        if nuevo_nombre != rol.nombre and rol.nombre in (ROL_ADMIN, ROL_SYSADMIN):
            # Los permisos de administración se resuelven por estos nombres.
            raise HTTPException(status_code=400, detail=f"El rol {rol.nombre} no se puede renombrar.")
        if nuevo_nombre != rol.nombre:
            dup = await sesion.execute(select(Rol).where(Rol.nombre == nuevo_nombre, Rol.id != rol_id))
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Ya existe otro rol con ese nombre.")
            rol.nombre = nuevo_nombre
    if datos.descripcion is not None:
        rol.descripcion = datos.descripcion
    await sesion.flush()
    await sesion.refresh(rol)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ACTUALIZADO,
                        {"rol_id": rol.id, "nombre": rol.nombre})
    return await _construir_salida_rol(sesion, rol)


@enrutador.delete("/roles/{rol_id}", status_code=204)
async def eliminar_rol(
    rol_id: int,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Rol).where(Rol.id == rol_id))
    rol = resultado.scalar_one_or_none()
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if rol.es_sistema:
        raise HTTPException(status_code=400, detail="No se puede eliminar un rol del sistema.")
    nombre = rol.nombre
    await sesion.delete(rol)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ELIMINADO,
                        {"rol_id": rol_id, "nombre": nombre})


@enrutador.put("/roles/{rol_id}/permisos", response_model=SalidaRol)
async def asignar_permisos_a_rol(
    rol_id: int,
    datos: DatosAsignarPermisos,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Rol).where(Rol.id == rol_id))
    rol = resultado.scalar_one_or_none()
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    ids_unicos = list(set(datos.permiso_ids))
    if ids_unicos:
        validos = await sesion.execute(select(Permiso.id).where(Permiso.id.in_(ids_unicos)))
        ids_validos = {row[0] for row in validos.all()}
        invalidos = set(ids_unicos) - ids_validos
        if invalidos:
            raise HTTPException(status_code=400, detail=f"Permisos no encontrados: {sorted(invalidos)}")

    # Borrar asignaciones actuales y volver a crear (sincronización total)
    actuales_q = await sesion.execute(select(RolPermiso).where(RolPermiso.rol_id == rol_id))
    for rp in actuales_q.scalars().all():
        await sesion.delete(rp)
    await sesion.flush()
    for pid in ids_unicos:
        sesion.add(RolPermiso(rol_id=rol_id, permiso_id=pid))
    await sesion.flush()
    salida = await _construir_salida_rol(sesion, rol)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.ROL_ACTUALIZADO,
                        {"rol_id": rol.id, "nombre": rol.nombre,
                         "permisos": [p.codigo for p in salida.permisos]})
    return salida


# ── Asignar rol personalizado a un usuario ────────────────────────────────────

@enrutador.patch("/usuarios/{user_id}/rol-personalizado", response_model=SalidaUsuario)
async def asignar_rol_a_usuario(
    user_id: int,
    datos: DatosAsignarRol,
    request: Request,
    admin_id: int = Depends(requerir_sysadmin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if datos.rol_id is not None:
        rol_q = await sesion.execute(select(Rol).where(Rol.id == datos.rol_id))
        if not rol_q.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if datos.rol_id != usuario.rol_id:
        await _impedir_quedar_sin_sysadmin(sesion, usuario)
    usuario.rol_id = datos.rol_id
    await sesion.flush()
    await sesion.refresh(usuario)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.USUARIO_ACTUALIZADO,
                        {"usuario_id": usuario.id, "usuario": usuario.username, "rol_id": datos.rol_id})
    salida = SalidaUsuario.model_validate(usuario)
    if usuario.rol_id is not None:
        rol = (await sesion.execute(select(Rol).where(Rol.id == usuario.rol_id))).scalar_one_or_none()
        if rol:
            salida.rol_personalizado = RolMini.model_validate(rol)
    return salida


# ── Uso del sistema ───────────────────────────────────────────────────────────

@enrutador.get("/stats", response_model=SalidaUsoSistema)
async def obtener_estadisticas(
    # Admin entra por el atajo de usuario_tiene_permiso(); UCVMM por su permiso.
    _: int = Depends(requerir_algun_permiso("T-PROCESAR-PACIFICO")),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Cuentas, agencias y documentos almacenados (el flujo tiene sus propias
    estadísticas en /solicitudes/estadisticas)."""
    repo_solicitudes = RepositorioSolicitud(sesion)
    usuarios, activos = await RepositorioUsuario(sesion).contar()
    documentos, almacenamiento_bytes = await repo_solicitudes.totales_documentos()
    return SalidaUsoSistema(
        usuarios=usuarios,
        usuarios_activos=activos,
        agencias=await RepositorioCatalogo(sesion).contar_agencias(),
        documentos=documentos,
        almacenamiento_bytes=almacenamiento_bytes,
        top_agencias=[
            FilaTopAgencia(agencia_id=f.agencia_id, nombre=f.agencia_nombre, total=f.total)
            for f in await repo_solicitudes.top_agencias()
        ],
    )
