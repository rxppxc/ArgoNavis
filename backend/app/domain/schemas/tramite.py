from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

CondicionDocumento = Literal["siempre", "solo_panamenos", "nacionalidad_restringida"]
Formulario         = Literal["formulario_3"]


# ── Documento dentro del checklist de un trámite ─────────────────────────────

class SalidaTramiteDocumento(BaseModel):
    """Una fila del checklist: qué documento, con qué alcance y condición."""
    model_config = ConfigDict(from_attributes=True)

    id:           int
    documento_id: int
    codigo:       str
    nombre:       str
    descripcion:  str | None = None
    alcance:      Literal["solicitud", "marino"]
    condicion:    CondicionDocumento
    orden:        int = 0
    requiere_libreta: bool = False


# ── Tipos de trámite ─────────────────────────────────────────────────────────

class SalidaTipoTramite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    codigo:     str
    nombre:     str
    formulario: Formulario

    requiere_buque:              bool
    requiere_puerto:             bool
    requiere_puerto_desembarque: bool
    requiere_motivo:             bool
    requiere_clinica:            bool = False
    valida_vigencia:             bool = False
    # Rangos de tripulante admitidos (nulo = cualquiera).
    rangos_permitidos: list[str] | None = None
    # Al aprobar se avisa que se debe tramitar la custodia de los restringidos.
    aviso_custodia: bool = False

    nota:   str | None = None
    orden:  int  = 0
    activo: bool = True

    documentos: list[SalidaTramiteDocumento] = Field(default_factory=list)
