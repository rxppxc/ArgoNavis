"""Expediente de una Solicitud de Autorización Marítima.

Es la adaptación del storage original: los documentos ya no son una
transferencia suelta con enlace público, sino el expediente de una solicitud
de una agencia — organizado por casilla del checklist y por tripulante,
visible por rol y conservado como registro del trámite.
"""
import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class EstadoSolicitud(str, enum.Enum):
    EN_REVISION   = "review"     # enviada por la naviera, en la cola de UCVMM
    EN_CORRECCION = "returned"   # UCVMM la devolvió: la agencia tiene un plazo para subsanar
    APROBADA      = "approved"   # autorizada, pendiente de que el puesto de control la finalice
    NEGADA        = "denied"     # UCVMM la rechazó (estado final)
    FINALIZADA    = "finalized"  # el puesto de control registró la operación (estado final)
    EXPIRADA      = "expired"    # venció un plazo (corrección o finalización) — estado final


class RangoMarino(str, enum.Enum):
    """Rango del tripulante. Solo el rango Marino porta seamanbook: al resto
    no se le pide libreta ni se le valida su vencimiento."""
    MARINO          = "marino"
    MILITAR         = "militar"
    TECNICO         = "tecnico"
    SUPERNUMERARIO  = "supernumerario"
    SUPERINTENDENTE = "superintendente"


RANGOS_CON_LIBRETA = {RangoMarino.MARINO.value}


class TipoEventoSolicitud(str, enum.Enum):
    """Hitos del historial de una solicitud."""
    CREADA       = "creada"
    CORREGIDA    = "corregida"
    IMPEDIMENTOS = "impedimentos"
    IMPEDIMENTOS_CORREGIDOS = "impedimentos_corregidos"
    DEVUELTA     = "devuelta"
    APROBADA     = "aprobada"
    NEGADA       = "negada"
    COMENTARIO   = "comentario"
    FINALIZADA   = "finalizada"
    EXPIRADA     = "expirada"


def _valores(enumeracion: type[enum.Enum]) -> str:
    return ", ".join(f"'{e.value}'" for e in enumeracion)


class Solicitud(Base):
    __tablename__ = "solicitudes"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_valores(EstadoSolicitud)})", name="ck_solicitudes_estado"),
    )

    id:     Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    numero: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)   # "AM-2026-000123"

    # La solicitud es de la agencia; el nombre se guarda como foto (si luego se
    # renombra la agencia o el puesto, el expediente conserva lo que se envió).
    agencia_id:        Mapped[int] = mapped_column(ForeignKey("agencias_navieras.id", ondelete="RESTRICT"), index=True)
    agencia_nombre:    Mapped[str] = mapped_column(String(200))
    creada_por_id:     Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    tipo_tramite_id:   Mapped[int] = mapped_column(ForeignKey("tipos_tramite.id", ondelete="RESTRICT"), index=True)
    puesto_control_id: Mapped[int] = mapped_column(ForeignKey("puestos_control.id", ondelete="RESTRICT"), index=True)
    puesto_nombre:     Mapped[str] = mapped_column(String(200))

    titulo:               Mapped[str]  = mapped_column(String(255))
    fecha_operacion:      Mapped[date] = mapped_column(Date)
    cantidad_tripulantes: Mapped[int]  = mapped_column(Integer)

    # Buque — `bandera` es el código de país (catálogo `paises`)
    nombre_buque: Mapped[str | None] = mapped_column(String(255))
    imo:          Mapped[str | None] = mapped_column(String(20))
    bandera:      Mapped[str | None] = mapped_column(ForeignKey("paises.codigo", ondelete="RESTRICT"))

    # Campos que aplican según el tipo de trámite (ver TipoTramite.requiere_*)
    nombre_puerto:      Mapped[str | None] = mapped_column(String(255))
    puerto_desembarque: Mapped[str | None] = mapped_column(String(255))
    motivo:             Mapped[str | None] = mapped_column(Text)
    clinica_hospital:   Mapped[str | None] = mapped_column(String(255))
    observaciones:      Mapped[str | None] = mapped_column(Text)

    # ── Flujo ────────────────────────────────────────────────────────────────
    estado:         Mapped[str]      = mapped_column(String(20), default=EstadoSolicitud.EN_REVISION.value,
                                                     server_default=EstadoSolicitud.EN_REVISION.value, index=True)
    enviada_en:     Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)   # último envío a revisión
    veces_devuelta: Mapped[int]      = mapped_column(Integer, default=0, server_default="0")

    impedimentos_verificados:        Mapped[bool]            = mapped_column(Boolean, default=False, server_default="false")
    comentario_impedimentos:         Mapped[str | None]      = mapped_column(Text)
    impedimentos_verificados_en:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    impedimentos_verificados_por_id: Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    motivo_devolucion: Mapped[str | None]      = mapped_column(Text)
    plazo_correccion:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    aprobada_en:            Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    aprobada_por_id:        Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    observacion_aprobacion: Mapped[str | None]      = mapped_column(Text)
    vigente_hasta:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Código del QR del PDF: solo permite verificar la autorización, no abre el expediente.
    codigo_verificacion:    Mapped[str | None]      = mapped_column(String(64), unique=True, index=True)

    negada_en:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    negada_por_id:   Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    motivo_negacion: Mapped[str | None]      = mapped_column(Text)

    finalizada_en:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizada_por_id:       Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comentario_finalizacion: Mapped[str | None]      = mapped_column(Text)
    # La operación puede empezar en un puerto y terminar en otro: el puesto de
    # control indica dónde terminó al finalizar (el nombre, como foto).
    puesto_finalizacion_id:     Mapped[int | None] = mapped_column(ForeignKey("puestos_control.id", ondelete="RESTRICT"))
    puesto_finalizacion_nombre: Mapped[str | None] = mapped_column(String(200))

    expirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # `foreign_keys` explícito: la tabla tiene varias FK hacia users.
    creada_por:   Mapped["Usuario"]        = relationship("Usuario", foreign_keys=[creada_por_id], lazy="selectin")  # noqa: F821
    tipo_tramite: Mapped["TipoTramite"]    = relationship("TipoTramite", lazy="selectin")  # noqa: F821
    puesto:       Mapped["PuestoControl"]  = relationship(  # noqa: F821
        "PuestoControl", foreign_keys=[puesto_control_id], lazy="selectin",
    )
    agencia:      Mapped["AgenciaNaviera"] = relationship("AgenciaNaviera", lazy="selectin")  # noqa: F821

    # `passive_deletes`: las FK hijas son ON DELETE CASCADE en la BD, así que al
    # borrar no hace falta cargar las colecciones.
    tripulantes: Mapped[list["TripulanteSolicitud"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", passive_deletes=True,
        order_by="TripulanteSolicitud.orden",
    )
    documentos: Mapped[list["DocumentoSolicitud"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", passive_deletes=True,
        order_by="DocumentoSolicitud.id",
    )
    # Sin delete-orphan: los eventos se agregan por `solicitud_id` sin pasar por
    # la colección, y nunca se quitan sueltos (el historial no se edita).
    eventos: Mapped[list["EventoSolicitud"]] = relationship(
        back_populates="solicitud", cascade="all", passive_deletes=True,
        order_by="EventoSolicitud.id",
    )
    # Foto del checklist con el que se envió o corrigió por última vez: el
    # expediente se evalúa contra ella, no contra el catálogo de hoy.
    casillas: Mapped[list["CasillaSolicitud"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", passive_deletes=True,
        order_by="CasillaSolicitud.orden",
    )


class TripulanteSolicitud(Base):
    """Un tripulante dentro de una solicitud.

    `es_panameno` y `nacionalidad_restringida` se derivan de la nacionalidad
    al guardar (la segunda es una foto del catálogo en ese momento, para que
    un cambio posterior del catálogo no altere solicitudes ya enviadas).
    """
    __tablename__ = "solicitud_tripulantes"
    __table_args__ = (
        CheckConstraint("sexo IN ('M', 'F', 'X')", name="ck_solicitud_tripulantes_sexo"),
        CheckConstraint(f"rango IN ({_valores(RangoMarino)})", name="ck_solicitud_tripulantes_rango"),
    )

    id:               Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    solicitud_id:     Mapped[int]         = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), index=True)
    nombre:           Mapped[str]         = mapped_column(String(150))
    apellido:         Mapped[str]         = mapped_column(String(150))
    fecha_nacimiento: Mapped[date]        = mapped_column(Date)
    pais_nacimiento:  Mapped[str]         = mapped_column(ForeignKey("paises.codigo", ondelete="RESTRICT"))
    nacionalidad:     Mapped[str]         = mapped_column(ForeignKey("paises.codigo", ondelete="RESTRICT"))
    sexo:             Mapped[str]         = mapped_column(String(1))
    pasaporte:        Mapped[str]         = mapped_column(String(100))
    pasaporte_expira: Mapped[date]        = mapped_column(Date)
    libreta_marino:   Mapped[str | None]  = mapped_column(String(100))   # seamanbook
    libreta_expira:   Mapped[date | None] = mapped_column(Date)
    rango:            Mapped[str]         = mapped_column(String(20))
    ocupacion:        Mapped[str]         = mapped_column(String(150))
    es_panameno:      Mapped[bool]        = mapped_column(Boolean, default=False, server_default="false")
    nacionalidad_restringida: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Verificación de impedimentos (SIMPLUS) de esta persona: None = sin verificar.
    # Es información interna del SNM: la agencia no la ve.
    con_impedimento:  Mapped[bool | None] = mapped_column(Boolean)
    orden:            Mapped[int]         = mapped_column(Integer, default=0, server_default="0")
    created_at:       Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())

    solicitud: Mapped["Solicitud"] = relationship(back_populates="tripulantes")
    # Sin delete-orphan: un documento de alcance "solicitud" no tiene
    # tripulante, y con delete-orphan SQLAlchemy lo trataría como huérfano.
    # Al borrar el tripulante, la BD borra sus documentos (FK ON DELETE CASCADE).
    documentos: Mapped[list["DocumentoSolicitud"]] = relationship(
        back_populates="tripulante", cascade="all", passive_deletes=True,
    )
    # Igual que los documentos: sin delete-orphan (hay casillas de la solicitud,
    # sin tripulante). La relación ordena los borrados: casillas antes que el tripulante.
    casillas: Mapped[list["CasillaSolicitud"]] = relationship(
        back_populates="tripulante", cascade="all", passive_deletes=True,
    )
    pais_nacimiento_ref: Mapped["Pais"] = relationship("Pais", foreign_keys=[pais_nacimiento], lazy="selectin", viewonly=True)  # noqa: F821
    nacionalidad_ref:    Mapped["Pais"] = relationship("Pais", foreign_keys=[nacionalidad], lazy="selectin", viewonly=True)  # noqa: F821

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def porta_libreta(self) -> bool:
        return self.rango in RANGOS_CON_LIBRETA


class DocumentoSolicitud(Base):
    """Un archivo del expediente. `documento_id` es la casilla del checklist
    que cubre (nulo = documento adicional); `tripulante_id` solo va cuando el
    documento es de alcance "marino"."""
    __tablename__ = "solicitud_documentos"

    id:                Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    solicitud_id:      Mapped[int]        = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), index=True)
    tripulante_id:     Mapped[int | None] = mapped_column(ForeignKey("solicitud_tripulantes.id", ondelete="CASCADE"), index=True)
    documento_id:      Mapped[int | None] = mapped_column(ForeignKey("documentos_requeridos.id", ondelete="RESTRICT"), index=True)
    nombre_original:   Mapped[str]        = mapped_column(String(500))
    nombre_almacenado: Mapped[str]        = mapped_column(String(500))
    ruta:              Mapped[str]        = mapped_column(String(1000))   # relativa a STORAGE_PATH
    tipo_mime:         Mapped[str | None] = mapped_column(String(255))
    tamano:            Mapped[int]        = mapped_column(BigInteger)
    subido_por_id:     Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at:        Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    solicitud:  Mapped["Solicitud"]                  = relationship(back_populates="documentos")
    tripulante: Mapped["TripulanteSolicitud | None"] = relationship(back_populates="documentos")
    documento:  Mapped["DocumentoRequerido | None"]  = relationship("DocumentoRequerido", lazy="selectin", viewonly=True)  # noqa: F821


class CasillaSolicitud(Base):
    """Una casilla del checklist con el que se envió (o corrigió por última
    vez) la solicitud: qué documento se exigía y, si es por tripulante, de
    quién. Una solicitud se juzga con las reglas que regían al enviarla; si el
    catálogo cambia después, sus casillas no cambian (una corrección se valida
    con las reglas del día y vuelve a tomar la foto). Como `nacionalidad_restringida`
    de los tripulantes."""
    __tablename__ = "solicitud_casillas"

    id:            Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    solicitud_id:  Mapped[int]        = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), index=True)
    documento_id:  Mapped[int]        = mapped_column(ForeignKey("documentos_requeridos.id", ondelete="RESTRICT"))
    tripulante_id: Mapped[int | None] = mapped_column(ForeignKey("solicitud_tripulantes.id", ondelete="CASCADE"), index=True)
    orden:         Mapped[int]        = mapped_column(Integer, default=0, server_default="0")

    solicitud:  Mapped["Solicitud"]                  = relationship(back_populates="casillas")
    tripulante: Mapped["TripulanteSolicitud | None"] = relationship(back_populates="casillas")
    documento:  Mapped["DocumentoRequerido"]         = relationship("DocumentoRequerido", lazy="selectin", viewonly=True)  # noqa: F821


class EventoSolicitud(Base):
    """Historial: cada cambio de estado y cada comentario, con fecha/hora y el
    usuario (nombre guardado como foto: el historial no cambia si luego se
    renombra o elimina la cuenta)."""
    __tablename__ = "solicitud_eventos"

    id:              Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    solicitud_id:    Mapped[int]        = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), index=True)
    tipo:            Mapped[str]        = mapped_column(String(30))
    estado_anterior: Mapped[str | None] = mapped_column(String(20))
    estado_nuevo:    Mapped[str | None] = mapped_column(String(20))
    comentario:      Mapped[str | None] = mapped_column(Text)
    usuario_id:      Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    usuario_nombre:  Mapped[str | None] = mapped_column(String(255))
    creado_en:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    solicitud: Mapped["Solicitud"] = relationship(back_populates="eventos")
