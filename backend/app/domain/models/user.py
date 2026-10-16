from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database import Base
import enum
import typing

if typing.TYPE_CHECKING:
    from app.domain.models.catalogo import AgenciaNaviera
    from app.domain.models.rol import Rol


class TipoUsuario(str, enum.Enum):
    AD    = "ad"
    LOCAL = "local"


class EstadoUsuario(str, enum.Enum):
    ACTIVO   = "active"
    INACTIVO = "inactive"


class Usuario(Base):
    __tablename__ = "users"

    id:        Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    username:  Mapped[str]           = mapped_column(String(100), unique=True, nullable=False, index=True)
    name:      Mapped[str | None]    = mapped_column(String(150))
    last_name: Mapped[str | None]    = mapped_column(String(150))
    email:     Mapped[str | None]    = mapped_column(String(255))
    guid:      Mapped[str | None]    = mapped_column(String(100), unique=True)
    user_type: Mapped[TipoUsuario]   = mapped_column(SAEnum(TipoUsuario),  default=TipoUsuario.AD)
    status:    Mapped[EstadoUsuario] = mapped_column(SAEnum(EstadoUsuario), default=EstadoUsuario.ACTIVO)
    rol_id:    Mapped[int | None]    = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Usuarios de una agencia naviera: comparten las solicitudes de su agencia.
    agencia_id: Mapped[int | None] = mapped_column(
        ForeignKey("agencias_navieras.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ── Cuenta local (user_type=LOCAL): contraseña propia del sistema ────────
    # Las cuentas AD no usan estos campos: la contraseña y su política viven en
    # el Active Directory.
    password_hash:         Mapped[str | None]      = mapped_column(String(255))
    intentos_fallidos:     Mapped[int]             = mapped_column(Integer, default=0, server_default="0")
    bloqueado_hasta:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    debe_cambiar_password: Mapped[bool]            = mapped_column(Boolean, default=False, server_default="false")

    # Los tokens emitidos antes de este momento ya no valen (cierre de sesión,
    # cambio o restablecimiento de contraseña). NULL = ningún cierre registrado.
    sesiones_validas_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rol_personalizado: Mapped["Rol | None"]            = relationship("Rol", lazy="selectin")
    agencia:           Mapped["AgenciaNaviera | None"] = relationship(
        "AgenciaNaviera", back_populates="usuarios", lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.name, self.last_name])) or self.username
