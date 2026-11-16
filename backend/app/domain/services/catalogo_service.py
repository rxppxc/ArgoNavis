"""Los catálogos del flujo: puestos de control, sectores de UCVMM, agencias navieras
y nacionalidades restringidas (auditoría del 2026-11-14; hasta entonces, las reglas
estaban en api/v1/catalogos.py). Las rutas llaman aquí, arman la salida y dejan la
bitácora.

Reglas que viven aquí:
  - los nombres de puestos y agencias son únicos (409);
  - un puesto o una agencia con solicitudes no se borra: se desactiva (409);
  - el sector de un puesto tiene que existir; mover el puesto mueve sus solicitudes;
  - los usuarios que se asignan tienen que existir. Asignarlos no les da acceso sin
    el permiso de su rol (ContextoAcceso exige las dos cosas).
"""
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.catalogo import AgenciaNaviera, Pais, PuestoControl, Sector
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.catalogo import (
    DatosActualizarAgencia, DatosActualizarPuesto, DatosCrearAgencia, DatosCrearPuesto,
)

Entidad = PuestoControl | AgenciaNaviera


class ServicioCatalogos:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion
        self.repo = RepositorioCatalogo(sesion)

    # ── Ayudas ───────────────────────────────────────────────────────────────

    async def _sector_existente(self, sector_id: int) -> Sector:
        sector = await self.repo.buscar_sector(sector_id)
        if not sector:
            raise HTTPException(status_code=400, detail="El sector elegido no existe.")
        return sector

    @staticmethod
    async def _aplicar_cambios(
        entidad: Entidad,
        datos: DatosActualizarPuesto | DatosActualizarAgencia,
        buscar_por_nombre: Callable[[str], Awaitable[Entidad | None]],
        duplicado: str,
    ) -> dict:
        """Aplica nombre/correo/activo y devuelve lo que cambió (para la bitácora)."""
        cambios: dict = {}
        if datos.nombre is not None and datos.nombre != entidad.nombre:
            otro = await buscar_por_nombre(datos.nombre)
            if otro and otro.id != entidad.id:
                raise HTTPException(status_code=409, detail=duplicado)
            cambios["nombre"] = entidad.nombre = datos.nombre
        if "correo" in datos.model_fields_set and datos.correo != entidad.correo:
            cambios["correo"] = entidad.correo = datos.correo
        if datos.activo is not None and datos.activo != entidad.activo:
            cambios["activo"] = entidad.activo = datos.activo
        return cambios

    async def _validar_usuarios(self, usuario_ids: list[int]) -> list[int]:
        ids = sorted(set(usuario_ids))
        faltan = set(ids) - await RepositorioUsuario(self.sesion).ids_existentes(ids)
        if faltan:
            raise HTTPException(status_code=400, detail=f"Usuarios no encontrados: {sorted(faltan)}.")
        return ids

    # ── Puestos de control ───────────────────────────────────────────────────

    async def puesto(self, puesto_id: int, *, con_usuarios: bool = False) -> PuestoControl:
        puesto = await self.repo.buscar_puesto(puesto_id, con_usuarios=con_usuarios)
        if not puesto:
            raise HTTPException(status_code=404, detail="Puesto de control no encontrado.")
        return puesto

    async def crear_puesto(self, datos: DatosCrearPuesto) -> PuestoControl:
        if await self.repo.buscar_puesto_por_nombre(datos.nombre):
            raise HTTPException(status_code=409, detail="Ya existe un puesto de control con ese nombre.")
        sector = await self._sector_existente(datos.sector_id)
        # Con el objeto (no el id): así `puesto.sector` queda cargado para la respuesta.
        puesto = PuestoControl(nombre=datos.nombre, correo=datos.correo, activo=True, sector=sector)
        self.repo.agregar(puesto)
        await self.sesion.flush()
        return puesto

    async def actualizar_puesto(self, puesto_id: int, datos: DatosActualizarPuesto) -> tuple[PuestoControl, dict]:
        """El puesto y lo que cambió."""
        puesto = await self.puesto(puesto_id, con_usuarios=True)
        cambios = await self._aplicar_cambios(
            puesto, datos, self.repo.buscar_puesto_por_nombre, "Ya existe otro puesto de control con ese nombre.",
        )
        if datos.sector_id is not None and datos.sector_id != puesto.sector_id:
            # Sus solicitudes, también las abiertas, pasan a los revisores del otro sector.
            sector = await self._sector_existente(datos.sector_id)
            puesto.sector = sector
            cambios["sector"] = sector.nombre
        await self.sesion.flush()
        return puesto, cambios

    async def eliminar_puesto(self, puesto_id: int) -> PuestoControl:
        puesto = await self.puesto(puesto_id)
        if await self.repo.puesto_en_uso(puesto_id):
            raise HTTPException(
                status_code=409,
                detail="El puesto tiene solicitudes registradas (autorizadas o finalizadas en él): "
                       "desactívalo en lugar de eliminarlo.",
            )
        await self.repo.eliminar(puesto)
        return puesto

    async def asignar_usuarios_puesto(self, puesto_id: int, usuario_ids: list[int]) -> tuple[PuestoControl, list[int]]:
        """Reemplaza la lista de funcionarios asignados al puesto."""
        puesto = await self.puesto(puesto_id)
        ids = await self._validar_usuarios(usuario_ids)
        await self.repo.reemplazar_usuarios_de_puesto(puesto_id, ids)
        return puesto, ids

    # ── Sectores de UCVMM ────────────────────────────────────────────────────

    async def sector(self, sector_id: int, *, con_usuarios: bool = False) -> Sector:
        sector = await self.repo.buscar_sector(sector_id, con_usuarios=con_usuarios)
        if not sector:
            raise HTTPException(status_code=404, detail="Sector no encontrado.")
        return sector

    async def cambiar_correo_sector(self, sector_id: int, correo: str | None) -> tuple[Sector, bool]:
        """El sector y si cambió su buzón."""
        sector = await self.sector(sector_id, con_usuarios=True)
        if correo == sector.correo:
            return sector, False
        sector.correo = correo
        await self.sesion.flush()
        return sector, True

    async def asignar_usuarios_sector(self, sector_id: int, usuario_ids: list[int]) -> tuple[Sector, list[int]]:
        """Reemplaza los funcionarios del sector. Un revisor puede estar en los dos
        (vacaciones, refuerzos): ve las solicitudes de los puestos de ambos."""
        sector = await self.sector(sector_id)
        ids = await self._validar_usuarios(usuario_ids)
        await self.repo.reemplazar_usuarios_de_sector(sector_id, ids)
        return sector, ids

    # ── Agencias navieras ────────────────────────────────────────────────────

    async def agencia(self, agencia_id: int, *, con_usuarios: bool = False) -> AgenciaNaviera:
        agencia = await self.repo.buscar_agencia(agencia_id, con_usuarios=con_usuarios)
        if not agencia:
            raise HTTPException(status_code=404, detail="Agencia naviera no encontrada.")
        return agencia

    async def crear_agencia(self, datos: DatosCrearAgencia) -> AgenciaNaviera:
        if await self.repo.buscar_agencia_por_nombre(datos.nombre):
            raise HTTPException(status_code=409, detail="Ya existe una agencia naviera con ese nombre.")
        agencia = AgenciaNaviera(nombre=datos.nombre, correo=datos.correo, activo=True)
        self.repo.agregar(agencia)
        await self.sesion.flush()
        return agencia

    async def actualizar_agencia(self, agencia_id: int, datos: DatosActualizarAgencia) -> tuple[AgenciaNaviera, dict]:
        """Nombre, buzón y estado. Las solicitudes ya enviadas conservan el nombre
        que tenía la agencia al enviarlas. Una agencia inactiva no envía nuevas."""
        agencia = await self.agencia(agencia_id, con_usuarios=True)
        cambios = await self._aplicar_cambios(
            agencia, datos, self.repo.buscar_agencia_por_nombre, "Ya existe otra agencia naviera con ese nombre.",
        )
        await self.sesion.flush()
        return agencia, cambios

    async def eliminar_agencia(self, agencia_id: int) -> AgenciaNaviera:
        """Solo una agencia sin solicitudes; sus usuarios quedan sin agencia."""
        agencia = await self.agencia(agencia_id)
        if (await self.repo.contar_solicitudes_por_agencia()).get(agencia_id):
            raise HTTPException(
                status_code=409,
                detail="La agencia tiene solicitudes registradas: desactívala en lugar de eliminarla.",
            )
        await self.repo.eliminar(agencia)
        return agencia

    async def asignar_usuarios_agencia(self, agencia_id: int, usuario_ids: list[int]) -> list[int]:
        """Reemplaza los usuarios de la agencia. Un usuario es de una sola agencia:
        asignarlo aquí lo saca de la que tuviera."""
        await self.agencia(agencia_id)
        ids = await self._validar_usuarios(usuario_ids)
        await self.repo.reemplazar_usuarios_de_agencia(agencia_id, ids)
        return ids

    # ── Países ───────────────────────────────────────────────────────────────

    async def marcar_restringida(self, codigo: str, restringida: bool) -> tuple[Pais, bool]:
        """Marca o desmarca una nacionalidad como restringida; devuelve el país y si
        cambió. Aplica a las solicitudes que se envíen desde ahora (las ya enviadas
        guardan su foto)."""
        pais = await self.repo.buscar_pais(codigo)
        if not pais:
            raise HTTPException(status_code=404, detail="País no encontrado.")
        if pais.nacionalidad_restringida == restringida:
            return pais, False
        pais.nacionalidad_restringida = restringida
        await self.sesion.flush()
        return pais, True
