"""Las cuentas de los usuarios: alta desde el AD o local, contraseña temporal,
estado, rol y baja (auditoría del 2026-11-14; hasta entonces, en api/v1/admin.py,
contra la regla de que las rutas solo orquestan). Las rutas llaman aquí y dejan
la bitácora.

Reglas que viven aquí:
  - el último SysAdmin activo no se desactiva, no se borra ni cambia de rol (409);
  - nadie se desactiva, se borra ni se cambia el rol a sí mismo (400);
  - un usuario con solicitudes no se borra: se desactiva (409, FK RESTRICT);
  - los nombres de usuario son únicos sin distinguir mayúsculas, como el login.
"""
import asyncio
import logging

from fastapi import HTTPException
from ldap3.core.exceptions import LDAPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obtener_configuracion
from app.core.ldap import servicio_ldap
from app.core.permisos import ROL_SYSADMIN
from app.core.security import cerrar_sesiones, generar_contrasena_temporal, hashear_password
from app.domain.models.rol import Rol
from app.domain.models.user import EstadoUsuario, TipoUsuario, Usuario
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.rol import RolMini
from app.domain.schemas.user import DatosCrearUsuarioLocal, SalidaUsuario

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_SIN_AD = "No se pudo conectar al Active Directory."


class ServicioUsuarios:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion
        self.repo = RepositorioUsuario(sesion)

    # ── Ayudas ───────────────────────────────────────────────────────────────

    async def _usuario(self, user_id: int) -> Usuario:
        usuario = await self.repo.buscar_por_id(user_id)
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return usuario

    async def _exigir_rol(self, rol_id: int | None) -> None:
        if rol_id is None:
            return
        if not (await self.sesion.execute(select(Rol).where(Rol.id == rol_id))).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Rol no encontrado.")

    @staticmethod
    def _exigir_cuentas_locales() -> None:
        if not configuracion.PERMITIR_LOGIN_LOCAL:
            raise HTTPException(status_code=403, detail="Las cuentas locales están deshabilitadas (PERMITIR_LOGIN_LOCAL).")

    async def _impedir_quedar_sin_sysadmin(self, usuario: Usuario) -> None:
        """409 si `usuario` es el último SysAdmin activo: TI se quedaría sin su cuenta
        técnica (el primero se asigna con app.infrastructure.asignar_rol)."""
        if not (usuario.rol_personalizado and usuario.rol_personalizado.nombre == ROL_SYSADMIN
                and usuario.status == EstadoUsuario.ACTIVO):
            return
        activos = (await self.sesion.execute(
            select(func.count()).select_from(Usuario).join(Rol, Rol.id == Usuario.rol_id)
            .where(Rol.nombre == ROL_SYSADMIN, Usuario.status == EstadoUsuario.ACTIVO)
        )).scalar() or 0
        if activos <= 1:
            raise HTTPException(
                status_code=409,
                detail="Es el único SysAdmin activo: asigna el rol SysAdmin a otra persona antes de quitárselo.",
            )

    async def salida(self, usuario: Usuario) -> SalidaUsuario:
        """La cuenta con su rol, que un usuario recién creado o cambiado no trae cargado."""
        salida = SalidaUsuario.model_validate(usuario)
        if usuario.rol_id is not None:
            rol = (await self.sesion.execute(select(Rol).where(Rol.id == usuario.rol_id))).scalar_one_or_none()
            if rol:
                salida.rol_personalizado = RolMini.model_validate(rol)
        return salida

    # ── Consultas ────────────────────────────────────────────────────────────

    async def listar(self) -> list[Usuario]:
        return await self.repo.listar_todos()

    @staticmethod
    async def buscar_en_ad(texto: str) -> list:
        try:
            return await asyncio.to_thread(servicio_ldap.buscar_usuarios_ad, texto)
        except LDAPException as e:
            logger.error(f"Error buscando en AD: {e}")
            raise HTTPException(status_code=503, detail=_SIN_AD) from e

    # ── Altas ────────────────────────────────────────────────────────────────

    async def crear_desde_ad(self, nombre_usuario: str) -> Usuario:
        try:
            ldap_usuario = await asyncio.to_thread(servicio_ldap.buscar_usuario, nombre_usuario)
        except LDAPException as e:
            logger.error(f"Error buscando usuario en AD: {e}")
            raise HTTPException(status_code=503, detail=_SIN_AD) from e
        if not ldap_usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado en Active Directory.")
        if await self.repo.nombre_en_uso(ldap_usuario["username"]):
            raise HTTPException(status_code=409, detail="El usuario ya existe en el sistema.")
        return await self.repo.crear_desde_ldap(ldap_usuario)

    async def crear_local(self, datos: DatosCrearUsuarioLocal) -> Usuario:
        """Para usuarios externos, como los de las agencias navieras (PERMITIR_LOGIN_LOCAL).
        Entran con la contraseña que les da el admin y el sistema les pide cambiarla."""
        self._exigir_cuentas_locales()
        if await self.repo.nombre_en_uso(datos.username):
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese nombre (sin distinguir mayúsculas).")
        await self._exigir_rol(datos.rol_id)
        return await self.repo.crear_local(
            username=datos.username,
            password_hash=await asyncio.to_thread(hashear_password, datos.password),   # bcrypt: fuera del bucle de eventos
            name=datos.name, last_name=datos.last_name, email=datos.email,
            rol_id=datos.rol_id,
        )

    # ── Cambios ──────────────────────────────────────────────────────────────

    async def restablecer_contrasena(self, user_id: int) -> tuple[Usuario, str]:
        """Una contraseña temporal para una cuenta local (y la desbloquea). Se muestra
        una sola vez; el usuario debe cambiarla al entrar."""
        self._exigir_cuentas_locales()
        usuario = await self._usuario(user_id)
        if usuario.user_type != TipoUsuario.LOCAL:
            raise HTTPException(status_code=400, detail="Es una cuenta del Active Directory: su contraseña la gestiona TI.")
        temporal = generar_contrasena_temporal()
        usuario.password_hash = await asyncio.to_thread(hashear_password, temporal)
        usuario.debe_cambiar_password = True
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        cerrar_sesiones(usuario)   # quien tuviera la sesión abierta vuelve a entrar con la temporal
        return usuario, temporal

    async def cambiar_estado(self, admin_id: int, user_id: int, estado: EstadoUsuario) -> Usuario:
        if user_id == admin_id and estado != EstadoUsuario.ACTIVO:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
        usuario = await self._usuario(user_id)
        if estado != EstadoUsuario.ACTIVO:
            await self._impedir_quedar_sin_sysadmin(usuario)
            cerrar_sesiones(usuario)   # al reactivarla, los tokens de antes ya no valen
        usuario.status = estado
        await self.sesion.flush()
        await self.sesion.refresh(usuario)
        return usuario

    async def asignar_rol(self, admin_id: int, user_id: int, rol_id: int | None) -> Usuario:
        usuario = await self._usuario(user_id)
        if user_id == admin_id and rol_id != usuario.rol_id:
            # Ni subirse de rol ni quedarse fuera por error: lo cambia otra persona.
            raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol.")
        await self._exigir_rol(rol_id)
        if rol_id != usuario.rol_id:
            await self._impedir_quedar_sin_sysadmin(usuario)
        usuario.rol_id = rol_id
        await self.sesion.flush()
        await self.sesion.refresh(usuario)
        return usuario

    async def eliminar(self, admin_id: int, user_id: int) -> str:
        """Borra la cuenta y devuelve su nombre de usuario (para la bitácora)."""
        if user_id == admin_id:
            raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta.")
        usuario = await self._usuario(user_id)
        await self._impedir_quedar_sin_sysadmin(usuario)
        # Las solicitudes que creó son registros del flujo: la BD impide borrar
        # al usuario (FK RESTRICT). Se desactiva en su lugar.
        if await RepositorioSolicitud(self.sesion).contar_creadas_por(user_id):
            raise HTTPException(
                status_code=409,
                detail="El usuario tiene solicitudes de autorización registradas: desactívalo en lugar de eliminarlo.",
            )
        nombre_usuario = usuario.username
        await self.sesion.delete(usuario)
        return nombre_usuario
