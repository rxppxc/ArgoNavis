from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class SalidaPermiso(BaseModel):
    id:          int
    codigo:      str
    nombre:      str
    descripcion: str | None
    created_at:  datetime

    model_config = {"from_attributes": True}


class RolMini(BaseModel):
    id:         int
    nombre:     str
    es_sistema: bool

    model_config = {"from_attributes": True}


class SalidaRol(BaseModel):
    id:          int
    nombre:      str
    descripcion: str | None
    es_sistema:  bool
    created_at:  datetime
    permisos:    list[SalidaPermiso] = []
    total_usuarios: int = 0

    model_config = {"from_attributes": True}


class DatosCrearRol(BaseModel):
    nombre:      str
    descripcion: str | None = Field(default=None, max_length=500)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío.")
        if len(v) > 100:
            raise ValueError("El nombre no puede superar 100 caracteres.")
        return v


class DatosActualizarRol(BaseModel):
    # roles.nombre es VARCHAR(100): sin el tope, uno más largo daba error 500.
    # El nombre vacío lo rechaza el endpoint (400), como antes.
    nombre:      str | None = Field(default=None, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)


class DatosAsignarPermisos(BaseModel):
    permiso_ids: list[int] = Field(max_length=100)


class DatosAsignarRol(BaseModel):
    rol_id: int | None
