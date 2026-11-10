"""Catálogos de apoyo al flujo de Autorizaciones Marítimas.

  - `Sector`: Sector Pacífico y Sector Atlántico de UCVMM (2026-11-10). Cada
    puesto es de un sector; los revisores de UCVMM y los supervisores de sector
    quedan asignados a uno o más (tabla `usuarios_sectores`) y solo ven las
    solicitudes de los puestos de sus sectores. Su buzón recibe el aviso de
    cada solicitud nueva del sector.
  - `PuestoControl`: los puestos de Control Migratorio donde se realiza el
    trámite. Cada solicitud apunta a uno; los funcionarios del puerto quedan
    asignados a sus puestos (tabla `usuarios_puestos`) y solo ven/finalizan
    las autorizaciones de esos puestos.
  - `AgenciaNaviera`: las agencias que solicitan. Sus usuarios (users.agencia_id)
    comparten las solicitudes de la agencia: cualquiera puede verlas,
    corregirlas y descargar la autorización.
  - `Pais`: catálogo ISO 3166-1 alfa-3 (más los códigos ICAO de apátrida y
    Kosovo) para nacionalidad, país de nacimiento y bandera del buque. El
    admin marca aquí las nacionalidades restringidas: en Desembarque obligan a
    adjuntar el Formulario No. 6 de custodia, y en los trámites con
    `aviso_custodia` la aprobación avisa que se debe tramitar la custodia.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base


usuarios_puestos = Table(
    "usuarios_puestos",
    Base.metadata,
    Column("usuario_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("puesto_id", ForeignKey("puestos_control.id", ondelete="CASCADE"), primary_key=True),
)


usuarios_sectores = Table(
    "usuarios_sectores",
    Base.metadata,
    Column("usuario_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("sector_id", ForeignKey("sectores.id", ondelete="CASCADE"), primary_key=True),
)


class Sector(Base):
    __tablename__ = "sectores"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True)
    nombre:     Mapped[str]        = mapped_column(String(100), nullable=False, unique=True)
    # Buzón del sector: recibe el aviso de cada solicitud nueva o corregida de sus
    # puestos. Sin buzón, va al general (CORREO_UCVMM).
    correo:     Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes: al borrar el sector, la BD limpia `usuarios_sectores`.
    usuarios: Mapped[list["Usuario"]] = relationship(  # noqa: F821
        "Usuario", secondary=usuarios_sectores, order_by="Usuario.name", passive_deletes=True,
    )
    puestos: Mapped[list["PuestoControl"]] = relationship(
        "PuestoControl", back_populates="sector", order_by="PuestoControl.nombre",
    )


class PuestoControl(Base):
    __tablename__ = "puestos_control"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    nombre:     Mapped[str]        = mapped_column(String(200), nullable=False, unique=True)
    # El sector de UCVMM que revisa sus solicitudes (Pacífico o Atlántico).
    sector_id:  Mapped[int]        = mapped_column(
        ForeignKey("sectores.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    # Buzón institucional del puesto: recibe el aviso de cada autorización
    # aprobada, además de los funcionarios asignados.
    correo:     Mapped[str | None] = mapped_column(String(255))
    activo:     Mapped[bool]       = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes: al borrar el puesto, la BD limpia `usuarios_puestos`.
    usuarios: Mapped[list["Usuario"]] = relationship(  # noqa: F821
        "Usuario", secondary=usuarios_puestos, order_by="Usuario.name", passive_deletes=True,
    )
    sector: Mapped[Sector] = relationship(Sector, back_populates="puestos", lazy="selectin")


class AgenciaNaviera(Base):
    __tablename__ = "agencias_navieras"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    nombre:     Mapped[str]        = mapped_column(String(200), nullable=False, unique=True)
    # Buzón de la agencia: recibe los avisos de sus solicitudes, además de sus usuarios.
    correo:     Mapped[str | None] = mapped_column(String(255))
    activo:     Mapped[bool]       = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes: al borrar la agencia, la BD deja sus usuarios sin agencia (SET NULL).
    usuarios: Mapped[list["Usuario"]] = relationship(  # noqa: F821
        "Usuario", back_populates="agencia", order_by="Usuario.name", passive_deletes=True,
    )


class Pais(Base):
    __tablename__ = "paises"

    id:     Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(3), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    nacionalidad_restringida: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
