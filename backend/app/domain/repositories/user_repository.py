from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.domain.models.user import Usuario, EstadoUsuario, TipoUsuario


class RepositorioUsuario:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def buscar_por_id(self, user_id: int) -> Usuario | None:
        resultado = await self.sesion.execute(select(Usuario).where(Usuario.id == user_id))
        return resultado.scalar_one_or_none()

    async def buscar_por_nombre_usuario(self, nombre_usuario: str) -> Usuario | None:
        resultado = await self.sesion.execute(select(Usuario).where(Usuario.username == nombre_usuario))
        return resultado.scalar_one_or_none()

    async def buscar_para_login(self, nombre_usuario: str) -> Usuario | None:
        """La cuenta con ese nombre sin distinguir mayúsculas (como el AD), con su
        fila bloqueada (SELECT ... FOR UPDATE) hasta el fin de la transacción:
        los intentos de login con una misma cuenta van de a uno, y el contador
        de fallos no se salta con pedidos en paralelo."""
        nombre = nombre_usuario.strip()
        resultado = await self.sesion.execute(
            select(Usuario)
            .where(func.lower(Usuario.username) == nombre.lower())
            .order_by((Usuario.username == nombre).desc(), Usuario.id)   # si hubiera dos, el exacto
            .limit(1)
            .with_for_update()
        )
        return resultado.scalar_one_or_none()

    async def listar_todos(self) -> list[Usuario]:
        resultado = await self.sesion.execute(
            select(Usuario).order_by(Usuario.name, Usuario.last_name, Usuario.username)
        )
        return list(resultado.scalars().all())

    async def ids_existentes(self, ids: list[int]) -> set[int]:
        if not ids:
            return set()
        resultado = await self.sesion.execute(select(Usuario.id).where(Usuario.id.in_(ids)))
        return {fila[0] for fila in resultado.all()}

    async def contar(self) -> tuple[int, int]:
        """(total de cuentas, cuentas activas)."""
        fila = (await self.sesion.execute(
            select(func.count(), func.count().filter(Usuario.status == EstadoUsuario.ACTIVO))
            .select_from(Usuario)
        )).one()
        return int(fila[0] or 0), int(fila[1] or 0)

    async def crear_desde_ldap(self, datos_ldap: dict) -> Usuario:
        usuario = Usuario(
            username  = datos_ldap["username"],
            name      = datos_ldap.get("name")      or None,
            last_name = datos_ldap.get("last_name") or None,
            email     = datos_ldap.get("email")     or None,
            guid      = datos_ldap.get("guid")      or None,
        )
        self.sesion.add(usuario)
        await self.sesion.flush()
        await self.sesion.refresh(usuario)
        return usuario

    async def crear_local(
        self, username: str, password_hash: str,
        name: str | None, last_name: str | None, email: str | None, rol_id: int | None,
    ) -> Usuario:
        """Alta de una cuenta LOCAL (sin AD). Entra con la contraseña que le
        dio el administrador y el sistema le pide cambiarla."""
        usuario = Usuario(
            username      = username,
            name          = name or None,
            last_name     = last_name or None,
            email         = email or None,
            user_type     = TipoUsuario.LOCAL,
            password_hash = password_hash,
            debe_cambiar_password = True,
            rol_id        = rol_id,
        )
        self.sesion.add(usuario)
        await self.sesion.flush()
        await self.sesion.refresh(usuario)
        return usuario

    async def actualizar_desde_ldap(self, usuario: Usuario, datos_ldap: dict) -> Usuario:
        """Refresca nombre, correo y GUID de una cuenta del AD con lo que dice el AD."""
        usuario.name      = datos_ldap.get("name")      or usuario.name
        usuario.last_name = datos_ldap.get("last_name") or usuario.last_name
        usuario.email     = datos_ldap.get("email")     or usuario.email
        usuario.guid      = datos_ldap.get("guid")      or usuario.guid
        await self.sesion.flush()
        await self.sesion.refresh(usuario)
        return usuario
