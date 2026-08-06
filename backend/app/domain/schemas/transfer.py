import re
from pydantic import BaseModel, field_validator
from datetime import datetime
from app.domain.models.transfer import EstadoTransferencia

_EMAIL_RE   = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TITULO_MAX  = 255
MENSAJE_MAX = 2000


class SalidaArchivoTransferencia(BaseModel):
    id:            int
    original_name: str
    mime_type:     str | None
    size:          int
    es_original:   bool = True
    subido_por_id: int | None = None

    model_config = {"from_attributes": True}


class SalidaTransferencia(BaseModel):
    id:            int
    token:         str
    title:         str | None
    message:       str | None
    recipient:     str | None
    expires_at:    datetime | None
    downloads:     int
    max_downloads: int | None
    status:        EstadoTransferencia
    created_at:    datetime
    files:         list[SalidaArchivoTransferencia] = []
    total_size:    int
    is_expired:    bool
    user_id:       int

    model_config = {"from_attributes": True}


class DatosCrearTransferencia(BaseModel):
    """Sube archivos y quedan disponibles de inmediato. El destinatario es
    opcional: si se indica, se envía un correo de aviso; si no, la
    transferencia queda igual visible para Sector Pacífico."""
    title:         str
    message:       str | None = None
    recipient:     str | None = None
    max_downloads: int | None = None

    @field_validator("title")
    @classmethod
    def validar_titulo(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El título es obligatorio.")
        if len(v) > TITULO_MAX:
            raise ValueError(f"El título no puede superar {TITULO_MAX} caracteres.")
        return v

    @field_validator("recipient")
    @classmethod
    def validar_destinatario(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not _EMAIL_RE.match(v):
            raise ValueError("El correo del destinatario no tiene un formato válido.")
        return v

    @field_validator("message")
    @classmethod
    def validar_mensaje(cls, v: str | None) -> str | None:
        if v is not None and len(v) > MENSAJE_MAX:
            raise ValueError(f"El mensaje no puede superar {MENSAJE_MAX} caracteres.")
        return v or None

    @field_validator("max_downloads")
    @classmethod
    def validar_max_descargas(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("El límite de descargas debe ser al menos 1.")
        return v


class RespuestaTransferenciaPublica(BaseModel):
    id:            int
    token:         str
    title:         str | None
    message:       str | None
    expires_at:    datetime | None
    downloads:     int
    max_downloads: int | None
    is_expired:    bool
    files:         list[SalidaArchivoTransferencia] = []
    total_size:    int
    sender:        str

    model_config = {"from_attributes": True}
