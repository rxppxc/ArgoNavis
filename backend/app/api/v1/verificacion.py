"""Verificación pública del QR de una Autorización Marítima.

Endpoint sin autenticación (lo abre quien escanea el PDF), con rate limit:
el código es aleatorio de 192 bits, pero igual se frena el barrido.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_utils import obtener_agente, obtener_ip
from app.core.rate_limit import limite_verificacion, limiter
from app.domain.models.audit_log import AccionAuditoria
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.schemas.solicitud import SalidaVerificacion
from app.domain.services.solicitud_service import ServicioSolicitud
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(prefix="/verificacion", tags=["verificacion"])


@enrutador.get("/{codigo}", response_model=SalidaVerificacion)
@limiter.limit(limite_verificacion)
async def verificar_autorizacion(
    request: Request,
    codigo:  str,
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await ServicioSolicitud(sesion).verificar(codigo)
    await RepositorioAuditoria(sesion).registrar(
        AccionAuditoria.AUTORIZACION_VERIFICADA,
        detalle={"numero": resultado.numero, "estado": resultado.estado, "valida": resultado.valida},
        ip=obtener_ip(request), agente=obtener_agente(request),
    )
    return resultado
