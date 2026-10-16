from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.tramite import TipoTramite, TramiteDocumento


class RepositorioTramite:
    """Acceso (de lectura) al catálogo de trámites y documentos requeridos.
    El catálogo se ajusta con migraciones; su edición desde la UI está pendiente."""

    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    def _consulta_tipos(self):
        return select(TipoTramite).options(
            selectinload(TipoTramite.documentos).selectinload(TramiteDocumento.documento)
        )

    async def listar_tipos(self, *, solo_activos: bool = True) -> list[TipoTramite]:
        consulta = self._consulta_tipos().order_by(TipoTramite.orden, TipoTramite.nombre)
        if solo_activos:
            consulta = consulta.where(TipoTramite.activo.is_(True))
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def buscar_tipo_por_id(self, tipo_id: int) -> TipoTramite | None:
        consulta = self._consulta_tipos().where(TipoTramite.id == tipo_id)
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def buscar_tipo_por_codigo(self, codigo: str) -> TipoTramite | None:
        consulta = self._consulta_tipos().where(TipoTramite.codigo == codigo)
        return (await self.sesion.execute(consulta)).scalar_one_or_none()
