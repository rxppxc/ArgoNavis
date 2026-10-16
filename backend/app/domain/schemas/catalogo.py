import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validar_correo(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not _EMAIL_RE.match(v):
        raise ValueError("El correo no tiene un formato válido.")
    return v


# ── Puestos de control y agencias navieras ───────────────────────────────────
# Los dos catálogos tienen la misma forma: nombre, buzón de correo, activo y
# los usuarios asignados (funcionarios del puesto / usuarios de la agencia).

class SalidaCatalogoMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:     int
    nombre: str


class UsuarioAsignado(BaseModel):
    id:        int
    username:  str
    full_name: str


class SalidaCatalogoConUsuarios(BaseModel):
    id:       int
    nombre:   str
    correo:   str | None = None
    activo:   bool
    usuarios: list[UsuarioAsignado] = Field(default_factory=list)
    total_solicitudes: int = 0


class SalidaPuesto(SalidaCatalogoConUsuarios):
    pass


class SalidaAgencia(SalidaCatalogoConUsuarios):
    pass


class _DatosCrearConCorreo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=3, max_length=200)
    correo: str | None = Field(default=None, max_length=255)

    @field_validator("correo")
    @classmethod
    def _v_correo(cls, v: str | None) -> str | None:
        return _validar_correo(v)


class _DatosActualizarConCorreo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str | None  = Field(default=None, min_length=3, max_length=200)
    correo: str | None  = Field(default=None, max_length=255)
    activo: bool | None = None

    @field_validator("correo")
    @classmethod
    def _v_correo(cls, v: str | None) -> str | None:
        return _validar_correo(v)


class DatosCrearPuesto(_DatosCrearConCorreo):
    pass


class DatosActualizarPuesto(_DatosActualizarConCorreo):
    pass


class DatosCrearAgencia(_DatosCrearConCorreo):
    pass


class DatosActualizarAgencia(_DatosActualizarConCorreo):
    pass


class DatosAsignarUsuarios(BaseModel):
    usuario_ids: list[int] = Field(default_factory=list)


# ── Países ───────────────────────────────────────────────────────────────────

class SalidaPais(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    nacionalidad_restringida: bool


class DatosActualizarPais(BaseModel):
    nacionalidad_restringida: bool
