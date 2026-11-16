"""Lo común a los tres entornos con BD temporal (auditoría del 2026-11-14): las
pruebas (conftest.py), el backend del E2E (servidor_e2e.py) y la prueba de carga
(carga.py). Antes, cada uno tenía su copia de la lista de variables.

Sin efectos al importarlo: cada uno elige el nombre de su BD y cuándo crearla y
borrarla. Usa el servidor PostgreSQL de TEST_DATABASE_URL o el de DATABASE_URL del
.env; la BD de desarrollo no se toca.
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent.parent


def servidor_bd() -> str:
    """La URL del servidor PostgreSQL, sin el nombre de la BD."""
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
    if not url:
        raise RuntimeError("Define TEST_DATABASE_URL o DATABASE_URL en backend/.env.")
    return url.rpartition("/")[0]


def url_admin(servidor: str) -> str:
    """La BD `postgres` del servidor, para crear y borrar las temporales (psycopg, sin asyncpg)."""
    return f"{servidor}/postgres".replace("postgresql+asyncpg://", "postgresql://")


def variables(url_bd: str, storage: Path, **extra: str) -> dict[str, str]:
    """Las variables de un backend de prueba: su BD y su carpeta, sin AD de verdad,
    sin correos, sin logs en archivo y sin tope de verificaciones. Se aplican antes
    de importar la app (la configuración se lee una sola vez). Si agregas una
    configuración que en las pruebas tenga que quedar apagada, va aquí."""
    return {
        "DATABASE_URL": url_bd,
        # Vacía: si el .env de desarrollo la trae, las migraciones irían a otra BD.
        "MIGRACIONES_DATABASE_URL": "",
        "STORAGE_PATH": str(storage),
        "APP_ENV": "test",
        "SECRET_KEY": secrets.token_urlsafe(32),
        "LDAP_HOST": "ldap.invalido", "LDAP_BASE_DN": "DC=prueba", "LDAP_BIND_USER": "x", "LDAP_BIND_PASSWORD": "x",
        "MAIL_HOST": "",
        "CORREO_UCVMM": "",
        "LOG_CARPETA": "",   # los logs no van a la carpeta del .env
        "PERMITIR_LOGIN_LOCAL": "true",
        "LIMITE_VERIFICACIONES_POR_MINUTO": "0",
        **extra,
    }


def sql_admin(admin: str, sentencia: str) -> None:
    """Una sentencia en la BD `postgres` (CREATE / DROP DATABASE, DROP ROLE)."""
    with psycopg.connect(admin, autocommit=True) as cx:
        cx.execute(sentencia)


def alembic(*argumentos: str, entorno: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Corre alembic en un proceso aparte, como en el despliegue. -I: sin la carpeta
    actual en sys.path, para que backend/alembic (las migraciones) no tape al
    paquete; y sin alembic.exe, que guarda la ruta del venv."""
    return subprocess.run(
        [sys.executable, "-I", "-m", "alembic", *argumentos], cwd=BACKEND, capture_output=True, text=True,
        env=entorno if entorno is not None else os.environ.copy(),
    )
