import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_correo(v: str | None) -> str | None:
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


class SalidaPuestoFormulario(SalidaCatalogoMini):
    """Un puesto para el formulario de solicitud. Con el número de su sector, sin
    el nombre: el cambio de puerto solo admite puestos del mismo sector (2026-11-13),
    y a la agencia no se le nombran los sectores."""
    sector_id: int


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
    # El sector de UCVMM que revisa sus solicitudes (2026-11-10).
    sector_id:     int
    sector_nombre: str


class SalidaAgencia(SalidaCatalogoConUsuarios):
    pass


class _DatosCrearConCorreo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=3, max_length=200)
    correo: str | None = Field(default=None, max_length=255)

    @field_validator("correo")
    @classmethod
    def _v_correo(cls, v: str | None) -> str | None:
        return validar_correo(v)


class _DatosActualizarConCorreo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str | None  = Field(default=None, min_length=3, max_length=200)
    correo: str | None  = Field(default=None, max_length=255)
    activo: bool | None = None

    @field_validator("correo")
    @classmethod
    def _v_correo(cls, v: str | None) -> str | None:
        return validar_correo(v)


class DatosCrearPuesto(_DatosCrearConCorreo):
    sector_id: int   # obligatorio: sin sector, ningún revisor vería sus solicitudes


class DatosActualizarPuesto(_DatosActualizarConCorreo):
    # Cambiarlo pasa sus solicitudes (también las abiertas) al otro sector.
    sector_id: int | None = None


class DatosCrearAgencia(_DatosCrearConCorreo):
    pass


class DatosActualizarAgencia(_DatosActualizarConCorreo):
    pass


class DatosAsignarUsuarios(BaseModel):
    usuario_ids: list[int] = Field(default_factory=list, max_length=500)


# ── Sectores de UCVMM (2026-11-10) ───────────────────────────────────────────
# Fijos (Pacífico y Atlántico, los siembra la migración): se cambian el buzón y
# los funcionarios asignados (UCVMM y supervisores de sector). Los puestos se
# asignan desde cada puesto.

class SalidaSector(BaseModel):
    id:       int
    nombre:   str
    correo:   str | None = None
    usuarios: list[UsuarioAsignado] = Field(default_factory=list)
    puestos:  list[SalidaCatalogoMini] = Field(default_factory=list)


class DatosActualizarSector(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    correo: str | None = Field(default=None, max_length=255)

    @field_validator("correo")
    @classmethod
    def _v_correo(cls, v: str | None) -> str | None:
        return validar_correo(v)


# ── Países ───────────────────────────────────────────────────────────────────

class SalidaPais(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    nacionalidad_restringida: bool


class DatosActualizarPais(BaseModel):
    nacionalidad_restringida: bool
