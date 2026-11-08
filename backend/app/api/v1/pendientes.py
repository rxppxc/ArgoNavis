"""Notificaciones internas: la campana de la cabecera. Solo con sesión."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import usuario_actual
from app.domain.models.user import Usuario
from app.domain.schemas.pendientes import SalidaPendientes
from app.domain.services.pendientes_service import ServicioPendientes
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(prefix="/pendientes", tags=["pendientes"])


@enrutador.get("", response_model=SalidaPendientes)
async def consultar_pendientes(
    usuario: Usuario      = Depends(usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Lo que le toca hacer al usuario y las novedades de sus solicitudes. La
    interfaz lo consulta cada minuto con la pestaña a la vista."""
    return await ServicioPendientes(sesion).consultar(usuario)


@enrutador.post("/vistas", status_code=204)
async def marcar_novedades_vistas(
    usuario: Usuario      = Depends(usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """El usuario abrió la campana: sus novedades hasta ahora quedan leídas."""
    await ServicioPendientes(sesion).marcar_vistas(usuario)
    return Response(status_code=204)
