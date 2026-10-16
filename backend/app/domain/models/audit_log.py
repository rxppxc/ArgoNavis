from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database import Base
from datetime import datetime
import enum


class AccionAuditoria(str, enum.Enum):
    LOGIN_EXITOSO           = "LOGIN_EXITOSO"
    LOGIN_FALLIDO           = "LOGIN_FALLIDO"
    CERRAR_SESION           = "CERRAR_SESION"
    SESION_EXPIRADA         = "SESION_EXPIRADA"
    # Legado: acciones del storage suelto y de una función de chat, ya
    # retirados. Existen en el tipo de la BD y en registros viejos; se
    # conservan solo para poder leerlos en la bitácora.
    TRANSFERENCIA_CREADA    = "TRANSFERENCIA_CREADA"
    TRANSFERENCIA_ELIMINADA = "TRANSFERENCIA_ELIMINADA"
    DESCARGA_REALIZADA      = "DESCARGA_REALIZADA"
    CHAT_CONSULTA           = "CHAT_CONSULTA"

    # Flujo de Autorizaciones Marítimas
    SOLICITUD_CREADA         = "SOLICITUD_CREADA"
    SOLICITUD_CONSULTADA     = "SOLICITUD_CONSULTADA"
    SOLICITUD_CORREGIDA      = "SOLICITUD_CORREGIDA"
    IMPEDIMENTOS_REGISTRADOS = "IMPEDIMENTOS_REGISTRADOS"
    SOLICITUD_DEVUELTA       = "SOLICITUD_DEVUELTA"
    SOLICITUD_APROBADA       = "SOLICITUD_APROBADA"
    SOLICITUD_NEGADA         = "SOLICITUD_NEGADA"
    SOLICITUD_COMENTADA      = "SOLICITUD_COMENTADA"
    SOLICITUD_FINALIZADA     = "SOLICITUD_FINALIZADA"
    SOLICITUD_EXPIRADA       = "SOLICITUD_EXPIRADA"
    AUTORIZACION_DESCARGADA  = "AUTORIZACION_DESCARGADA"
    AUTORIZACION_VERIFICADA  = "AUTORIZACION_VERIFICADA"
    DOCUMENTO_VISTO          = "DOCUMENTO_VISTO"
    DOCUMENTO_DESCARGADO     = "DOCUMENTO_DESCARGADO"

    # Cuentas
    CONTRASENA_CAMBIADA     = "CONTRASENA_CAMBIADA"
    CONTRASENA_RESTABLECIDA = "CONTRASENA_RESTABLECIDA"
    CUENTA_BLOQUEADA        = "CUENTA_BLOQUEADA"

    # Administración
    USUARIO_CREADO      = "USUARIO_CREADO"
    USUARIO_ACTUALIZADO = "USUARIO_ACTUALIZADO"
    USUARIO_ELIMINADO   = "USUARIO_ELIMINADO"
    ROL_CREADO          = "ROL_CREADO"
    ROL_ACTUALIZADO     = "ROL_ACTUALIZADO"
    ROL_ELIMINADO       = "ROL_ELIMINADO"
    PERMISO_CREADO      = "PERMISO_CREADO"
    PERMISO_ACTUALIZADO = "PERMISO_ACTUALIZADO"
    PERMISO_ELIMINADO   = "PERMISO_ELIMINADO"
    PUESTO_CREADO       = "PUESTO_CREADO"
    PUESTO_ACTUALIZADO  = "PUESTO_ACTUALIZADO"
    PUESTO_ELIMINADO    = "PUESTO_ELIMINADO"
    AGENCIA_CREADA      = "AGENCIA_CREADA"
    AGENCIA_ACTUALIZADA = "AGENCIA_ACTUALIZADA"
    AGENCIA_ELIMINADA   = "AGENCIA_ELIMINADA"
    PAIS_ACTUALIZADO    = "PAIS_ACTUALIZADO"


class RegistroAuditoria(Base):
    __tablename__ = "audit_logs"

    id:        Mapped[int]             = mapped_column(Integer, primary_key=True, index=True)
    user_id:   Mapped[int | None]      = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username:  Mapped[str | None]      = mapped_column(String(100))
    accion:    Mapped[AccionAuditoria] = mapped_column(SAEnum(AccionAuditoria, name="accionauditoria"))
    detalle:   Mapped[dict | None]     = mapped_column(JSON, nullable=True)
    ip:        Mapped[str | None]      = mapped_column(String(45))
    agente:    Mapped[str | None]      = mapped_column(String(500))
    creado_en: Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
