from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.infrastructure.database import obtener_sesion_bd
from app.api.v1.dependencias import usuario_actual
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.user import Usuario
from app.domain.models.rol import Permiso, RolPermiso
from app.domain.services.auth_service import ServicioAutenticacion
from app.domain.schemas.user import DatosCambiarContrasena, SolicitudLogin, RespuestaToken, SalidaUsuario
from app.core.config import obtener_configuracion
from app.core.security import (
    cerrar_sesiones, crear_token_acceso, decodificar_token, esquema_bearer, inicio_de_sesion,
    obtener_id_usuario_actual,
)
from app.core.http_utils import obtener_ip, obtener_agente
from app.core.rate_limit import limiter

configuracion = obtener_configuracion()
enrutador     = APIRouter(prefix="/auth", tags=["autenticacion"])


@enrutador.post("/login", response_model=RespuestaToken)
@limiter.limit("10/minute")
async def iniciar_sesion(
    cuerpo:  SolicitudLogin,
    request: Request,
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    audit = RepositorioAuditoria(sesion)
    svc   = ServicioAutenticacion(RepositorioUsuario(sesion), audit)
    try:
        resultado = await svc.login(cuerpo.username, cuerpo.password)
    except HTTPException as exc:
        await audit.registrar(
            AccionAuditoria.LOGIN_FALLIDO,
            username=cuerpo.username,
            # El motivo real (p. ej. "usuario no encontrado en el AD") solo va a la
            # bitácora; al usuario le llega el mensaje genérico (ErrorAcceso).
            detalle={"motivo": getattr(exc, "motivo", exc.detail)},
            ip=obtener_ip(request), agente=obtener_agente(request),
        )
        # Se responde sin relanzar: así la transacción se confirma y quedan
        # guardados el intento fallido (bloqueo de la cuenta) y la bitácora.
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    await audit.registrar(
        AccionAuditoria.LOGIN_EXITOSO,
        user_id=resultado.user.id, username=resultado.user.username,
        ip=obtener_ip(request), agente=obtener_agente(request),
    )
    return resultado


@enrutador.post("/cambiar-contrasena", response_model=RespuestaToken)
@limiter.limit("10/minute")
async def cambiar_contrasena(
    datos:   DatosCambiarContrasena,
    request: Request,
    usuario: Usuario = Depends(usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Cambio de la propia contraseña (cuentas locales). También es el paso
    obligatorio tras el alta o un restablecimiento hecho por el admin. Cierra
    las demás sesiones de la cuenta y devuelve un token nuevo para esta."""
    audit = RepositorioAuditoria(sesion)
    respuesta = await ServicioAutenticacion(RepositorioUsuario(sesion), audit).cambiar_contrasena(
        usuario, datos.actual, datos.nueva,
    )
    await audit.registrar(
        AccionAuditoria.CONTRASENA_CAMBIADA,
        user_id=usuario.id, username=usuario.username,
        ip=obtener_ip(request), agente=obtener_agente(request),
    )
    return respuesta


@enrutador.post("/logout", status_code=204)
async def cerrar_sesion(
    request: Request,
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Cierra la sesión: los tokens ya emitidos para la cuenta dejan de valer
    (en cualquier navegador), así uno copiado no sigue funcionando."""
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if usuario:
        cerrar_sesiones(usuario)
    await RepositorioAuditoria(sesion).registrar(
        AccionAuditoria.CERRAR_SESION,
        user_id=user_id,
        username=usuario.username if usuario else None,
        ip=obtener_ip(request), agente=obtener_agente(request),
    )


@enrutador.post("/session-expired", status_code=204)
async def sesion_expirada(
    request: Request,
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    await RepositorioAuditoria(sesion).registrar(
        AccionAuditoria.SESION_EXPIRADA,
        user_id=user_id,
        username=usuario.username if usuario else None,
        ip=obtener_ip(request), agente=obtener_agente(request),
    )


@enrutador.post("/refresh", response_model=RespuestaToken)
async def refrescar_sesion(
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_bearer),
    user_id:      int = Depends(obtener_id_usuario_actual),
    sesion:       AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Renueva el token de la sesión en curso, sin pasar de SESION_MAXIMA_HORAS
    desde el login (el nuevo token conserva ese inicio)."""
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    inicio = inicio_de_sesion(decodificar_token(credenciales.credentials))
    if datetime.now(timezone.utc) - inicio >= timedelta(hours=configuracion.SESION_MAXIMA_HORAS):
        raise HTTPException(status_code=401, detail="La sesión llegó a su duración máxima. Inicia sesión de nuevo.")
    token = crear_token_acceso(subject=usuario.id, extra={"username": usuario.username}, inicio_sesion=inicio)
    return RespuestaToken(access_token=token, user=SalidaUsuario.model_validate(usuario))


@enrutador.get("/me", response_model=SalidaUsuario)
async def perfil_actual(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    return SalidaUsuario.model_validate(usuario)


@enrutador.get("/me/permisos", response_model=list[str])
async def permisos_actuales(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    usuario = (await sesion.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if usuario.rol_id is None:
        return []
    resultado = await sesion.execute(
        select(Permiso.codigo)
        .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
        .where(RolPermiso.rol_id == usuario.rol_id)
        .order_by(Permiso.codigo)
    )
    return [row[0] for row in resultado.all()]
