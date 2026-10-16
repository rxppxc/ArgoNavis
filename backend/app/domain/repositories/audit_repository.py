from datetime import date

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models.audit_log import RegistroAuditoria, AccionAuditoria


class RepositorioAuditoria:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def registrar(
        self,
        accion: AccionAuditoria,
        *,
        user_id:  int | None  = None,
        username: str | None  = None,
        detalle:  dict | None = None,
        ip:       str | None  = None,
        agente:   str | None  = None,
    ) -> None:
        self.sesion.add(RegistroAuditoria(
            accion=accion, user_id=user_id, username=username,
            detalle=detalle, ip=ip, agente=agente,
        ))

    async def buscar(
        self,
        *,
        accion:  AccionAuditoria | None = None,
        usuario: str | None = None,
        texto:   str | None = None,
        desde:   date | None = None,
        hasta:   date | None = None,
        pagina:  int = 1,
        por_pagina: int = 50,
    ) -> tuple[int, list[RegistroAuditoria]]:
        """Bitácora filtrada y paginada, lo más reciente primero. `texto`
        busca dentro del detalle (JSON) y la IP; las fechas son de Panamá."""
        filtros = []
        if accion:
            filtros.append(RegistroAuditoria.accion == accion)
        if usuario:
            filtros.append(RegistroAuditoria.username.ilike(f"%{usuario}%"))
        if texto:
            patron = f"%{texto}%"
            filtros.append(or_(
                cast(RegistroAuditoria.detalle, String).ilike(patron),
                RegistroAuditoria.ip.ilike(patron),
            ))
        fecha = func.date(func.timezone("America/Panama", RegistroAuditoria.creado_en))
        if desde:
            filtros.append(fecha >= desde)
        if hasta:
            filtros.append(fecha <= hasta)

        total = (await self.sesion.execute(
            select(func.count()).select_from(RegistroAuditoria).where(*filtros)
        )).scalar() or 0

        consulta = (
            select(RegistroAuditoria)
            .where(*filtros)
            .order_by(RegistroAuditoria.creado_en.desc(), RegistroAuditoria.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        return total, list((await self.sesion.execute(consulta)).scalars().all())
