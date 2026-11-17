"""¿La base tiene todo lo que usa el código? Lo revisa el arranque (main.py).

El 2026-11-17 el código se puso al día y la base de desarrollo no (faltaba correr
migrate.bat): cada pedido respondía «Error interno del servidor» y la causa («no
existe la columna solicitudes.subir_y_bajar») solo estaba en el log, pedido por
pedido. Ahora el arranque compara la base con el ORM y, si le falta algo, lo dice en
el log con qué hacer; mientras tanto la API responde 503 con el motivo
(`EsquemaAlDia`, api/middleware.py) y /api/health, «base de datos sin migrar».

Se compara con el catálogo de PostgreSQL y no con `alembic_version`, que la cuenta de
la aplicación no puede leer (permisos_bd.py): así funciona con cualquier cuenta. Solo
mira lo que falta (tablas, columnas, tipos enum y sus valores): una base más nueva que
el código, como al volver a una versión anterior, no es una falla."""
import asyncio
import logging

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.infrastructure.database import Base

logger = logging.getLogger(__name__)

_ESPERA_S = 10     # una base que no contesta no frena el arranque más que esto
_NOMBRADOS = 5     # en el log, los primeros; el resto, contado

# Las tablas que el ORM alcanza por su nombre: las visibles en el search_path de la conexión.
_COLUMNAS = text("""
    SELECT c.relname, a.attname
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE c.relkind IN ('r', 'p') AND pg_catalog.pg_table_is_visible(c.oid)
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
""")
_VALORES_ENUM = text("""
    SELECT t.typname, e.enumlabel
    FROM pg_catalog.pg_type t
    JOIN pg_catalog.pg_enum e ON e.enumtypid = t.oid
    WHERE pg_catalog.pg_type_is_visible(t.oid)
""")


async def faltantes_del_esquema(conexion: AsyncConnection, metadatos: MetaData | None = None) -> list[str]:
    """Lo que el ORM (`metadatos`, por defecto el de la aplicación) usa y la base no
    tiene, en palabras: «la tabla X», «la columna T.C», «el tipo E», «el valor V del tipo E»."""
    metadatos = Base.metadata if metadatos is None else metadatos
    columnas: dict[str, set[str]] = {}
    for tabla, columna in await conexion.execute(_COLUMNAS):
        columnas.setdefault(tabla, set()).add(columna)
    valores: dict[str, set[str]] = {}
    for tipo, valor in await conexion.execute(_VALORES_ENUM):
        valores.setdefault(tipo, set()).add(valor)

    faltan: list[str] = []
    enums: dict[str, list[str]] = {}
    for tabla in metadatos.sorted_tables:
        if tabla.name not in columnas:
            faltan.append(f"la tabla {tabla.name}")
        else:
            faltan += [f"la columna {tabla.name}.{c.name}" for c in tabla.columns if c.name not in columnas[tabla.name]]
        for c in tabla.columns:
            if isinstance(c.type, SAEnum) and c.type.native_enum and c.type.name:
                enums.setdefault(c.type.name, list(c.type.enums))
    for tipo, esperados in sorted(enums.items()):
        if tipo not in valores:
            faltan.append(f"el tipo {tipo}")
        else:
            faltan += [f"el valor {v} del tipo {tipo}" for v in esperados if v not in valores[tipo]]
    return faltan


def mensaje_esquema_atrasado(faltantes: list[str]) -> str:
    """Para el log del arranque: qué le falta a la base y qué hacer."""
    nombrados = ", ".join(faltantes[:_NOMBRADOS])
    if len(faltantes) > _NOMBRADOS:
        nombrados += f" y {len(faltantes) - _NOMBRADOS} más"
    return (f"La base de datos no está al día con el código: le falta {nombrados}. "
            "Corre migrate.bat (en Docker lo hace el contenedor al arrancar: alembic upgrade head) "
            "y vuelve a levantar el backend. Mientras tanto, la API responde 503.")


async def revisar_esquema(motor: AsyncEngine, metadatos: MetaData | None = None) -> list[str]:
    """Lo que le falta a la base ([] si nada) y, si falta algo, el error en el log.
    Si la base no responde, [] y un aviso: no impide arrancar (/api/health lo dice)."""
    async def revisar() -> list[str]:
        async with motor.connect() as conexion:
            return await faltantes_del_esquema(conexion, metadatos)

    try:
        faltantes = await asyncio.wait_for(revisar(), timeout=_ESPERA_S)
    except Exception as exc:   # cualquier falla de la base es «no se pudo revisar»; el motivo, al log
        logger.warning("No se pudo revisar el esquema de la base al arrancar (%s): "
                       "se revisa otra vez al volver a levantar el backend.", type(exc).__name__)
        return []
    if faltantes:
        logger.error(mensaje_esquema_atrasado(faltantes))
    return faltantes
