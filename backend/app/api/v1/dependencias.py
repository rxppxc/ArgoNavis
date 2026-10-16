"""Dependencias y utilidades compartidas por los routers de la API."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_utils import obtener_agente, obtener_ip
from app.core.security import obtener_id_usuario_actual
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.user import Usuario
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.repositories.user_repository import RepositorioUsuario
from app.infrastructure.database import obtener_sesion_bd


async def usuario_actual(
    user_id: int = Depends(obtener_id_usuario_actual),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
) -> Usuario:
    usuario = await RepositorioUsuario(sesion).buscar_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return usuario


async def auditar_admin(
    sesion: AsyncSession, request: Request, admin_id: int,
    accion: AccionAuditoria, detalle: dict,
) -> None:
    """Deja en la bitácora una acción administrativa, con el usuario que la hizo."""
    admin = await RepositorioUsuario(sesion).buscar_por_id(admin_id)
    await RepositorioAuditoria(sesion).registrar(
        accion, user_id=admin_id, username=admin.username if admin else None,
        detalle=detalle, ip=obtener_ip(request), agente=obtener_agente(request),
    )
