from sqlalchemy import String, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database import Base
import enum
import typing

if typing.TYPE_CHECKING:
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
    # Solo se usa para usuarios user_type=LOCAL (cuentas de prueba sin AD,
    # ver ServicioAutenticacion.login). Se elimina junto con ese flujo antes
    # de pasar el sistema a producción.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    rol_id:    Mapped[int | None]    = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    transferencias: Mapped[list["Transferencia"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    rol_personalizado: Mapped["Rol | None"] = relationship("Rol", lazy="selectin")

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.name, self.last_name])) or self.username
