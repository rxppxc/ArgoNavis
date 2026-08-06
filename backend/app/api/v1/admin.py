import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from ldap3.core.exceptions import LDAPException
from app.infrastructure.database import obtener_sesion_bd
from app.core.config import obtener_configuracion
from app.core.security import obtener_id_usuario_actual, hashear_password
from app.core.permisos import es_admin_efectivo, requerir_algun_permiso
from app.core.ldap import servicio_ldap
from app.domain.models.user import Usuario, EstadoUsuario
from app.domain.models.transfer import Transferencia, ArchivoTransferencia, EstadoTransferencia
from app.domain.models.rol import Rol, Permiso, RolPermiso
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.user import SalidaUsuario, DatosCrearUsuario, DatosCambiarEstado, DatosCrearUsuarioLocal
from app.domain.schemas.rol import (
    SalidaPermiso, DatosCrearPermiso, DatosActualizarPermiso,
    SalidaRol, RolMini, DatosCrearRol, DatosActualizarRol, DatosAsignarPermisos, DatosAsignarRol,
)

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()
enrutador     = APIRouter(prefix="/admin", tags=["admin"])


# ── Dependencia: solo administradores ────────────────────────────────────────

async def requerir_admin(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
) -> int:
    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario or not es_admin_efectivo(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador para acceder a esta función.",
        )
    return user_id


# ── Búsqueda en Active Directory ──────────────────────────────────────────────

@enrutador.get("/usuarios/buscar-ad")
async def buscar_en_ad(
    q: str = Query(..., min_length=2, description="Nombre, usuario o email a buscar"),
    _: int = Depends(requerir_admin),
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
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    repo = RepositorioUsuario(sesion)
    return await repo.listar_todos()


# ── Crear usuario desde AD ────────────────────────────────────────────────────

@enrutador.post("/usuarios", response_model=SalidaUsuario, status_code=201)
async def crear_usuario(
    datos: DatosCrearUsuario,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
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

    return await repo.crear_desde_ldap(ldap_usuario)


# ── Usuario local de prueba (sin AD, solo fuera de producción) ───────────────
# Atajo temporal para probar roles/permisos sin depender de Active Directory.
# Se elimina junto con la rama de login local antes de pasar a producción.

@enrutador.post("/usuarios/local", response_model=SalidaUsuario, status_code=201)
async def crear_usuario_local(
    datos: DatosCrearUsuarioLocal,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    if not configuracion.PERMITIR_LOGIN_LOCAL:
        raise HTTPException(status_code=403, detail="No disponible en producción.")

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
    salida = SalidaUsuario.model_validate(usuario)
    if usuario.rol_id is not None:
        rol = (await sesion.execute(select(Rol).where(Rol.id == usuario.rol_id))).scalar_one_or_none()
        if rol:
            salida.rol_personalizado = RolMini.model_validate(rol)
    return salida


# ── Cambiar estado (activo / inactivo) ────────────────────────────────────────

@enrutador.patch("/usuarios/{user_id}/estado", response_model=SalidaUsuario)
async def cambiar_estado(
    user_id: int,
    datos: DatosCambiarEstado,
    admin_id: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    if user_id == admin_id and datos.status != EstadoUsuario.ACTIVO:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")

    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    usuario.status = datos.status
    await sesion.flush()
    await sesion.refresh(usuario)
    return SalidaUsuario.model_validate(usuario)


# ── Eliminar usuario ──────────────────────────────────────────────────────────

@enrutador.delete("/usuarios/{user_id}", status_code=204)
async def eliminar_usuario(
    user_id: int,
    admin_id: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta.")

    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    await sesion.delete(usuario)


# ── Permisos ──────────────────────────────────────────────────────────────────

@enrutador.get("/permisos", response_model=list[SalidaPermiso])
async def listar_permisos(
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Permiso).order_by(Permiso.codigo))
    return list(resultado.scalars().all())


@enrutador.post("/permisos", response_model=SalidaPermiso, status_code=201)
async def crear_permiso(
    datos: DatosCrearPermiso,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    existente = await sesion.execute(select(Permiso).where(Permiso.codigo == datos.codigo))
    if existente.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un permiso con ese código.")
    permiso = Permiso(codigo=datos.codigo, nombre=datos.nombre, descripcion=datos.descripcion)
    sesion.add(permiso)
    await sesion.flush()
    await sesion.refresh(permiso)
    return SalidaPermiso.model_validate(permiso)


@enrutador.patch("/permisos/{permiso_id}", response_model=SalidaPermiso)
async def actualizar_permiso(
    permiso_id: int,
    datos: DatosActualizarPermiso,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Permiso).where(Permiso.id == permiso_id))
    permiso = resultado.scalar_one_or_none()
    if not permiso:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")
    if datos.nombre is not None:
        permiso.nombre = datos.nombre.strip()
    if datos.descripcion is not None:
        permiso.descripcion = datos.descripcion
    await sesion.flush()
    await sesion.refresh(permiso)
    return SalidaPermiso.model_validate(permiso)


@enrutador.delete("/permisos/{permiso_id}", status_code=204)
async def eliminar_permiso(
    permiso_id: int,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Permiso).where(Permiso.id == permiso_id))
    permiso = resultado.scalar_one_or_none()
    if not permiso:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")
    await sesion.delete(permiso)


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
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
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
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    existente = await sesion.execute(select(Rol).where(Rol.nombre == datos.nombre))
    if existente.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre.")
    rol = Rol(nombre=datos.nombre, descripcion=datos.descripcion, es_sistema=False)
    sesion.add(rol)
    await sesion.flush()
    await sesion.refresh(rol)
    return await _construir_salida_rol(sesion, rol)


@enrutador.patch("/roles/{rol_id}", response_model=SalidaRol)
async def actualizar_rol(
    rol_id: int,
    datos: DatosActualizarRol,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Rol).where(Rol.id == rol_id))
    rol = resultado.scalar_one_or_none()
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if datos.nombre is not None:
        nuevo_nombre = datos.nombre.strip()
        if not nuevo_nombre:
            raise HTTPException(status_code=400, detail="El nombre no puede estar vacío.")
        if nuevo_nombre != rol.nombre:
            dup = await sesion.execute(select(Rol).where(Rol.nombre == nuevo_nombre, Rol.id != rol_id))
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Ya existe otro rol con ese nombre.")
            rol.nombre = nuevo_nombre
    if datos.descripcion is not None:
        rol.descripcion = datos.descripcion
    await sesion.flush()
    await sesion.refresh(rol)
    return await _construir_salida_rol(sesion, rol)


@enrutador.delete("/roles/{rol_id}", status_code=204)
async def eliminar_rol(
    rol_id: int,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Rol).where(Rol.id == rol_id))
    rol = resultado.scalar_one_or_none()
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if rol.es_sistema:
        raise HTTPException(status_code=400, detail="No se puede eliminar un rol del sistema.")
    await sesion.delete(rol)


@enrutador.put("/roles/{rol_id}/permisos", response_model=SalidaRol)
async def asignar_permisos_a_rol(
    rol_id: int,
    datos: DatosAsignarPermisos,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
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
    return await _construir_salida_rol(sesion, rol)


# ── Asignar rol personalizado a un usuario ────────────────────────────────────

@enrutador.patch("/usuarios/{user_id}/rol-personalizado", response_model=SalidaUsuario)
async def asignar_rol_a_usuario(
    user_id: int,
    datos: DatosAsignarRol,
    _: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    resultado = await sesion.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = resultado.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if datos.rol_id is not None:
        rol_q = await sesion.execute(select(Rol).where(Rol.id == datos.rol_id))
        if not rol_q.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
    usuario.rol_id = datos.rol_id
    await sesion.flush()
    await sesion.refresh(usuario)
    salida = SalidaUsuario.model_validate(usuario)
    if usuario.rol_id is not None:
        rol = (await sesion.execute(select(Rol).where(Rol.id == usuario.rol_id))).scalar_one_or_none()
        if rol:
            salida.rol_personalizado = RolMini.model_validate(rol)
    return salida


# ── Estadísticas globales ─────────────────────────────────────────────────────

@enrutador.get("/stats")
async def obtener_estadisticas(
    # Admin ve todo por el shortcut interno de usuario_tiene_permiso(); Sector
    # Pacífico entra por tener el permiso T-PROCESAR-PACIFICO. Antes esto era
    # admin-only aunque el frontend ya le mostraba el link a SP (quedaba roto).
    _: int = Depends(requerir_algun_permiso("T-PROCESAR-PACIFICO")),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    # Conteos a nivel de BD — evita cargar filas completas a memoria.
    total_usuarios = (await sesion.execute(select(func.count()).select_from(Usuario))).scalar() or 0

    no_eliminada = Transferencia.status != EstadoTransferencia.ELIMINADA
    ahora        = datetime.now(timezone.utc)

    total_transferencias = (await sesion.execute(
        select(func.count()).select_from(Transferencia).where(no_eliminada)
    )).scalar() or 0

    activas = (await sesion.execute(
        select(func.count()).select_from(Transferencia).where(
            and_(no_eliminada, or_(Transferencia.expires_at.is_(None), Transferencia.expires_at > ahora))
        )
    )).scalar() or 0

    expiradas = (await sesion.execute(
        select(func.count()).select_from(Transferencia).where(
            and_(no_eliminada, Transferencia.expires_at.isnot(None), Transferencia.expires_at <= ahora)
        )
    )).scalar() or 0

    total_descargas = (await sesion.execute(
        select(func.coalesce(func.sum(Transferencia.downloads), 0)).where(no_eliminada)
    )).scalar() or 0

    # Storage agregado vía JOIN — evita el O(N*M) de cargar archivos por transferencia
    total_storage = (await sesion.execute(
        select(func.coalesce(func.sum(ArchivoTransferencia.size), 0))
        .join(Transferencia, Transferencia.id == ArchivoTransferencia.transfer_id)
        .where(no_eliminada)
    )).scalar() or 0

    # Top 5 subidores
    uploader_q = await sesion.execute(
        select(Usuario.id, Usuario.name, Usuario.last_name, Usuario.username, func.count(Transferencia.id).label("total"))
        .join(Transferencia, Transferencia.user_id == Usuario.id)
        .where(Transferencia.status != EstadoTransferencia.ELIMINADA)
        .group_by(Usuario.id, Usuario.name, Usuario.last_name, Usuario.username)
        .order_by(func.count(Transferencia.id).desc())
        .limit(5)
    )
    top_uploaders = [
        {
            "id": row.id,
            "full_name": " ".join(filter(None, [row.name, row.last_name])) or row.username,
            "total": row.total,
        }
        for row in uploader_q.all()
    ]

    return {
        "usuarios":             total_usuarios,
        "transferencias":       total_transferencias,
        "activas":              activas,
        "expiradas":            expiradas,
        "total_descargas":      total_descargas,
        "storage_bytes":        total_storage,
        "top_uploaders":        top_uploaders,
    }
