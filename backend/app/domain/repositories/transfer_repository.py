from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.domain.models.transfer import Transferencia, ArchivoTransferencia, EstadoTransferencia


class RepositorioTransferencia:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def buscar_por_token(self, token: str) -> Transferencia | None:
        resultado = await self.sesion.execute(
            select(Transferencia)
            .options(
                selectinload(Transferencia.archivos),
                selectinload(Transferencia.usuario),
            )
            .where(Transferencia.token == token)
        )
        return resultado.scalar_one_or_none()

    async def guardar(self, transferencia: Transferencia) -> None:
        await self.sesion.flush()
        await self.sesion.refresh(transferencia, ["archivos", "usuario"])

    async def eliminar_archivo(self, archivo: ArchivoTransferencia) -> None:
        await self.sesion.delete(archivo)
        await self.sesion.flush()

    async def listar_por_usuario(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Transferencia]:
        resultado = await self.sesion.execute(
            select(Transferencia)
            .options(selectinload(Transferencia.archivos))
            .where(Transferencia.user_id == user_id)
            .order_by(Transferencia.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(resultado.scalars().all())

    async def listar_activas(self, limit: int = 500) -> list[Transferencia]:
        """Devuelve TODAS las transferencias activas de todos los usuarios."""
        resultado = await self.sesion.execute(
            select(Transferencia)
            .options(
                selectinload(Transferencia.archivos),
                selectinload(Transferencia.usuario),
            )
            .where(Transferencia.status == EstadoTransferencia.ACTIVA)
            .order_by(Transferencia.created_at.desc())
            .limit(limit)
        )
        return list(resultado.scalars().all())

    async def crear(self, transferencia: Transferencia) -> Transferencia:
        self.sesion.add(transferencia)
        await self.sesion.flush()
        await self.sesion.refresh(transferencia, ["archivos", "usuario"])
        return transferencia

    async def incrementar_descargas(self, token: str) -> None:
        # UPDATE con expresión SQL (downloads = downloads + 1) es atómico en
        # PostgreSQL: ejecuta en una sola declaración a nivel de fila, sin
        # ventana lectura-modificación-escritura — descartar incrementos
        # concurrentes es imposible aquí.
        await self.sesion.execute(
            update(Transferencia)
            .where(Transferencia.token == token)
            .values(downloads=Transferencia.downloads + 1)
        )

    async def eliminar(self, transferencia: Transferencia) -> None:
        await self.sesion.delete(transferencia)
