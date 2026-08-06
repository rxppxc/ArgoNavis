from pydantic import BaseModel, field_validator
from app.domain.models.user import TipoUsuario, EstadoUsuario
from app.domain.schemas.rol import RolMini


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
    """Alta de un usuario LOCAL de prueba (sin Active Directory) — solo
    disponible fuera de producción, para probar roles/permisos sin crear
    cuentas reales en el AD. Ver ServicioAutenticacion.login."""
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
    def _v_password(cls, v: str) -> str:
        if not v or len(v) < 4:
            raise ValueError("La contraseña debe tener al menos 4 caracteres.")
        return v
