"""Cola de salida de los avisos por correo (`correos_salida`).

Cada aviso se guarda en la misma transacción que la operación que lo genera: si
la operación no se confirma, el aviso no sale; si se confirma, no se pierde
aunque el servidor de correo esté caído o el backend se reinicie. Lo envía y lo
reintenta `infrastructure/cola_correos.py`.
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class EstadoCorreo(str, enum.Enum):
    PENDIENTE = "pendiente"   # por enviar, o por reintentar en `proximo_intento`
    ENVIADO   = "enviado"
    FALLIDO   = "fallido"     # se agotaron los reintentos, o el mensaje no se pudo armar


class CorreoSalida(Base):
    __tablename__ = "correos_salida"
    __table_args__ = (
        CheckConstraint("estado IN ('pendiente', 'enviado', 'fallido')", name="ck_correos_salida_estado"),
        # Lo que busca la tarea de correos: los pendientes que ya tocan.
        Index("ix_correos_salida_pendientes", "proximo_intento", postgresql_where=text("estado = 'pendiente'")),
    )

    id:              Mapped[int]             = mapped_column(Integer, primary_key=True)
    numero:          Mapped[str]             = mapped_column(String(20))    # de la solicitud: para buscar sus avisos
    asunto:          Mapped[str]             = mapped_column(String(300))
    aviso:           Mapped[dict]            = mapped_column(JSON)          # el Aviso completo, con sus destinatarios
    estado:          Mapped[str]             = mapped_column(String(10), default=EstadoCorreo.PENDIENTE.value)
    intentos:        Mapped[int]             = mapped_column(Integer, default=0)
    proximo_intento: Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_error:    Mapped[str | None]      = mapped_column(String(500))
    creado_en:       Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    enviado_en:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
