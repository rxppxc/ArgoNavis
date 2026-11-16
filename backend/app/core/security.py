"""Capa de seguridad: contraseñas (bcrypt) y tokens JWT.

El verificador de cada pedido, `obtener_id_usuario_actual`, está en
api/v1/dependencias.py: valida contra la BD en cada request para que los cambios
de estado del usuario (desactivado, rol revocado, borrado) tengan efecto
inmediato y no esperen al vencimiento del token.

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
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from app.core.config import obtener_configuracion
from app.core.identidad import INSTITUCION
from app.domain.models.user import Usuario
from app.domain.schemas.user import problema_de_contrasena

configuracion  = obtener_configuracion()
esquema_bearer = HTTPBearer(auto_error=True)

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


AGENCIA_DESACTIVADA = f"Tu agencia naviera está desactivada en ARGO NAVIS. Contacta al {INSTITUCION}."


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
        # Solo el algoritmo configurado: un token firmado con otro, o sin firma, no vale.
        return jwt.decode(token, configuracion.SECRET_KEY, algorithms=[configuracion.ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
