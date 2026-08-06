from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.infrastructure.database import Base
from datetime import datetime, timezone
import enum


class EstadoTransferencia(str, enum.Enum):
    ACTIVA    = "active"    # visible de inmediato para Sector Pacífico
    EXPIRADA  = "expired"   # venció por fecha o descargas
    ELIMINADA = "deleted"   # borrada lógicamente


class Transferencia(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        Index("ix_transfers_expires_at", "expires_at"),
        Index("ix_transfers_status",     "status"),
    )

    id:            Mapped[int]                    = mapped_column(Integer, primary_key=True, index=True)
    user_id:       Mapped[int]                    = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token:         Mapped[str]                    = mapped_column(String(64), unique=True, nullable=False, index=True)
    title:         Mapped[str | None]             = mapped_column(String(255))
    message:       Mapped[str | None]             = mapped_column(Text)
    recipient:     Mapped[str | None]              = mapped_column(String(255))
    expires_at:    Mapped[datetime | None]        = mapped_column(DateTime(timezone=True))
    downloads:     Mapped[int]                    = mapped_column(Integer, default=0)
    max_downloads: Mapped[int | None]             = mapped_column(Integer)
    status:        Mapped[str]                    = mapped_column(String(20), default="active", server_default="active", index=True)
    created_at:    Mapped[datetime]               = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:    Mapped[datetime]               = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    usuario:  Mapped["Usuario"]                     = relationship(back_populates="transferencias")
    archivos: Mapped[list["ArchivoTransferencia"]]  = relationship(back_populates="transferencia", cascade="all, delete-orphan")

    @property
    def files(self) -> list["ArchivoTransferencia"]:
        return self.archivos

    @property
    def is_expired(self) -> bool:
        if self.status != EstadoTransferencia.ACTIVA:
            return True
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return True
        if self.max_downloads and self.downloads >= self.max_downloads:
            return True
        return False

    @property
    def total_size(self) -> int:
        return sum(archivo.size for archivo in self.archivos)

    @property
    def sender(self) -> str | None:
        return self.usuario.full_name if self.usuario else None


class ArchivoTransferencia(Base):
    __tablename__ = "transfer_files"

    id:            Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    transfer_id:   Mapped[int]        = mapped_column(ForeignKey("transfers.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str]        = mapped_column(String(500), nullable=False)
    stored_name:   Mapped[str]        = mapped_column(String(500), nullable=False)
    path:          Mapped[str]        = mapped_column(String(1000), nullable=False)
    mime_type:     Mapped[str | None] = mapped_column(String(255))
    size:          Mapped[int]        = mapped_column(BigInteger, default=0)
    created_at:    Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    subido_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    es_original:   Mapped[bool]       = mapped_column(default=True, server_default="true")

    transferencia: Mapped["Transferencia"] = relationship(back_populates="archivos")
