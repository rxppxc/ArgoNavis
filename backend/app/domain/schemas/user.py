import unicodedata

from pydantic import BaseModel, ValidationInfo, field_validator
from app.domain.models.user import TipoUsuario, EstadoUsuario
from app.domain.schemas.catalogo import SalidaCatalogoMini
from app.domain.schemas.rol import RolMini

LARGO_MINIMO_CONTRASENA = 12
LARGO_MAXIMO_CONTRASENA = 64
# Lo primero que prueba cualquiera: con estas palabras la contraseña no vale
# aunque cumpla lo demás (se comparan sin tildes ni mayúsculas).
_PALABRAS_PROHIBIDAS = ("password", "contrasena", "qwerty", "123456", "navis", "migracion", "panama")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def problema_de_contrasena(clave: str, usuario: str | None = None) -> str | None:
    """Política de las cuentas locales (las del AD siguen la del dominio). None
    si la cumple. Espejo en frontend/src/utils/contrasena.ts."""
    if len(clave) < LARGO_MINIMO_CONTRASENA:
        return f"La contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres."
    if len(clave) > LARGO_MAXIMO_CONTRASENA or len(clave.encode("utf-8")) > 72:   # bcrypt solo usa 72 bytes
        return f"La contraseña es demasiado larga (máximo {LARGO_MAXIMO_CONTRASENA} caracteres)."
    if not any(c.isupper() for c in clave):
        return "La contraseña debe tener al menos una mayúscula."
    if not any(c.islower() for c in clave):
        return "La contraseña debe tener al menos una minúscula."
    if not any(c.isdigit() for c in clave):
        return "La contraseña debe tener al menos un número."
    if not any(not c.isalnum() and not c.isspace() for c in clave):
        return "La contraseña debe tener al menos un carácter especial (por ejemplo ! # % - . @)."
    normal = _normalizar(clave)
    if usuario and len(usuario.strip()) >= 3 and _normalizar(usuario.strip()) in normal:
        return "La contraseña no puede contener el nombre de usuario."
    if any(palabra in normal for palabra in _PALABRAS_PROHIBIDAS):
        return "La contraseña no puede contener palabras fáciles de adivinar (password, navis, 123456…)."
    return None


def validar_politica_contrasena(v: str, usuario: str | None = None) -> str:
    problema = problema_de_contrasena(v or "", usuario)
    if problema:
        raise ValueError(problema)
    return v


class SalidaUsuario(BaseModel):
    id:        int
    username:  str
    name:      str | None
    last_name: str | None
    email:     str | None
    user_type: TipoUsuario
    status:    EstadoUsuario
    rol_id:    int | None = None
    rol_personalizado: RolMini | None = None
    agencia_id: int | None = None
    agencia:    SalidaCatalogoMini | None = None
    debe_cambiar_password: bool = False
    full_name: str

    model_config = {"from_attributes": True}


class RespuestaToken(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         SalidaUsuario


class SolicitudLogin(BaseModel):
    username: str
    password: str


class DatosCrearUsuario(BaseModel):
    """Alta de un usuario a partir de su cuenta de Active Directory."""
    username: str

    @field_validator("username")
    @classmethod
    def _v_username(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Se requiere el nombre de usuario.")
        return v


class DatosCambiarEstado(BaseModel):
    """Activar o desactivar la cuenta de un usuario."""
    status: EstadoUsuario


class DatosCrearUsuarioLocal(BaseModel):
    """Alta de un usuario LOCAL (sin Active Directory): cuentas para usuarios
    externos, como los de las agencias navieras. Requiere PERMITIR_LOGIN_LOCAL.
    Entra con la contraseña inicial y el sistema le pide cambiarla."""
    username:  str
    password:  str
    name:      str | None = None
    last_name: str | None = None
    email:     str | None = None
    rol_id:    int | None = None

    @field_validator("username")
    @classmethod
    def _v_username(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Se requiere el nombre de usuario.")
        return v

    @field_validator("password")
    @classmethod
    def _v_password(cls, v: str, info: ValidationInfo) -> str:
        return validar_politica_contrasena(v, info.data.get("username"))


class DatosCambiarContrasena(BaseModel):
    """Cambio de contraseña de la propia cuenta local."""
    actual: str
    nueva:  str

    @field_validator("nueva")
    @classmethod
    def _v_nueva(cls, v: str) -> str:
        return validar_politica_contrasena(v)


class RespuestaContrasenaTemporal(BaseModel):
    """Contraseña temporal generada al restablecer una cuenta local. Se
    muestra una sola vez al administrador; el usuario debe cambiarla al entrar."""
    contrasena_temporal: str
