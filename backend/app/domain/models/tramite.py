"""Catálogo de trámites migratorios y sus documentos requeridos.

Modela el Formulario 3 del SNM — Solicitud de Autorización, que llena la
agencia naviera. Cada tipo de trámite exige una lista distinta de documentos.
(El Formulario 4, fuera del horario laboral, se retiró por ahora; la columna
`formulario` se conserva por si vuelve.)

El catálogo vive en BD (no como enum en código) a propósito: los requisitos
de un organismo público cambian por resolución administrativa. Hoy se
consulta en `/admin/tramites` y se ajusta con una migración; editarlo desde la
interfaz queda pendiente.
"""
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.infrastructure.database import Base
from datetime import datetime
import enum


class AlcanceDocumento(str, enum.Enum):
    """A qué nivel se adjunta el documento dentro de una solicitud."""
    SOLICITUD = "solicitud"   # uno solo para todo el expediente (ej. Lista de Tripulantes)
    MARINO    = "marino"      # uno por cada tripulante (ej. su pasaporte)


class CondicionDocumento(str, enum.Enum):
    """Cuándo se vuelve exigible el documento.

    Todas salvo `SIEMPRE` se evalúan en código contra los datos de la
    solicitud (ver ServicioTramite.construir_casillas).
    """
    SIEMPRE                  = "siempre"
    SOLO_PANAMENOS           = "solo_panamenos"            # Libreta de Marino en Embarque
    NACIONALIDAD_RESTRINGIDA = "nacionalidad_restringida"  # Form. No. 6 de custodia


class TipoTramite(Base):
    """Un tipo de trámite del catálogo (ej. Embarque, Cambio de Puerto)."""
    __tablename__ = "tipos_tramite"

    id:         Mapped[int]       = mapped_column(Integer, primary_key=True, index=True)
    codigo:     Mapped[str]       = mapped_column(String(50), nullable=False, unique=True, index=True)
    nombre:     Mapped[str]       = mapped_column(String(200), nullable=False)
    formulario: Mapped[str]       = mapped_column(String(20), nullable=False, index=True)   # hoy siempre "formulario_3"

    # Campos extra que el formulario pide según el trámite. Determinan qué
    # inputs muestra el frontend y qué valida el backend al crear la solicitud.
    requiere_buque:              Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requiere_puerto:             Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requiere_puerto_desembarque: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requiere_motivo:             Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requiere_clinica:            Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Si el trámite exige pasaporte y seamanbook vigentes a la fecha de la
    # operación (Embarque, Visita médica y Shore Pass, según UCVMM).
    valida_vigencia: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Rangos de tripulante que admite el trámite (nulo = cualquiera). La
    # Autorización de Técnico, Superintendente o Supernumerario solo admite esos tres.
    rangos_permitidos: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    # Si el proceso del trámite dice que, al aprobar, se informa a la agencia
    # que debe tramitar la custodia de los tripulantes de nacionalidad
    # restringida (Desembarque, Urgencias, Renovación y Shore Pass).
    aviso_custodia: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Cuándo se usa el trámite, en una línea (tarjetas del paso 1 de «Nueva solicitud»).
    descripcion: Mapped[str | None] = mapped_column(String(300))
    nota:       Mapped[str | None] = mapped_column(Text)   # aviso al usuario (ej. prórroga de extensión)
    orden:      Mapped[int]        = mapped_column(Integer, default=0)
    activo:     Mapped[bool]       = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    documentos: Mapped[list["TramiteDocumento"]] = relationship(
        "TramiteDocumento", back_populates="tipo_tramite",
        cascade="all, delete-orphan", order_by="TramiteDocumento.orden",
    )


class DocumentoRequerido(Base):
    """Catálogo maestro de documentos que pueden exigirse en un trámite."""
    __tablename__ = "documentos_requeridos"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    codigo:      Mapped[str]        = mapped_column(String(50), nullable=False, unique=True, index=True)
    nombre:      Mapped[str]        = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    # Solo se exige a tripulantes que portan seamanbook (rango Marino): los
    # militares, técnicos, supernumerarios y superintendentes no lo tienen.
    requiere_libreta: Mapped[bool]  = mapped_column(Boolean, default=False, server_default="false")
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    tramites: Mapped[list["TramiteDocumento"]] = relationship(
        "TramiteDocumento", back_populates="documento", cascade="all, delete-orphan"
    )


class TramiteDocumento(Base):
    """Puente: qué documentos exige cada trámite, con qué alcance y condición."""
    __tablename__ = "tramite_documentos"
    __table_args__ = (
        UniqueConstraint("tipo_tramite_id", "documento_id", name="uq_tramite_documento"),
    )

    id:              Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tipo_tramite_id: Mapped[int] = mapped_column(ForeignKey("tipos_tramite.id", ondelete="CASCADE"), nullable=False, index=True)
    documento_id:    Mapped[int] = mapped_column(ForeignKey("documentos_requeridos.id", ondelete="CASCADE"), nullable=False, index=True)

    alcance:   Mapped[str] = mapped_column(String(20), nullable=False, default=AlcanceDocumento.SOLICITUD.value)
    condicion: Mapped[str] = mapped_column(String(30), nullable=False, default=CondicionDocumento.SIEMPRE.value)
    orden:     Mapped[int] = mapped_column(Integer, default=0)

    tipo_tramite: Mapped["TipoTramite"]         = relationship("TipoTramite", back_populates="documentos")
    documento:    Mapped["DocumentoRequerido"]  = relationship("DocumentoRequerido", back_populates="tramites")
