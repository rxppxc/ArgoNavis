from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SalidaRegistroAuditoria(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    creado_en: datetime
    accion:    str
    user_id:   int | None = None
    username:  str | None = None
    detalle:   dict | None = None
    ip:        str | None = None


class SalidaBitacora(BaseModel):
    total:      int
    pagina:     int
    por_pagina: int
    items:      list[SalidaRegistroAuditoria] = Field(default_factory=list)
