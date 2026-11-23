"""Boletas de recargo por atención fuera del horario laboral (2026-11-16).

Cuando UCVMM aprueba fuera del horario, la solicitud lleva un recargo
(`solicitudes.costo_fuera_de_horario`, guardado al aprobar). El SNM imprime una
boleta para cobrarlo y se la entrega a la agencia, que no la ve en el sistema.

La identifica el número de oficio que escribe el funcionario: único entre todas
las boletas, también las anuladas, sin distinguir mayúsculas. Como en un
talonario, una boleta mal hecha no se corrige ni se borra: se anula, con motivo,
y se genera otra con otro número. Hay una sola vigente por solicitud. La cuenta
de la aplicación no puede borrar filas de esta tabla (permisos_bd.TABLAS_SIN_BORRAR).
"""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base

if TYPE_CHECKING:   # solo para el verificador de tipos: en ejecución, las relaciones van por nombre
    from app.domain.models.solicitud import Solicitud
    from app.domain.models.user import Usuario

LARGO_NUMERO_OFICIO    = 40
LARGO_MOTIVO_ANULACION = 500


class BoletaRecargo(Base):
    __tablename__ = "boletas_recargo"
    __table_args__ = (
        # Los mismos de la revisión e5c1a7d3b902.
        Index("ux_boletas_recargo_numero", text("lower(numero_oficio)"), unique=True),
        Index("ux_boletas_recargo_vigente", "solicitud_id", unique=True, postgresql_where=text("anulada_en IS NULL")),
        CheckConstraint("(anulada_en IS NULL) = (motivo_anulacion IS NULL)", name="ck_boletas_recargo_anulacion"),
        CheckConstraint("monto > 0", name="ck_boletas_recargo_monto"),
    )

    id:               Mapped[int]             = mapped_column(Integer, primary_key=True)
    solicitud_id:     Mapped[int]             = mapped_column(ForeignKey("solicitudes.id", ondelete="RESTRICT"), index=True)
    numero_oficio:    Mapped[str]             = mapped_column(String(LARGO_NUMERO_OFICIO))
    # El recargo de la solicitud cuando se generó (foto).
    monto:            Mapped[Decimal]         = mapped_column(Numeric(8, 2))
    generada_en:      Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    generada_por_id:  Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    anulada_en:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por_id:   Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    motivo_anulacion: Mapped[str | None]      = mapped_column(String(LARGO_MOTIVO_ANULACION))

    generada_por: Mapped["Usuario | None"] = relationship(  # noqa: F821
        "Usuario", foreign_keys=[generada_por_id], lazy="selectin",
    )
    anulada_por:  Mapped["Usuario | None"] = relationship(  # noqa: F821
        "Usuario", foreign_keys=[anulada_por_id], lazy="selectin",
    )
    solicitud:    Mapped["Solicitud"] = relationship(back_populates="boletas")  # noqa: F821

    @property
    def vigente(self) -> bool:
        return self.anulada_en is None
