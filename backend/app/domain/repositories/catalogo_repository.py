from sqlalchemy import delete, exists, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.catalogo import AgenciaNaviera, Pais, PuestoControl, usuarios_puestos
from app.domain.models.solicitud import Solicitud
from app.domain.models.user import EstadoUsuario, Usuario


class RepositorioCatalogo:
    """Puestos de control, agencias navieras (con sus usuarios) y países."""

    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    # ── Puestos de control ───────────────────────────────────────────────────

    async def listar_puestos(self, *, solo_activos: bool = False, con_usuarios: bool = False) -> list[PuestoControl]:
        consulta = select(PuestoControl).order_by(PuestoControl.nombre)
        if solo_activos:
            consulta = consulta.where(PuestoControl.activo.is_(True))
        if con_usuarios:
            consulta = consulta.options(selectinload(PuestoControl.usuarios))
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def buscar_puesto(self, puesto_id: int, *, con_usuarios: bool = False) -> PuestoControl | None:
        consulta = select(PuestoControl).where(PuestoControl.id == puesto_id)
        if con_usuarios:
            consulta = consulta.options(selectinload(PuestoControl.usuarios))
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def buscar_puesto_por_nombre(self, nombre: str) -> PuestoControl | None:
        consulta = select(PuestoControl).where(func.lower(PuestoControl.nombre) == nombre.lower())
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def contar_solicitudes_por_puesto(self) -> dict[int, int]:
        consulta = select(Solicitud.puesto_control_id, func.count()).group_by(Solicitud.puesto_control_id)
        return {pid: total for pid, total in (await self.sesion.execute(consulta)).all()}

    async def puesto_en_uso(self, puesto_id: int) -> bool:
        """Si alguna solicitud lo tiene como puesto autorizado o como puesto
        donde se finalizó (las dos llaves impiden borrarlo)."""
        consulta = select(exists().where(or_(
            Solicitud.puesto_control_id == puesto_id,
            Solicitud.puesto_finalizacion_id == puesto_id,
        )))
        return bool((await self.sesion.execute(consulta)).scalar())

    async def puestos_de_usuario(self, usuario_id: int) -> set[int]:
        consulta = select(usuarios_puestos.c.puesto_id).where(usuarios_puestos.c.usuario_id == usuario_id)
        return {fila[0] for fila in (await self.sesion.execute(consulta)).all()}

    async def correos_de_puesto(self, puesto_id: int) -> list[str]:
        """Correo de los funcionarios activos asignados al puesto."""
        consulta = (
            select(Usuario.email)
            .join(usuarios_puestos, usuarios_puestos.c.usuario_id == Usuario.id)
            .where(
                usuarios_puestos.c.puesto_id == puesto_id,
                Usuario.status == EstadoUsuario.ACTIVO,
                Usuario.email.isnot(None),
            )
        )
        return [fila[0] for fila in (await self.sesion.execute(consulta)).all() if fila[0]]

    async def reemplazar_usuarios_de_puesto(self, puesto_id: int, usuario_ids: list[int]) -> None:
        await self.sesion.execute(delete(usuarios_puestos).where(usuarios_puestos.c.puesto_id == puesto_id))
        if usuario_ids:
            await self.sesion.execute(
                insert(usuarios_puestos),
                [{"usuario_id": uid, "puesto_id": puesto_id} for uid in usuario_ids],
            )

    def agregar(self, entidad: PuestoControl | AgenciaNaviera) -> None:
        self.sesion.add(entidad)

    async def eliminar(self, entidad: PuestoControl | AgenciaNaviera) -> None:
        await self.sesion.delete(entidad)

    # ── Agencias navieras ────────────────────────────────────────────────────

    async def listar_agencias(self, *, con_usuarios: bool = False) -> list[AgenciaNaviera]:
        consulta = select(AgenciaNaviera).order_by(AgenciaNaviera.nombre)
        if con_usuarios:
            consulta = consulta.options(selectinload(AgenciaNaviera.usuarios))
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def buscar_agencia(self, agencia_id: int, *, con_usuarios: bool = False) -> AgenciaNaviera | None:
        consulta = select(AgenciaNaviera).where(AgenciaNaviera.id == agencia_id)
        if con_usuarios:
            consulta = consulta.options(selectinload(AgenciaNaviera.usuarios))
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def buscar_agencia_por_nombre(self, nombre: str) -> AgenciaNaviera | None:
        consulta = select(AgenciaNaviera).where(func.lower(AgenciaNaviera.nombre) == nombre.lower())
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def contar_agencias(self) -> int:
        return (await self.sesion.execute(select(func.count()).select_from(AgenciaNaviera))).scalar() or 0

    async def contar_solicitudes_por_agencia(self) -> dict[int, int]:
        consulta = select(Solicitud.agencia_id, func.count()).group_by(Solicitud.agencia_id)
        return {aid: total for aid, total in (await self.sesion.execute(consulta)).all()}

    async def correos_de_agencia(self, agencia_id: int) -> list[str]:
        """Correo de los usuarios activos de la agencia."""
        consulta = select(Usuario.email).where(
            Usuario.agencia_id == agencia_id,
            Usuario.status == EstadoUsuario.ACTIVO,
            Usuario.email.isnot(None),
        )
        return [fila[0] for fila in (await self.sesion.execute(consulta)).all() if fila[0]]

    async def reemplazar_usuarios_de_agencia(self, agencia_id: int, usuario_ids: list[int]) -> None:
        """Deja en la agencia exactamente a esos usuarios (un usuario pertenece
        a una sola agencia: asignarlo aquí lo saca de la que tuviera)."""
        await self.sesion.execute(
            update(Usuario).where(Usuario.agencia_id == agencia_id).values(agencia_id=None)
        )
        if usuario_ids:
            await self.sesion.execute(
                update(Usuario).where(Usuario.id.in_(usuario_ids)).values(agencia_id=agencia_id)
            )

    # ── Países ───────────────────────────────────────────────────────────────

    async def listar_paises(self) -> list[Pais]:
        consulta = select(Pais).order_by(Pais.nombre)
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def paises_por_codigo(self, codigos: set[str]) -> dict[str, Pais]:
        if not codigos:
            return {}
        consulta = select(Pais).where(Pais.codigo.in_(codigos))
        return {p.codigo: p for p in (await self.sesion.execute(consulta)).scalars().all()}

    async def buscar_pais(self, codigo: str) -> Pais | None:
        consulta = select(Pais).where(Pais.codigo == codigo.upper())
        return (await self.sesion.execute(consulta)).scalar_one_or_none()
