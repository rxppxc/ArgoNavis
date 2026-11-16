"""Los roles y sus permisos (auditoría del 2026-11-14; hasta entonces, en
api/v1/admin.py). Las rutas llaman aquí y dejan la bitácora.

Reglas que viven aquí:
  - los permisos son de solo lectura: los siembran las migraciones y el código
    revisa esos códigos (T-CREAR-BASICA, T-PROCESAR-PACIFICO…);
  - Administrador y SysAdmin no se renombran (los permisos de administración se
    resuelven por esos nombres) y sus permisos son fijos;
  - un rol del sistema no se borra.
"""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permisos import ROL_ADMIN, ROL_SYSADMIN
from app.domain.models.rol import Permiso, Rol, RolPermiso
from app.domain.models.user import Usuario
from app.domain.schemas.rol import DatosActualizarRol, DatosCrearRol, SalidaPermiso, SalidaRol


class ServicioRoles:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def _rol(self, rol_id: int) -> Rol:
        rol = (await self.sesion.execute(select(Rol).where(Rol.id == rol_id))).scalar_one_or_none()
        if not rol:
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
        return rol

    async def salida(self, rol: Rol) -> SalidaRol:
        permisos_q = await self.sesion.execute(
            select(Permiso)
            .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
            .where(RolPermiso.rol_id == rol.id)
            .order_by(Permiso.codigo)
        )
        permisos = [SalidaPermiso.model_validate(p) for p in permisos_q.scalars().all()]
        total_usuarios = (await self.sesion.execute(
            select(func.count()).select_from(Usuario).where(Usuario.rol_id == rol.id)
        )).scalar() or 0
        # Se arma a mano: model_validate(rol) intentaría leer rol.permisos
        # (relación a RolPermiso, no a SalidaPermiso) y revienta.
        return SalidaRol(
            id=rol.id,
            nombre=rol.nombre,
            descripcion=rol.descripcion,
            es_sistema=rol.es_sistema,
            created_at=rol.created_at,
            permisos=permisos,
            total_usuarios=total_usuarios,
        )

    async def listar_permisos(self) -> list[Permiso]:
        return list((await self.sesion.execute(select(Permiso).order_by(Permiso.codigo))).scalars().all())

    async def listar(self) -> list[SalidaRol]:
        roles = (await self.sesion.execute(select(Rol).order_by(Rol.nombre))).scalars().all()
        return [await self.salida(r) for r in roles]

    async def crear(self, datos: DatosCrearRol) -> Rol:
        if (await self.sesion.execute(select(Rol).where(Rol.nombre == datos.nombre))).scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre.")
        rol = Rol(nombre=datos.nombre, descripcion=datos.descripcion, es_sistema=False)
        self.sesion.add(rol)
        await self.sesion.flush()
        await self.sesion.refresh(rol)
        return rol

    async def actualizar(self, rol_id: int, datos: DatosActualizarRol) -> Rol:
        rol = await self._rol(rol_id)
        if datos.nombre is not None:
            nuevo_nombre = datos.nombre.strip()
            if not nuevo_nombre:
                raise HTTPException(status_code=400, detail="El nombre no puede estar vacío.")
            if nuevo_nombre != rol.nombre and rol.nombre in (ROL_ADMIN, ROL_SYSADMIN):
                # Los permisos de administración se resuelven por estos nombres.
                raise HTTPException(status_code=400, detail=f"El rol {rol.nombre} no se puede renombrar.")
            if nuevo_nombre != rol.nombre:
                dup = await self.sesion.execute(select(Rol).where(Rol.nombre == nuevo_nombre, Rol.id != rol_id))
                if dup.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="Ya existe otro rol con ese nombre.")
                rol.nombre = nuevo_nombre
        if datos.descripcion is not None:
            rol.descripcion = datos.descripcion
        await self.sesion.flush()
        await self.sesion.refresh(rol)
        return rol

    async def eliminar(self, rol_id: int) -> str:
        """Borra el rol y devuelve su nombre (para la bitácora)."""
        rol = await self._rol(rol_id)
        if rol.es_sistema:
            raise HTTPException(status_code=400, detail="No se puede eliminar un rol del sistema.")
        nombre = rol.nombre
        await self.sesion.delete(rol)
        return nombre

    async def asignar_permisos(self, rol_id: int, permiso_ids: list[int]) -> SalidaRol:
        """Reemplaza los permisos del rol (sincronización total)."""
        rol = await self._rol(rol_id)
        if rol.nombre in (ROL_ADMIN, ROL_SYSADMIN):
            # El Administrador ya tiene todo por su nombre (el atajo) y el SysAdmin no
            # lleva permisos del flujo: con uno T-* vería solicitudes.
            raise HTTPException(status_code=400, detail=f"Los permisos del rol {rol.nombre} son fijos.")
        ids_unicos = list(set(permiso_ids))
        if ids_unicos:
            validos = await self.sesion.execute(select(Permiso.id).where(Permiso.id.in_(ids_unicos)))
            invalidos = set(ids_unicos) - {fila[0] for fila in validos.all()}
            if invalidos:
                raise HTTPException(status_code=400, detail=f"Permisos no encontrados: {sorted(invalidos)}")
        actuales = await self.sesion.execute(select(RolPermiso).where(RolPermiso.rol_id == rol_id))
        for rp in actuales.scalars().all():
            await self.sesion.delete(rp)
        await self.sesion.flush()
        for pid in ids_unicos:
            self.sesion.add(RolPermiso(rol_id=rol_id, permiso_id=pid))
        await self.sesion.flush()
        return await self.salida(rol)
