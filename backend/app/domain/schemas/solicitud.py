"""Contratos HTTP de las solicitudes de Autorización Marítima."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.models.boleta import LARGO_MOTIVO_ANULACION, LARGO_NUMERO_OFICIO

RangoMarino = Literal["marino", "pasajero", "militar", "tecnico", "supernumerario", "superintendente"]
Sexo        = Literal["M", "F", "X"]
Estado      = Literal["review", "returned", "approved", "denied", "finalized", "expired"]
# La del trámite de Técnico (2026-11-18). Espejo: OperacionTecnico (models/solicitud.py).
Operacion   = Literal["embarque", "desembarque", "subir_y_bajar"]
# Los días del sellado de Shore Pass (2026-11-18). Espejo: DIAS_SELLADO (models/solicitud.py).
DiasSellado = Literal[5, 15]

# Tope genérico de archivos por envío: evita listas absurdas antes de llegar al
# servicio. El tope real de tripulantes es MAX_TRIPULANTES (30, en
# solicitud_service.py); estos 2000 alcanzan aun con los 300 del esquema × 4
# documentos + 1 de la solicitud + 20 adicionales.
MAX_ARCHIVOS_POR_ENVIO = 2000
# Tope de la página pedida en las bandejas, la consulta histórica y la bitácora: un número
# enorme hacía fallar el OFFSET de PostgreSQL con un 500 (auditoría del 2026-11-14).
MAX_PAGINA = 100_000


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
    # La ocupación salió del formulario el 2026-11-16: si un navegador con la versión
    # anterior todavía la manda, se ignora (los campos de más no se validan).

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
    documento_codigo:  str | None = Field(default=None, max_length=50)
    indice_tripulante: int | None = None


class _DatosFormularioSolicitud(BaseModel):
    """Cabecera del formulario + tripulantes + asignación de los archivos.

    La agencia no viaja: sale del usuario que envía. Qué campos son
    obligatorios depende del tipo de trámite (ServicioTramite)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    puesto_control_id: int | None  = None
    # Cambio de puerto (2026-11-13): el nuevo puesto, del mismo sector. Nulo = sin cambio.
    puesto_destino_id: int | None  = None
    # «¿Subir y bajar?» (2026-11-16): solo en los trámites que lo ofrecen; en los demás
    # se descarta. Con «Sí», cada tripulante adjunta la Carta de Responsabilidad.
    subir_y_bajar:     bool        = False
    # Embarque, Desembarque o Subir y bajar (2026-11-18): obligatoria en los trámites que
    # la piden (el de Técnico); en los demás se descarta.
    operacion:         Operacion | None = None
    # 5 o 15 días (2026-11-18): obligatorios en los trámites que los piden (Shore Pass); en
    # los demás se descartan.
    dias_sellado:      DiasSellado | None = None
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
    asignaciones: list[AsignacionArchivo]      = Field(default_factory=list, max_length=MAX_ARCHIVOS_POR_ENVIO)

    @field_validator(
        "nombre_buque", "imo", "bandera", "nombre_puerto", "puerto_desembarque",
        "motivo", "clinica_hospital", "observaciones",
    )
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)

    @field_validator("operacion", "dias_sellado", mode="before")
    @classmethod
    def _sin_elegir(cls, v):
        """«Selecciona…» llega vacío: es un valor sin elegir, no uno inválido."""
        return None if v == "" else v


class DatosCrearSolicitud(_DatosFormularioSolicitud):
    codigo_tramite: str = Field(max_length=50)


class DatosCorregirSolicitud(_DatosFormularioSolicitud):
    """Reenvío tras una devolución. El tipo de trámite no cambia.

    `documentos_conservados` son los ids de los documentos ya cargados que se
    mantienen; los que no vengan en la lista se eliminan."""
    documentos_conservados: list[int] = Field(default_factory=list, max_length=MAX_ARCHIVOS_POR_ENVIO)


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

    tripulantes:       list[DatosImpedimentoTripulante] = Field(min_length=1, max_length=300)
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


class DatosBoleta(BaseModel):
    """La boleta de recargo (2026-11-16): el número de oficio que escribe el
    funcionario. Se le quitan los espacios de los extremos y los repetidos; es
    único entre todas las boletas (lo comprueba el servicio)."""
    numero_oficio: str = Field(max_length=200)

    @field_validator("numero_oficio")
    @classmethod
    def _normalizar(cls, v: str) -> str:
        if any(c in v for c in "\r\n\t"):
            raise ValueError("El número de oficio va en una sola línea.")
        v = " ".join(v.split())
        if not v:
            raise ValueError("Escribe el número de oficio.")
        if len(v) > LARGO_NUMERO_OFICIO:
            raise ValueError(f"El número de oficio admite hasta {LARGO_NUMERO_OFICIO} caracteres.")
        return v


class DatosAnularBoleta(BaseModel):
    """Por qué se anula la boleta: queda con ella, en el historial y en la bitácora."""
    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: str = Field(min_length=5, max_length=LARGO_MOTIVO_ANULACION)


class DatosAprobacion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    observacion: str | None = Field(default=None, max_length=2000)

    @field_validator("observacion")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


class DatosFinalizar(BaseModel):
    """Cierre en el puesto de control, con el comentario de la operación.

    Se finaliza siempre en el puesto autorizado (desde el 2026-10-30). El
    campo `puesto_finalizacion_id` ya no lo manda la interfaz: queda para que
    una página abierta antes del cambio reciba el motivo si elige otro puesto."""
    model_config = ConfigDict(str_strip_whitespace=True)

    comentario:             str = Field(min_length=3, max_length=2000)
    puesto_finalizacion_id: int | None = None


class ConsultaBandeja(BaseModel):
    """Filtros y página de una bandeja (van en la query string)."""
    estado:     Estado | None = None
    texto:      str | None = Field(default=None, max_length=100)
    desde:      date | None = None   # fecha de envío, en hora de Panamá
    hasta:      date | None = None
    pagina:     int = Field(default=1, ge=1, le=MAX_PAGINA)
    por_pagina: int = Field(default=20, ge=5, le=100)

    @field_validator("texto")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)


class ConsultaHistorica(BaseModel):
    """Filtros de la consulta histórica (2026-11-11): las solicitudes que ve el
    personal del SNM, de cualquier año, con filtros que las bandejas no tienen.
    Van en el cuerpo del pedido (POST, 2026-11-14), para que el pasajero buscado no
    quede en los logs; la exportación a Excel usa los mismos."""
    texto:            str | None = Field(default=None, max_length=100)   # número, buque, IMO, agencia, puesto
    pasajero:         str | None = Field(default=None, max_length=100)   # nombre, pasaporte o seamanbook
    agencia_id:       int | None = Field(default=None, ge=1)
    puesto_id:        int | None = Field(default=None, ge=1)
    tipo_tramite_id:  int | None = Field(default=None, ge=1)
    estado:           Estado | None = None
    autorizadas:      bool = False   # solo las que se aprobaron alguna vez (2026-11-22)
    fuera_de_horario: bool = False
    fecha:            Literal["envio", "operacion"] = "envio"   # a qué fecha van desde y hasta
    desde:            date | None = None
    hasta:            date | None = None
    pagina:           int = Field(default=1, ge=1, le=MAX_PAGINA)
    por_pagina:       int = Field(default=20, ge=5, le=100)

    @field_validator("texto", "pasajero")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        return _texto_o_nada(v)

    @model_validator(mode="after")
    def _rango(self) -> "ConsultaHistorica":
        if self.desde and self.hasta and self.hasta < self.desde:
            raise ValueError("La fecha «hasta» no puede ser anterior a «desde».")
        return self


class OpcionFiltro(BaseModel):
    id:     int
    nombre: str
    activo: bool = True


class SalidaOpcionesHistorico(BaseModel):
    """Los filtros de la consulta histórica, con lo desactivado (una solicitud
    vieja puede ser de un puesto que ya no existe). Los puestos, solo los del
    alcance de quien consulta, también los que cambiaron de sector."""
    agencias: list[OpcionFiltro]
    puestos:  list[OpcionFiltro]
    tramites: list[OpcionFiltro]


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
    # Solo la traen las solicitudes enviadas antes del 2026-11-16 (salió del formulario).
    ocupacion:        str | None = None
    es_panameno:      bool
    nacionalidad_restringida: bool
    # Verificación de impedimentos de la persona, la de UCVMM y la del puesto de
    # control. Solo para personal SNM (a la agencia le llega None): None = sin verificar.
    con_impedimento:  bool | None = None
    con_impedimento_puesto: bool | None = None
    porta_libreta:    bool
    orden:            int

    # Alertas para la revisión, calculadas a la fecha de la operación
    pasaporte_vencido: bool = False
    # Vigente ese día, pero vence antes de 3 meses (2026-11-13: no deja enviar).
    pasaporte_vigencia_corta: bool = False
    # El seamanbook vencido no impide enviar desde el 2026-11-13: solo se señala.
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
    # Opcional (2026-11-11): sin archivo no cuenta como faltante.
    obligatoria:       bool = True


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
    finalizar:              bool = False
    descargar_autorizacion: bool = False
    # Tendría permiso de revisar, pero la solicitud la creó él o es de su
    # agencia (separación de funciones): la interfaz explica por qué no puede.
    conflicto_revision:     bool = False
    # Boleta de recargo (2026-11-16): generar si no hay una vigente; anular la vigente.
    generar_boleta:         bool = False
    anular_boleta:          bool = False
    # El historial completo: versiones, documentos retirados y huellas (2026-11-22).
    ver_registro:           bool = False


class SalidaVersion(BaseModel):
    """Lo que la agencia había enviado antes de una corrección (2026-11-22): la foto, con
    los nombres de ese día, quién la devolvió y por qué, y qué cambió al corregirla."""
    numero:        int
    enviada_en:    datetime
    enviada_por:   str | None = None
    devuelta_en:   datetime | None = None
    devuelta_por:  str | None = None
    motivo:        str | None = None
    corregida_en:  datetime
    corregida_por: str | None = None
    datos:         list[tuple[str, str]]          # (rótulo, valor)
    tripulantes:   list[dict]                     # id, nombre y datos (rótulo, valor)
    documentos:    list[dict]                     # id, documento, tripulante y nombre del archivo
    cambios:       list[str]


class SalidaArchivo(BaseModel):
    """Un archivo de la solicitud con su huella: un documento (vigente o retirado) o una
    autorización emitida (2026-11-22)."""
    clase:       Literal["documento", "emitido"]
    id:          int
    documento:   str                    # qué es: «Libreta de marino», «Autorización aprobada»…
    tripulante:  str | None = None
    nombre:      str                    # el del archivo
    tamano:      int
    tipo_mime:   str
    sha256:      str | None = None      # None: de antes, hasta que se le calcula
    fecha:       datetime               # subido o emitido
    por:         str | None = None
    retirado_en: datetime | None = None


class SalidaRegistro(BaseModel):
    """El historial completo de una solicitud (2026-11-22)."""
    versiones:   list[SalidaVersion]
    # Correcciones de antes del 2026-11-22, que no guardaron lo que se había enviado.
    sin_version: int
    archivos:    list[SalidaArchivo]


class SalidaBoleta(BaseModel):
    """Una boleta de recargo (2026-11-16). Solo para el personal del SNM."""
    id:               int
    numero_oficio:    str
    monto:            str             # "B/.20.00"
    generada_en:      datetime
    generada_por:     str | None = None
    anulada_en:       datetime | None = None
    anulada_por:      str | None = None
    motivo_anulacion: str | None = None
    vigente:          bool


class SalidaTripulanteEncontrado(BaseModel):
    """Un tripulante que coincide con lo buscado en la consulta histórica (2026-11-22)."""
    nombre:    str
    pasaporte: str


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
    # Cambio de puerto (2026-11-13): el nuevo puesto, que es el que la finaliza.
    puesto_destino_nombre: str | None = None
    # La del trámite de Técnico (2026-11-18): Embarque, Desembarque o Subir y bajar.
    operacion:            Operacion | None = None
    # Los días del sellado de Shore Pass (2026-11-18): 5 o 15.
    dias_sellado:         DiasSellado | None = None
    # El sector de UCVMM que la revisó o, sin revisar, el del puesto (2026-11-22; antes,
    # siempre el del puesto). Solo para el SNM: a la agencia le llega None.
    sector_nombre:        str | None = None
    # El sector de hoy del puesto, si cambió desde que se revisó. Solo para el SNM.
    sector_actual_nombre: str | None = None
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
    # Algún tripulante de nacionalidad restringida: desde el 2026-11-14, en todos los
    # trámites (se le pide la Visa); antes, solo en los que avisan la custodia.
    tiene_nacionalidad_restringida: bool = False
    # Aprobada fuera del horario laboral (None: sin aprobar). Desde el 2026-11-11
    # lo ve también la agencia, con el recargo guardado al aprobar
    # ("B/.20.00"; None si no tiene).
    fuera_de_horario:               bool | None = None
    costo_fuera_de_horario:         str | None = None
    # Al buscar un tripulante en la consulta histórica, los que coinciden (2026-11-22). None en lo demás.
    tripulantes_encontrados:        list[SalidaTripulanteEncontrado] | None = None


class PaginaSolicitudes(BaseModel):
    total:      int
    pagina:     int
    por_pagina: int
    # Cantidad por estado con los mismos filtros (sin el de estado): son los
    # números de las pestañas de la bandeja.
    conteos:    dict[str, int] = Field(default_factory=dict)
    # Con los mismos filtros, las que se aprobaron alguna vez: vigentes, finalizadas y
    # vencidas sin finalizar (2026-11-22).
    autorizadas: int = 0
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
    puesto_destino_id:  int | None = None
    # «¿Subir y bajar?» (2026-11-16): la respuesta y si el trámite hace la pregunta.
    subir_y_bajar:          bool = False
    permite_subir_y_bajar:  bool = False
    # Si el trámite pide la operación (2026-11-18: el de Técnico).
    pide_operacion:         bool = False
    # Si el trámite pide los días del sellado (2026-11-18: Shore Pass).
    pide_dias_sellado:      bool = False
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
    # La del puesto de control antes de finalizar (2026-11-06), aparte de la de UCVMM.
    impedimentos_puesto_verificados: bool = False
    comentario_impedimentos_puesto:  str | None = None
    impedimentos_puesto_en:          datetime | None = None
    impedimentos_puesto_por:         str | None = None
    motivo_devolucion:       str | None = None
    observacion_aprobacion:  str | None = None
    aprobada_por:            str | None = None
    motivo_negacion:         str | None = None
    comentario_finalizacion: str | None = None
    finalizada_por:          str | None = None
    # Dónde se finalizó: el autorizado (antes del 2026-10-30 podía ser otro).
    puesto_finalizacion_id:     int | None = None
    puesto_finalizacion_nombre: str | None = None

    tripulantes: list[SalidaTripulante] = Field(default_factory=list)
    documentos:  list[SalidaDocumentoSolicitud]  = Field(default_factory=list)
    checklist:   list[SalidaCasilla]    = Field(default_factory=list)
    eventos:     list[SalidaEvento]     = Field(default_factory=list)
    acciones:    AccionesSolicitud      = Field(default_factory=AccionesSolicitud)
    # Las boletas de recargo, con las anuladas (2026-11-16). None para la agencia: no
    # las ve (las imprime el SNM y se las entrega).
    boletas:     list[SalidaBoleta] | None = None


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
    puesto_destino_nombre: str | None = None   # cambio de puerto: donde vale y se finaliza
    fecha_operacion: date | None = None
    aprobada_en:     datetime | None = None
    vigente_hasta:   datetime | None = None
    finalizada_en:   datetime | None = None
    puesto_finalizacion_nombre: str | None = None
    # Si quien escanea puede ver el PDF (la copia de la agencia, 2026-11-14): mientras
    # valga y hasta DIAS_PDF_PUBLICO días después de la operación.
    pdf_disponible:  bool = False
    tripulantes:     list[SalidaTripulanteVerificacion] = Field(default_factory=list)


# ── Estadísticas ─────────────────────────────────────────────────────────────

class FilaEstadisticaTipo(BaseModel):
    codigo:    str
    nombre:    str
    recibidas: int
    aprobadas: int
    negadas:   int
    expiradas: int


class FilaEstadisticaSerie(BaseModel):
    """Lo que pasó en un día, un mes o un año (hora de Panamá): cada cifra
    cuenta cuando ocurrió (la llegada, la aprobación, la finalización…)."""
    periodo:       str   # "2026-10-05", "2026-10" o "2026"
    recibidas:     int = 0
    aprobadas:     int = 0
    negadas:       int = 0
    expiradas:     int = 0
    finalizadas:   int = 0
    fuera_horario: int = 0   # aprobadas fuera del horario laboral


class FilaEstadisticaPuesto(BaseModel):
    puesto:        str
    aprobadas:     int
    finalizadas:   int
    expiradas:     int


class FilaFueraHorario(BaseModel):
    """Una autorización aprobada fuera del horario laboral."""
    id:           int
    numero:       str | None = None
    tipo_tramite: str
    puesto:       str
    aprobada_en:  datetime
    aprobada_por: str | None = None


class FilaPorHora(BaseModel):
    """Aprobadas un día de la semana a una hora, en hora de Panamá."""
    dia:   int   # 1 = lunes … 7 = domingo
    hora:  int   # 0–23
    total: int


class FilaSector(BaseModel):
    id:     int
    nombre: str


class SalidaEstadisticasSolicitudes(BaseModel):
    recibidas:   int
    por_estado:  dict[str, int]
    aprobadas:   int   # aprobadas alguna vez (incluye las ya finalizadas o expiradas)
    negadas:     int
    expiradas:   int
    finalizadas: int
    horas_promedio_resolucion: float | None = None
    # Aprobadas por UCVMM fuera del horario laboral (core/horario.py) y las más recientes.
    aprobadas_fuera_horario:   int = 0
    horario_laboral:           str = ""
    operaciones_fuera_horario: list[FilaFueraHorario] = Field(default_factory=list)
    # El mapa de horas de las estadísticas: solo las celdas con alguna aprobada.
    aprobadas_por_hora:        list[FilaPorHora] = Field(default_factory=list)
    por_tipo:   list[FilaEstadisticaTipo]   = Field(default_factory=list)
    # La misma serie por día (los últimos 31 del periodo), por mes (hasta 12) y por año (hasta 10).
    por_dia:     list[FilaEstadisticaSerie]  = Field(default_factory=list)
    por_mes:     list[FilaEstadisticaSerie]  = Field(default_factory=list)
    por_anio:    list[FilaEstadisticaSerie]  = Field(default_factory=list)
    por_puesto:  list[FilaEstadisticaPuesto] = Field(default_factory=list)
    # De qué sectores son las cifras (2026-11-10): UCVMM y el supervisor de sector
    # ven las de sus sectores; el Administrador y el supervisor general, las de
    # todos, y pueden elegir uno (`sectores`). El uso del sistema, solo ellos.
    alcance:     str = "Todos los sectores"
    sector_id:   int | None = None
    sectores:    list[FilaSector] = Field(default_factory=list)
    uso_del_sistema: bool = True


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
