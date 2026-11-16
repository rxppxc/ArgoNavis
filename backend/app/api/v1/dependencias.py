"""Dependencias y utilidades compartidas por los routers de la API: quién pide
(`obtener_id_usuario_actual`, `usuario_actual`), qué puede (`requerir_*`) y la
bitácora (`auditar`). Hasta el 2026-11-14, las dos primeras estaban en
core/security.py y core/permisos.py."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_utils import obtener_agente, obtener_ip
from app.core.permisos import es_admin_efectivo, es_sysadmin_efectivo, usuario_tiene_permiso
from app.core.security import AGENCIA_DESACTIVADA, CABECERA_CAMBIO_CONTRASENA, decodificar_token, esquema_bearer
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.catalogo import AgenciaNaviera
from app.domain.models.user import EstadoUsuario, Usuario
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.repositories.user_repository import RepositorioUsuario
from app.infrastructure.database import obtener_sesion_bd

# Rutas que una cuenta con cambio de contraseña pendiente sí puede usar: ver su
# perfil y permisos, cambiar la contraseña y cerrar la sesión.
_RUTAS_CON_CAMBIO_PENDIENTE = {
    "/api/v1/auth/me", "/api/v1/auth/me/permisos", "/api/v1/auth/cambiar-contrasena",
    "/api/v1/auth/logout", "/api/v1/auth/session-expired", "/api/v1/auth/refresh",
}


async def obtener_id_usuario_actual(
    request:      Request,
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_bearer),
    sesion:       AsyncSession                 = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Devuelve el id del usuario autenticado, verificando que la cuenta siga
    activa en cada request. Cualquier cambio de estado (desactivado, borrado)
    invalida el token de inmediato sin esperar al vencimiento.

    Una cuenta local con cambio de contraseña pendiente (recién creada o
    restablecida por el admin) solo puede usar las rutas para cambiarla."""
    carga   = decodificar_token(credenciales.credentials)
    user_id = carga.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.") from None

    fila = (await sesion.execute(
        select(Usuario.status, Usuario.debe_cambiar_password, Usuario.sesiones_validas_desde,
               AgenciaNaviera.activo)
        .outerjoin(AgenciaNaviera, AgenciaNaviera.id == Usuario.agencia_id)
        .where(Usuario.id == uid)
    )).one_or_none()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La cuenta ya no existe.")
    estado, debe_cambiar, validas_desde, agencia_activa = fila
    if validas_desde is not None:
        emitido = carga.get("iat")
        if not isinstance(emitido, (int, float)) or emitido < validas_desde.timestamp():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión se cerró. Inicia sesión de nuevo.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    # EstadoUsuario hereda de str, así que el miembro enum y su .value ("active")
    # comparan igual; una sola comparación cubre ambos casos.
    if estado != EstadoUsuario.ACTIVO.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta está desactivada.")
    if agencia_activa is False:
        # Agencia desactivada: sus usuarios quedan fuera, también con la sesión
        # abierta. 401 para que el frontend la cierre; el login dice por qué.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AGENCIA_DESACTIVADA,
                            headers={"WWW-Authenticate": "Bearer"})
    if debe_cambiar and request.url.path not in _RUTAS_CON_CAMBIO_PENDIENTE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña antes de continuar.",
            headers={CABECERA_CAMBIO_CONTRASENA: "requerido"},
        )
    return uid


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


async def requerir_admin_o_sysadmin(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Dependencia: Administrador o SysAdmin (usuarios, roles, permisos y bitácora)."""
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


async def usuario_actual(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> Usuario:
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return usuario


async def auditar(
    sesion: AsyncSession, request: Request, accion: AccionAuditoria, *,
    usuario: Usuario | None = None, user_id: int | None = None, username: str | None = None,
    detalle: dict | None = None,
) -> None:
    """Una línea en la bitácora con la IP y el navegador de quien pide: la forma de
    anotar desde la API. Con `usuario`, su id y su nombre; si no, los que se pasen,
    o ninguno (lo público, como la verificación del QR)."""
    if usuario is not None:
        user_id, username = usuario.id, usuario.username
    await RepositorioAuditoria(sesion).registrar(
        accion, user_id=user_id, username=username, detalle=detalle,
        ip=obtener_ip(request), agente=obtener_agente(request),
    )


async def auditar_admin(
    sesion: AsyncSession, request: Request, admin_id: int,
    accion: AccionAuditoria, detalle: dict,
) -> None:
    """Deja en la bitácora una acción administrativa, con el usuario que la hizo."""
    admin = await RepositorioUsuario(sesion).buscar_por_id(admin_id)
    await auditar(sesion, request, accion, user_id=admin_id, username=admin.username if admin else None,
                  detalle=detalle)
