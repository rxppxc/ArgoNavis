from dataclasses import asdict
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import Aviso
from app.domain.models.correo import CorreoSalida, EstadoCorreo


class RepositorioCorreo:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def agregar(self, aviso: Aviso) -> None:
        self.sesion.add(CorreoSalida(numero=aviso.numero[:20], asunto=aviso.asunto[:300], aviso=asdict(aviso)))

    async def tomar_pendiente(self) -> CorreoSalida | None:
        """El pendiente que ya toca, el más antiguo primero, bloqueado hasta el
        fin de la transacción. SKIP LOCKED: si otro worker lo está enviando,
        devuelve el siguiente, y ninguno se envía dos veces."""
        return (await self.sesion.execute(
            select(CorreoSalida)
            .where(CorreoSalida.estado == EstadoCorreo.PENDIENTE.value, CorreoSalida.proximo_intento <= func.now())
            .order_by(CorreoSalida.proximo_intento, CorreoSalida.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()

    async def borrar_terminados(self, antes_de: datetime) -> int:
        """Borra los enviados y fallidos creados antes de `antes_de` (los pendientes, nunca)."""
        resultado = await self.sesion.execute(
            delete(CorreoSalida).where(
                CorreoSalida.estado != EstadoCorreo.PENDIENTE.value, CorreoSalida.creado_en < antes_de,
            )
        )
        return resultado.rowcount or 0
