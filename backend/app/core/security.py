"""Capa de seguridad: emisión y verificación de tokens JWT.

El verificador `obtener_id_usuario_actual` hace una validación de BD en cada
request para que los cambios de estado del usuario (desactivado, rol revocado,
borrado) tengan efecto inmediato y no esperen al vencimiento del token.

Cerrar sesión, cambiar la contraseña o que el SysAdmin la restablezca invalida
los tokens ya emitidos (`users.sesiones_validas_desde` contra el `iat` del
token). Cada token lleva además el inicio de la sesión (`ini`): /auth/refresh
no renueva pasadas SESION_MAXIMA_HORAS.

Si esto se vuelve un problema de rendimiento se puede pasar a una caché corta
(Redis, 30-60s) o a una lista de revocación, pero por defecto preferimos
seguridad sobre micro-optimización.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import obtener_configuracion
from app.infrastructure.database import obtener_sesion_bd
from app.domain.models.catalogo import AgenciaNaviera
from app.domain.models.user import Usuario, EstadoUsuario
from app.domain.schemas.user import problema_de_contrasena

configuracion  = obtener_configuracion()
esquema_bearer = HTTPBearer(auto_error=True)

# Rutas que una cuenta con cambio de contraseña pendiente sí puede usar: ver su
# perfil y permisos, cambiar la contraseña y cerrar la sesión.
_RUTAS_CON_CAMBIO_PENDIENTE = {
    "/api/v1/auth/me", "/api/v1/auth/me/permisos", "/api/v1/auth/cambiar-contrasena",
    "/api/v1/auth/logout", "/api/v1/auth/session-expired", "/api/v1/auth/refresh",
}
# Cabecera con la que el frontend reconoce el 403 de "cambia tu contraseña".
CABECERA_CAMBIO_CONTRASENA = "X-Cambio-Contrasena"


# Solo para cuentas locales (user_type=LOCAL) — ver auth_service.py.
# bcrypt directo (no passlib): passlib 1.7.4 no es compatible con bcrypt>=4.1
# (falla su autodetección interna de un bug ya parcheado hace años).
def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def generar_contrasena_temporal(largo: int = 14) -> str:
    """Contraseña temporal aleatoria que cumple la política (mayúscula,
    minúscula, número y carácter especial). Sin caracteres que se confunden al
    dictarla (0/O, 1/l/I)."""
    caracteres = "ABCDEFGHJKLMNPQRSTUVWXYZ" "abcdefghijkmnopqrstuvwxyz" "23456789" "!#%+-=?@"
    while True:
        clave = "".join(secrets.choice(caracteres) for _ in range(largo))
        if problema_de_contrasena(clave) is None:
            return clave


AGENCIA_DESACTIVADA = "Tu agencia naviera está desactivada en ARGO NAVIS. Contacta a UCVMM."


def crear_token_acceso(subject: str | Any, extra: dict | None = None, *, inicio_sesion: datetime | None = None) -> str:
    """Token de acceso. `inicio_sesion` es el login original (al renovar se
    conserva); el token nunca vence después de inicio + SESION_MAXIMA_HORAS."""
    ahora  = datetime.now(timezone.utc)
    inicio = inicio_sesion or ahora
    expiracion = min(
        ahora + timedelta(minutes=configuracion.ACCESS_TOKEN_EXPIRE_MINUTES),
        inicio + timedelta(hours=configuracion.SESION_MAXIMA_HORAS),
    )
    # iat con fracción de segundo (válido en JWT): así un cierre de sesión
    # invalida también los tokens emitidos en ese mismo segundo.
    carga = {"sub": str(subject), "iat": ahora.timestamp(), "ini": int(inicio.timestamp()), "exp": expiracion}
    if extra:
        carga.update(extra)
    return jwt.encode(carga, configuracion.SECRET_KEY, algorithm=configuracion.ALGORITHM)


def inicio_de_sesion(carga: dict) -> datetime:
    """Cuándo empezó la sesión del token (los emitidos antes de este cambio no
    traen `ini`: se toma su `iat` o, sin él, ahora)."""
    marca = carga.get("ini") or carga.get("iat")
    if isinstance(marca, (int, float)):
        return datetime.fromtimestamp(marca, timezone.utc)
    return datetime.now(timezone.utc)


def cerrar_sesiones(usuario: Usuario) -> None:
    """Invalida todos los tokens emitidos hasta ahora para el usuario."""
    usuario.sesiones_validas_desde = datetime.now(timezone.utc)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, configuracion.SECRET_KEY, algorithms=[configuracion.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def obtener_id_usuario_actual(
    request:      Request,
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_bearer),
    sesion:       AsyncSession                 = Depends(obtener_sesion_bd, scope="function"),
) -> int:
    """Devuelve el id del usuario autenticado, verificando que la cuenta siga
    activa en cada request. Cualquier cambio de estado (desactivado, borrado)
    invalida el token de inmediato sin esperar al vencimiento.

    Una cuenta local con cambio de contraseña pendiente (recién creada o
    restablecida por el admin) solo puede usar las rutas para cambiarla."""
    carga   = decodificar_token(credenciales.credentials)
    user_id = carga.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    fila = (await sesion.execute(
        select(Usuario.status, Usuario.debe_cambiar_password, Usuario.sesiones_validas_desde,
               AgenciaNaviera.activo)
        .outerjoin(AgenciaNaviera, AgenciaNaviera.id == Usuario.agencia_id)
        .where(Usuario.id == uid)
    )).one_or_none()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La cuenta ya no existe.")
    estado, debe_cambiar, validas_desde, agencia_activa = fila
    if validas_desde is not None:
        emitido = carga.get("iat")
        if not isinstance(emitido, (int, float)) or emitido < validas_desde.timestamp():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión se cerró. Inicia sesión de nuevo.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    # EstadoUsuario hereda de str, así que el miembro enum y su .value ("active")
    # comparan igual; una sola comparación cubre ambos casos.
    if estado != EstadoUsuario.ACTIVO.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta está desactivada.")
    if agencia_activa is False:
        # Agencia desactivada: sus usuarios quedan fuera, también con la sesión
        # abierta. 401 para que el frontend la cierre; el login dice por qué.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AGENCIA_DESACTIVADA,
                            headers={"WWW-Authenticate": "Bearer"})
    if debe_cambiar and request.url.path not in _RUTAS_CON_CAMBIO_PENDIENTE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña antes de continuar.",
            headers={CABECERA_CAMBIO_CONTRASENA: "requerido"},
        )
    return uid
