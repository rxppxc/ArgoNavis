"""Contratos HTTP de las solicitudes de Autorización Marítima."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RangoMarino = Literal["marino", "militar", "tecnico", "supernumerario", "superintendente"]
Sexo        = Literal["M", "F", "X"]
Estado      = Literal["review", "returned", "approved", "denied", "finalized", "expired"]


def _texto_o_nada(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


# ── Entrada ──────────────────────────────────────────────────────────────────

class DatosTripulanteEntrada(BaseModel):
    """Ficha del tripulante (formulario de registro del marino de UCVMM).

    `id` solo viaja al corregir: identifica a un tripulante ya registrado que
    se conserva (con sus documentos). Sin `id` es un tripulante nuevo."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id:               int | None = None
    nombre:           str  = Field(min_length=2, max_length=150)
    apellido:         str  = Field(min_length=2, max_length=150)
    fecha_nacimiento: date
    pais_nacimiento:  str  = Field(min_length=3, max_length=3)
    nacionalidad:     str  = Field(min_length=3, max_length=3)
    sexo:             Sexo
    pasaporte:        str  = Field(min_length=3, max_length=100)
    pasaporte_expira: date
    libreta_marino:   str | None = Field(default=None, max_length=100)   # seamanbook
    libreta_expira:   date | None = None
    rango:            RangoMarino
    ocupacion:        str  = Field(min_length=2, max_length=150)

    @field_validator("pais_nacimiento", "nacionalidad", "pasaporte")
    @classmethod
    def _mayusculas(cls, v: str) -> str:
        return v.upper()

    @field_validator("libreta_marino")
    @classmethod
    def _libreta(cls, v: str | None) -> str | None:
        v = _texto_o_nada(v)
        return v.upper() if v else None


class AsignacionArchivo(BaseModel):
    """A qué casilla corresponde el archivo en la misma posición.

    - `documento_codigo` nulo = documento adicional (fuera del checklist).
    - `indice_tripulante` (posición en `tripulantes`) solo para documentos de
      alcance "marino"; nulo para los de la solicitud y los adicionales."""
    documento_codigo:  str | None = None
    indice_tripulante: int | None = None


class _DatosFormularioSolicitud(BaseModel):
    """Cabecera del formulario + tripulantes + asignación de los archivos.

    La agencia no viaja: sale del usuario que envía. Qué campos son
    obligatorios depende del tipo de trámite (ServicioTramite)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    puesto_control_id: int | None  = None
    fecha_operacion:   date | None = None

    nombre_buque: str | None = Field(default=None, max_length=255)
    imo:          str | None = Field(default=None, max_length=20)
    bandera:      str | None = Field(default=None, max_length=3)   # código de país

    # Según el tipo de trámite (ver TipoTramite.requiere_*)
    nombre_puerto:      str | None = Field(default=None, max_length=255)
    puerto_desembarque: str | None = Field(default=None, max_length=255)
    motivo:             str | None = Field(default=None, max_length=2000)
    clinica_hospital:   str | None = Field(default=None, max_length=255)

    observaciones: str | None = Field(default=None, max_length=2000)

    tripulantes:  list[DatosTripulanteEntrada] = Field(default_factory=list, max_length=300)
    asignaciones: list[AsignacionArchivo]      = Field(default_factory=list)

    @field_validator(
        "nombre_buque", "imo", "bandera", "nombre_puerto", "puerto_desembarque",
        "motivo", "clinica_hospital", "observaciones",
    )
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


class DatosCrearSolicitud(_DatosFormularioSolicitud):
    codigo_tramite: str


class DatosCorregirSolicitud(_DatosFormularioSolicitud):
    """Reenvío tras una devolución. El tipo de trámite no cambia.

    `documentos_conservados` son los ids de los documentos ya cargados que se
    mantienen; los que no vengan en la lista se eliminan."""
    documentos_conservados: list[int] = Field(default_factory=list)


class DatosImpedimentoTripulante(BaseModel):
    """Resultado de la verificación en SIMPLUS de un tripulante."""
    tripulante_id:   int
    con_impedimento: bool


class DatosImpedimentos(BaseModel):
    """Verificación de impedimentos (SIMPLUS) por tripulante y, opcional, un
    comentario. Tienen que venir todos los tripulantes de la solicitud, una
    vez cada uno. Si ya estaba registrada, es una corrección y exige
    `motivo_correccion`."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tripulantes:       list[DatosImpedimentoTripulante] = Field(min_length=1)
    comentario:        str | None = Field(default=None, max_length=2000)
    motivo_correccion: str | None = Field(default=None, max_length=2000)

    @field_validator("comentario", "motivo_correccion")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


class DatosMotivo(BaseModel):
    """Motivo obligatorio al devolver a corrección o negar."""
    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: str = Field(min_length=5, max_length=2000)


class DatosAprobacion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    observacion: str | None = Field(default=None, max_length=2000)

    @field_validator("observacion")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


class DatosComentario(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    comentario: str = Field(min_length=3, max_length=2000)


class DatosFinalizar(DatosComentario):
    """Cierre en el puesto de control. `puesto_finalizacion_id` es donde terminó
    la operación (puede ser otro que el autorizado); vacío = el autorizado."""
    puesto_finalizacion_id: int | None = None


class ConsultaBandeja(BaseModel):
    """Filtros y página de una bandeja (van en la query string)."""
    estado:     Estado | None = None
    texto:      str | None = Field(default=None, max_length=100)
    desde:      date | None = None   # fecha de envío, en hora de Panamá
    hasta:      date | None = None
    pagina:     int = Field(default=1, ge=1)
    por_pagina: int = Field(default=20, ge=5, le=100)

    @field_validator("texto")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


# ── Salida ───────────────────────────────────────────────────────────────────

class SalidaTripulante(BaseModel):
    id:               int
    nombre:           str
    apellido:         str
    nombre_completo:  str
    fecha_nacimiento: date
    pais_nacimiento:        str
    pais_nacimiento_nombre: str | None = None
    nacionalidad:           str
    nacionalidad_nombre:    str | None = None
    sexo:             str
    pasaporte:        str
    pasaporte_expira: date
    libreta_marino:   str | None = None
    libreta_expira:   date | None = None
    rango:            str
    ocupacion:        str
    es_panameno:      bool
    nacionalidad_restringida: bool
    # Verificación de impedimentos de la persona. Solo para personal SNM
    # (a la agencia le llega None): None = sin verificar.
    con_impedimento:  bool | None = None
    porta_libreta:    bool
    orden:            int

    # Alertas para la revisión, calculadas a la fecha de la operación
    pasaporte_vencido: bool = False
    libreta_vencida:   bool = False


class SalidaDocumentoSolicitud(BaseModel):
    id:               int
    nombre_original:  str
    tamano:           int
    tipo_mime:        str | None = None
    documento_id:     int | None = None   # nulo = documento adicional
    documento_codigo: str | None = None
    documento_nombre: str | None = None
    tripulante_id:    int | None = None
    created_at:       datetime


class SalidaCasilla(BaseModel):
    """Una casilla del checklist ya resuelta para esta solicitud."""
    documento_id:      int
    documento_codigo:  str
    documento_nombre:  str
    alcance:           str
    tripulante_id:     int | None = None
    tripulante_nombre: str | None = None
    documento_ids:     list[int] = Field(default_factory=list)
    cubierta:          bool


class SalidaEvento(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              int
    tipo:            str
    estado_anterior: str | None = None
    estado_nuevo:    str | None = None
    comentario:      str | None = None
    usuario_nombre:  str | None = None
    creado_en:       datetime


class AccionesSolicitud(BaseModel):
    """Qué puede hacer el usuario actual con esta solicitud (la interfaz
    muestra los botones según esto; el backend igual lo vuelve a validar)."""
    corregir:               bool = False
    revisar:                bool = False
    comentar:               bool = False
    finalizar:              bool = False
    descargar_autorizacion: bool = False
    # Tendría permiso de revisar, pero la solicitud la creó él o es de su
    # agencia (separación de funciones): la interfaz explica por qué no puede.
    conflicto_revision:     bool = False


class SalidaSolicitudResumen(BaseModel):
    """Fila de las bandejas (agencia, revisión, puerto)."""
    id:                   int
    numero:               str | None = None
    titulo:               str
    estado:               Estado
    tipo_tramite_codigo:  str
    tipo_tramite_nombre:  str
    agencia_id:           int
    agencia_nombre:       str
    puesto_nombre:        str
    nombre_buque:         str | None = None
    imo:                  str | None = None
    fecha_operacion:      date
    cantidad_tripulantes: int
    creada_por:           str | None = None
    created_at:           datetime
    enviada_en:           datetime
    plazo_correccion:     datetime | None = None
    vigente_hasta:        datetime | None = None
    aprobada_en:          datetime | None = None
    negada_en:            datetime | None = None
    finalizada_en:        datetime | None = None
    expirada_en:          datetime | None = None
    veces_devuelta:       int = 0
    tripulantes_con_alerta:         int = 0
    # Solo en los trámites con aviso de custodia (los demás procesos no la mencionan).
    tiene_nacionalidad_restringida: bool = False


class PaginaSolicitudes(BaseModel):
    total:      int
    pagina:     int
    por_pagina: int
    # Cantidad por estado con los mismos filtros (sin el de estado): son los
    # números de las pestañas de la bandeja.
    conteos:    dict[str, int] = Field(default_factory=dict)
    items:      list[SalidaSolicitudResumen] = Field(default_factory=list)


class SalidaSolicitud(SalidaSolicitudResumen):
    """Expediente completo de una solicitud."""
    tipo_tramite_nota:           str | None = None
    # Al aprobar se avisa que se debe tramitar la custodia de los restringidos.
    tipo_tramite_aviso_custodia: bool = False
    requiere_buque:              bool = False
    requiere_puerto:             bool = False
    requiere_puerto_desembarque: bool = False
    requiere_motivo:             bool = False
    requiere_clinica:            bool = False
    valida_vigencia:             bool = False

    puesto_control_id:  int
    bandera:            str | None = None
    bandera_nombre:     str | None = None
    nombre_puerto:      str | None = None
    puerto_desembarque: str | None = None
    motivo:             str | None = None
    clinica_hospital:   str | None = None
    observaciones:      str | None = None

    impedimentos_verificados:     bool = False
    comentario_impedimentos:      str | None = None
    impedimentos_verificados_en:  datetime | None = None
    impedimentos_verificados_por: str | None = None
    motivo_devolucion:       str | None = None
    observacion_aprobacion:  str | None = None
    aprobada_por:            str | None = None
    motivo_negacion:         str | None = None
    comentario_finalizacion: str | None = None
    finalizada_por:          str | None = None
    # Dónde terminó la operación (puede ser otro puesto que el autorizado).
    puesto_finalizacion_id:     int | None = None
    puesto_finalizacion_nombre: str | None = None

    tripulantes: list[SalidaTripulante] = Field(default_factory=list)
    documentos:  list[SalidaDocumentoSolicitud]  = Field(default_factory=list)
    checklist:   list[SalidaCasilla]    = Field(default_factory=list)
    eventos:     list[SalidaEvento]     = Field(default_factory=list)
    acciones:    AccionesSolicitud      = Field(default_factory=AccionesSolicitud)


class SalidaTripulanteVerificacion(BaseModel):
    nombre_completo: str
    nacionalidad:    str | None = None
    pasaporte:       str | None = None   # enmascarado: solo los últimos 4 caracteres
    rango:           str | None = None


class SalidaVerificacion(BaseModel):
    """Lo que muestra el QR de una autorización: lo mínimo para comprobar
    que es auténtica y está vigente, sin exponer el expediente."""
    valida:          bool
    estado:          Estado
    numero:          str | None = None
    tipo_tramite:    str | None = None
    agencia_nombre:  str | None = None
    nombre_buque:    str | None = None
    imo:             str | None = None
    bandera:         str | None = None
    puesto_nombre:   str | None = None
    fecha_operacion: date | None = None
    aprobada_en:     datetime | None = None
    vigente_hasta:   datetime | None = None
    finalizada_en:   datetime | None = None
    puesto_finalizacion_nombre: str | None = None
    tripulantes:     list[SalidaTripulanteVerificacion] = Field(default_factory=list)


# ── Estadísticas ─────────────────────────────────────────────────────────────

class FilaEstadisticaTipo(BaseModel):
    codigo:    str
    nombre:    str
    recibidas: int
    aprobadas: int
    negadas:   int
    expiradas: int


class FilaEstadisticaMes(BaseModel):
    mes:       str   # "2026-10"
    recibidas: int
    aprobadas: int
    negadas:   int
    expiradas: int


class FilaEstadisticaPuesto(BaseModel):
    puesto:      str
    aprobadas:   int
    finalizadas: int
    expiradas:   int


class SalidaEstadisticasSolicitudes(BaseModel):
    recibidas:   int
    por_estado:  dict[str, int]
    aprobadas:   int   # aprobadas alguna vez (incluye las ya finalizadas o expiradas)
    negadas:     int
    expiradas:   int
    finalizadas: int
    horas_promedio_resolucion: float | None = None
    por_tipo:    list[FilaEstadisticaTipo]   = Field(default_factory=list)
    por_mes:     list[FilaEstadisticaMes]    = Field(default_factory=list)
    por_puesto:  list[FilaEstadisticaPuesto] = Field(default_factory=list)


class FilaTopAgencia(BaseModel):
    agencia_id: int
    nombre:     str
    total:      int


class SalidaUsoSistema(BaseModel):
    """Uso del sistema (no del flujo): cuentas, agencias y almacenamiento."""
    usuarios:             int
    usuarios_activos:     int
    agencias:             int
    documentos:           int
    almacenamiento_bytes: int
    top_agencias:         list[FilaTopAgencia] = Field(default_factory=list)
