"""Consulta de la bitácora (audit_logs) — solo administradores."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permisos import requerir_admin_o_sysadmin
from app.domain.models.audit_log import AccionAuditoria
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.schemas.auditoria import SalidaBitacora, SalidaRegistroAuditoria
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(prefix="/admin/bitacora", tags=["admin"])


@enrutador.get("", response_model=SalidaBitacora)
async def consultar_bitacora(
    accion:     AccionAuditoria | None = Query(default=None),
    usuario:    str | None = Query(default=None, max_length=100),
    texto:      str | None = Query(default=None, max_length=200),
    desde:      date | None = Query(default=None),
    hasta:      date | None = Query(default=None),
    pagina:     int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=10, le=200),
    _admin:     int = Depends(requerir_admin_o_sysadmin),
    sesion:     AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    total, registros = await RepositorioAuditoria(sesion).buscar(
        accion=accion,
        usuario=usuario.strip() if usuario and usuario.strip() else None,
        texto=texto.strip() if texto and texto.strip() else None,
        desde=desde, hasta=hasta, pagina=pagina, por_pagina=por_pagina,
    )
    return SalidaBitacora(
        total=total, pagina=pagina, por_pagina=por_pagina,
        items=[
            SalidaRegistroAuditoria(
                id=r.id, creado_en=r.creado_en, accion=r.accion.value,
                user_id=r.user_id, username=r.username, detalle=r.detalle, ip=r.ip,
            )
            for r in registros
        ],
    )


@enrutador.get("/acciones", response_model=list[str])
async def listar_acciones(_admin: int = Depends(requerir_admin_o_sysadmin)):
    """Acciones posibles, para el filtro de la bitácora."""
    return [a.value for a in AccionAuditoria]
