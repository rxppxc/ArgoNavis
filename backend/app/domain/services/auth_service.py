"""Inicio de sesión: Active Directory o cuenta local.

  - Cuentas AD: la contraseña y su política viven en el Active Directory. Solo
    se le consulta por cuentas del AD registradas y activas en ARGO NAVIS, y se deja
    de hacerlo un rato tras LOGIN_AD_MAX_FALLOS fallos seguidos: desde ARGO NAVIS (al
    que las agencias entran por la VPN) no se pueden probar contraseñas del
    dominio ni bloquearle la cuenta a un funcionario.
  - Cuentas locales (PERMITIR_LOGIN_LOCAL): las de usuarios externos, como las
    agencias navieras. Contraseña propia (bcrypt) con la política de
    `problema_de_contrasena`, bloqueo temporal tras LOGIN_MAX_INTENTOS fallos
    seguidos y cambio obligatorio cuando el admin la crea o la restablece, o
    cuando la que tiene ya no cumple la política.
  - Un usuario de una agencia desactivada no entra (ni sigue con la sesión abierta).

Los errores se lanzan como HTTPException; el endpoint los convierte en
respuesta sin propagar la excepción, para que el contador de intentos y la
bitácora sí se guarden.
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from ldap3.core.exceptions import LDAPException

from app.core.config import obtener_configuracion
from app.core.ldap import servicio_ldap
from app.core.security import (
    AGENCIA_DESACTIVADA, cerrar_sesiones, crear_token_acceso, hashear_password, verificar_password,
)
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.user import EstadoUsuario, TipoUsuario, Usuario
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.user import RespuestaToken, SalidaUsuario, problema_de_contrasena

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."
_CUENTA_DESHABILITADA   = "Tu cuenta está deshabilitada. Contacta al administrador de TI."


def _error(codigo: int, detalle: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=detalle)


class ErrorAcceso(HTTPException):
    """Credenciales rechazadas. Al usuario le llega el mensaje genérico (no
    revela si la cuenta existe en el AD); la bitácora guarda el `motivo` real."""

    def __init__(self, motivo: str, *, codigo: int = status.HTTP_401_UNAUTHORIZED,
                 detalle: str = _CREDENCIALES_INVALIDAS):
        super().__init__(status_code=codigo, detail=detalle)
        self.motivo = motivo



def _frenado(falta: timedelta, motivo: str) -> ErrorAcceso:
    """Login de una cuenta del AD frenado por intentos fallidos."""
    minutos = max(1, math.ceil(falta.total_seconds() / 60))
    return ErrorAcceso(
        motivo, codigo=status.HTTP_429_TOO_MANY_REQUESTS,
        detalle=f"Demasiados intentos fallidos. Por seguridad, espera {minutos} minuto(s) e intenta de nuevo.",
    )


class ServicioAutenticacion:
    def __init__(self, repo_usuario: RepositorioUsuario, repo_auditoria: RepositorioAuditoria):
        self.repo_usuario   = repo_usuario
        self.repo_auditoria = repo_auditoria

    @staticmethod
    def _respuesta(usuario: Usuario) -> RespuestaToken:
        token = crear_token_acceso(subject=usuario.id, extra={"username": usuario.username})
        return RespuestaToken(access_token=token, user=SalidaUsuario.model_validate(usuario))

    async def login(self, nombre_usuario: str, contrasena: str) -> RespuestaToken:
        # Con la fila bloqueada: los intentos con una misma cuenta van de a uno.
        usuario = await self.repo_usuario.buscar_para_login(nombre_usuario)
        if usuario and usuario.user_type == TipoUsuario.LOCAL and configuracion.PERMITIR_LOGIN_LOCAL:
            return await self._login_local(usuario, contrasena)
        return await self._login_ad(usuario, contrasena)

    # ── Cuenta local ─────────────────────────────────────────────────────────

    async def _login_local(self, usuario: Usuario, contrasena: str) -> RespuestaToken:
        ahora = datetime.now(timezone.utc)
        if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
            minutos = math.ceil((usuario.bloqueado_hasta - ahora).total_seconds() / 60)
            raise _error(
                status.HTTP_423_LOCKED,
                f"La cuenta está bloqueada por intentos fallidos. Intenta de nuevo en {minutos} minuto(s) "
                "o pide al administrador que restablezca tu contraseña.",
            )

        if not usuario.password_hash or not verificar_password(contrasena, usuario.password_hash):
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
            if usuario.intentos_fallidos >= configuracion.LOGIN_MAX_INTENTOS:
                usuario.intentos_fallidos = 0
                usuario.bloqueado_hasta = ahora + timedelta(minutes=configuracion.LOGIN_MINUTOS_BLOQUEO)
                await self.repo_auditoria.registrar(
                    AccionAuditoria.CUENTA_BLOQUEADA,
                    user_id=usuario.id, username=usuario.username,
                    detalle={"minutos": configuracion.LOGIN_MINUTOS_BLOQUEO},
                )
                raise _error(
                    status.HTTP_423_LOCKED,
                    f"Demasiados intentos fallidos: la cuenta quedó bloqueada {configuracion.LOGIN_MINUTOS_BLOQUEO} minutos.",
                )
            raise ErrorAcceso("Contraseña incorrecta (cuenta local).")

        if usuario.status != EstadoUsuario.ACTIVO:
            raise _error(status.HTTP_403_FORBIDDEN, _CUENTA_DESHABILITADA)
        self._exigir_agencia_activa(usuario)

        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        if problema_de_contrasena(contrasena, usuario.username):
            # La política subió (2026-10-16): quien entra con una contraseña que
            # ya no la cumple tiene que cambiarla antes de seguir.
            usuario.debe_cambiar_password = True
        return self._respuesta(usuario)

    @staticmethod
    def _exigir_agencia_activa(usuario: Usuario) -> None:
        """Solo tras verificar la contraseña: no revela nada a quien no la sabe."""
        if usuario.agencia is not None and not usuario.agencia.activo:
            raise _error(status.HTTP_403_FORBIDDEN, AGENCIA_DESACTIVADA)

    async def cambiar_contrasena(self, usuario: Usuario, actual: str, nueva: str) -> RespuestaToken:
        """Cambio de la propia contraseña (solo cuentas locales). Invalida los
        tokens anteriores de la cuenta y devuelve uno nuevo para seguir."""
        if usuario.user_type != TipoUsuario.LOCAL:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "Tu cuenta es del Active Directory: la contraseña se cambia en Windows o con TI.",
            )
        if not usuario.password_hash or not verificar_password(actual, usuario.password_hash):
            raise _error(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta.")
        if actual == nueva:
            raise _error(status.HTTP_400_BAD_REQUEST, "La contraseña nueva debe ser distinta de la actual.")
        problema = problema_de_contrasena(nueva, usuario.username)
        if problema:
            raise _error(status.HTTP_400_BAD_REQUEST, problema)
        usuario.password_hash = hashear_password(nueva)
        usuario.debe_cambiar_password = False
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        cerrar_sesiones(usuario)
        return self._respuesta(usuario)

    # ── Active Directory ─────────────────────────────────────────────────────

    async def _login_ad(self, usuario: Usuario | None, contrasena: str) -> RespuestaToken:
        # Al AD solo se le pregunta por cuentas del AD registradas y activas en
        # ARGO NAVIS. Por cualquier otro nombre se responde lo mismo sin tocar el
        # dominio: si no, ARGO NAVIS serviría para probar contraseñas de cualquier
        # cuenta del SNM (con la correcta respondía "no tienes acceso") y para
        # bloquearlas.
        if usuario is None:
            raise ErrorAcceso("Usuario no registrado en ARGO NAVIS: no se consultó el AD.")
        if usuario.user_type != TipoUsuario.AD:
            raise ErrorAcceso("Cuenta local con el login local deshabilitado: no se consultó el AD.")
        if usuario.status != EstadoUsuario.ACTIVO:
            raise ErrorAcceso("Cuenta desactivada: no se consultó el AD.")

        ahora = datetime.now(timezone.utc)
        if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
            raise _frenado(usuario.bloqueado_hasta - ahora, "Freno por intentos fallidos: no se consultó el AD.")

        try:
            ldap_usuario = await self._verificar_en_ad(usuario.username, contrasena)
        except ErrorAcceso as error:
            # Freno por debajo del umbral de bloqueo del dominio (ver
            # LOGIN_AD_MAX_FALLOS en core/config.py).
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
            if usuario.intentos_fallidos < configuracion.LOGIN_AD_MAX_FALLOS:
                raise
            espera = timedelta(minutes=configuracion.LOGIN_AD_MINUTOS_ESPERA)
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = ahora + espera
            await self.repo_auditoria.registrar(
                AccionAuditoria.CUENTA_BLOQUEADA,
                user_id=usuario.id, username=usuario.username,
                detalle={"minutos": configuracion.LOGIN_AD_MINUTOS_ESPERA, "origen": "ad"},
            )
            raise _frenado(espera, error.motivo) from error

        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        self._exigir_agencia_activa(usuario)
        await self.repo_usuario.actualizar_desde_ldap(usuario, ldap_usuario)
        return self._respuesta(usuario)

    async def _verificar_en_ad(self, nombre_usuario: str, contrasena: str) -> dict:
        """Los datos del AD de la cuenta, si el AD acepta la contraseña."""
        # 1. Buscar en Active Directory
        try:
            ldap_usuario = await asyncio.to_thread(servicio_ldap.buscar_usuario, nombre_usuario)
        except LDAPException as e:
            logger.error(f"Error de conexión con Active Directory: {e}")
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "No se pudo conectar al servidor de Active Directory. Verifica tu conexión de red.",
            )

        if not ldap_usuario:
            raise ErrorAcceso("Usuario no encontrado en Active Directory.")

        # 2. Verificar contraseña contra AD
        try:
            autenticado = await asyncio.to_thread(servicio_ldap.autenticar, ldap_usuario["dn"], contrasena)
        except Exception as e:
            logger.error(f"Error inesperado al verificar credenciales LDAP: {e}", exc_info=True)
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Error al verificar credenciales. Inténtalo de nuevo.")
        if not autenticado:
            raise ErrorAcceso("Contraseña incorrecta (Active Directory).")
        return ldap_usuario
