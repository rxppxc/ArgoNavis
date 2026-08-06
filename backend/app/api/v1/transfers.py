from urllib.parse import quote as url_quote
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.infrastructure.database import obtener_sesion_bd
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.repositories.transfer_repository import RepositorioTransferencia
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.models.audit_log import AccionAuditoria
from app.domain.services.transfer_service import ServicioTransferencia
from app.domain.schemas.transfer import (
    DatosCrearTransferencia, SalidaTransferencia, RespuestaTransferenciaPublica,
)
from app.domain.models.user import Usuario
from app.core.security import obtener_id_usuario_actual
from app.core.permisos import requerir_permiso
from app.core.email import enviar_notificacion_transferencia
from app.core.http_utils import obtener_ip, obtener_agente
from app.core.rate_limit import limiter, limite_descarga

enrutador = APIRouter(prefix="/transfers", tags=["transferencias"])


def _obtener_servicio(sesion: AsyncSession = Depends(obtener_sesion_bd)) -> ServicioTransferencia:
    return ServicioTransferencia(RepositorioTransferencia(sesion))


async def _obtener_usuario_actual(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd),
) -> Usuario:
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return usuario


@enrutador.get("/", response_model=list[SalidaTransferencia])
async def listar_transferencias(
    usuario: Usuario = Depends(_obtener_usuario_actual),
    svc: ServicioTransferencia = Depends(_obtener_servicio),
):
    return await svc.listar_por_usuario(usuario.id)


@enrutador.get("/todas-activas", response_model=list[SalidaTransferencia])
async def listar_todas_activas(
    _perm: int = Depends(requerir_permiso("T-PROCESAR-PACIFICO")),
    svc: ServicioTransferencia = Depends(_obtener_servicio),
):
    """Todas las transferencias activas subidas por cualquier Naviera — vista
    de Sector Pacífico (y Admin) del storage completo."""
    return await svc.listar_todas_activas()


@enrutador.post("/", response_model=SalidaTransferencia, status_code=201)
async def crear_transferencia(
    request:          Request,
    background_tasks: BackgroundTasks,
    files:         list[UploadFile] = File(...),
    title:         str              = Form(...),
    message:       Optional[str]    = Form(None),
    recipient:     Optional[str]    = Form(None),
    max_downloads: Optional[int]    = Form(None),
    usuario: Usuario = Depends(_obtener_usuario_actual),
    _perm:   int     = Depends(requerir_permiso("T-CREAR-BASICA")),
    svc: ServicioTransferencia = Depends(_obtener_servicio),
    sesion: AsyncSession = Depends(obtener_sesion_bd),
):
    datos = DatosCrearTransferencia(
        title=title, message=message, recipient=recipient, max_downloads=max_downloads,
    )
    resultado = await svc.crear(usuario.id, datos, files)

    await RepositorioAuditoria(sesion).registrar(
        AccionAuditoria.TRANSFERENCIA_CREADA,
        user_id=usuario.id, username=usuario.username,
        detalle={
            "token":        resultado.token,
            "titulo":       resultado.title,
            "destinatario": resultado.recipient,
            "archivos":     [f.original_name for f in resultado.files],
            "expira_en":    resultado.expires_at.isoformat() if resultado.expires_at else None,
        },
        ip=obtener_ip(request), agente=obtener_agente(request),
    )

    if resultado.recipient:
        fecha_exp = resultado.expires_at.strftime("%d/%m/%Y a las %H:%M") if resultado.expires_at else "—"
        background_tasks.add_task(
            enviar_notificacion_transferencia,
            recipient_email=resultado.recipient,
            sender_name=usuario.full_name,
            title=resultado.title,
            message=resultado.message,
            token=resultado.token,
            expires_at=fecha_exp,
            cantidad_archivos=len(resultado.files),
        )

    return resultado


@enrutador.get("/preview/{token}/{file_id}")
@limiter.limit(limite_descarga)
async def previsualizar_archivo(
    request: Request,
    token:   str,
    file_id: int,
    svc:     ServicioTransferencia = Depends(_obtener_servicio),
):
    ruta, mime, nombre = await svc.obtener_ruta_preview(token, file_id)
    return FileResponse(
        path=ruta,
        media_type=mime or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{url_quote(nombre)}",
            "Cache-Control": "private, max-age=300",
        },
    )


@enrutador.get("/public/{token}", response_model=RespuestaTransferenciaPublica)
@limiter.limit(limite_descarga)
async def obtener_transferencia_publica(
    request: Request,
    token: str,
    svc: ServicioTransferencia = Depends(_obtener_servicio),
):
    return await svc.obtener_publica(token)


@enrutador.get("/download/{token}")
@limiter.limit(limite_descarga)
async def descargar_transferencia(
    token:   str,
    request: Request,
    svc:     ServicioTransferencia = Depends(_obtener_servicio),
    sesion:  AsyncSession = Depends(obtener_sesion_bd),
):
    ruta, nombre_archivo = await svc.obtener_ruta_descarga(token)

    transferencia = await RepositorioTransferencia(sesion).buscar_por_token(token)
    if transferencia:
        await RepositorioAuditoria(sesion).registrar(
            AccionAuditoria.DESCARGA_REALIZADA,
            user_id=transferencia.user_id,
            username=transferencia.usuario.username if transferencia.usuario else None,
            detalle={"token": token, "archivo": nombre_archivo, "titulo": transferencia.title},
            ip=obtener_ip(request), agente=obtener_agente(request),
        )

    return FileResponse(path=ruta, filename=nombre_archivo, media_type="application/octet-stream")


@enrutador.delete("/{token}", status_code=204)
async def eliminar_transferencia(
    token:   str,
    request: Request,
    usuario: Usuario = Depends(_obtener_usuario_actual),
    svc:     ServicioTransferencia = Depends(_obtener_servicio),
    sesion:  AsyncSession = Depends(obtener_sesion_bd),
):
    transferencia = await RepositorioTransferencia(sesion).buscar_por_token(token)
    await svc.eliminar(token, usuario.id)

    await RepositorioAuditoria(sesion).registrar(
        AccionAuditoria.TRANSFERENCIA_ELIMINADA,
        user_id=usuario.id, username=usuario.username,
        detalle={
            "token":  token,
            "titulo": transferencia.title if transferencia else None,
        },
        ip=obtener_ip(request), agente=obtener_agente(request),
    )
