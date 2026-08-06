from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.infrastructure.database import Base
from app.domain.models.user import Usuario
from app.domain.models.transfer import Transferencia, ArchivoTransferencia
from app.domain.models.audit_log import RegistroAuditoria  # noqa: F401
from app.domain.models.rol import Rol, Permiso, RolPermiso
from app.core.config import obtener_configuracion

configuracion = obtener_configuracion()
config = context.config
# Alembic necesita un driver síncrono; asyncpg es sólo para la app async
url_sync = configuracion.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
config.set_main_option("sqlalchemy.url", url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def ejecutar_migraciones_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_migraciones_online():
    conectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectable.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_migraciones_offline()
else:
    ejecutar_migraciones_online()
