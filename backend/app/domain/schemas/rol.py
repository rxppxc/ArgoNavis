from pydantic import BaseModel, field_validator
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
    descripcion: str | None = None

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
    nombre:      str | None = None
    descripcion: str | None = None


class DatosAsignarPermisos(BaseModel):
    permiso_ids: list[int]


class DatosAsignarRol(BaseModel):
    rol_id: int | None
