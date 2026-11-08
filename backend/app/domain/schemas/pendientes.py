"""Contratos de las notificaciones internas (la campana de la cabecera)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SalidaPendiente(BaseModel):
    """Lo que le toca hacer al usuario en una de sus bandejas."""
    clave:    Literal["por_revisar", "por_finalizar", "por_corregir"]
    texto:    str
    cantidad: int
    bandeja:  Literal["agencia", "revision", "puerto"]
    estado:   Literal["review", "returned", "approved"]
    # El plazo más próximo (corrección o finalización); nulo si no hay ninguna.
    vence_en: datetime | None = None


class SalidaNovedad(BaseModel):
    """Un paso de una de sus solicitudes, como lo ve el usuario (a la agencia
    no le llega lo interno ni el nombre de los funcionarios)."""
    id:             int   # del evento del historial
    solicitud_id:   int
    numero:         str | None = None
    titulo:         str
    tipo:           str
    comentario:     str | None = None
    usuario_nombre: str | None = None
    creado_en:      datetime
    no_leida:       bool


class SalidaPendientes(BaseModel):
    # Si el usuario trabaja solicitudes (el SysAdmin no: no lleva campana).
    disponible: bool
    pendientes: list[SalidaPendiente] = Field(default_factory=list)
    novedades:  list[SalidaNovedad]   = Field(default_factory=list)
    no_leidas:  int = 0
