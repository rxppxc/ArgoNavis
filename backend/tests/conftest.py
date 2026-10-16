"""Entorno de pruebas: una BD PostgreSQL temporal (se crea al empezar y se
borra al terminar), migrada con Alembic, y el storage en una carpeta temporal.

Necesita un PostgreSQL accesible: usa el servidor de TEST_DATABASE_URL o, si
no está, el de DATABASE_URL del .env (con un nombre de BD aleatorio; la BD de
desarrollo no se toca). No se envían correos ni se aplica el rate limit.

    cd backend
    venv\\Scripts\\python -m pytest
"""
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent.parent

# ── Entorno (antes de importar la app: la configuración se lee una sola vez) ──

_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
if not _url:
    raise RuntimeError("Define TEST_DATABASE_URL o DATABASE_URL en backend/.env para correr las pruebas.")
_base, _, _ = _url.rpartition("/")
NOMBRE_BD = f"argonavis_pruebas_{secrets.token_hex(4)}"
URL_ADMIN = f"{_base}/postgres".replace("postgresql+asyncpg://", "postgresql://")
STORAGE   = Path(tempfile.mkdtemp(prefix="argonavis_documentos_pruebas_"))

os.environ.update({
    "DATABASE_URL": f"{_base}/{NOMBRE_BD}",
    "STORAGE_PATH": str(STORAGE),
    "APP_ENV": "test",
    "SECRET_KEY": secrets.token_urlsafe(32),
    "LDAP_HOST": "ldap.invalido", "LDAP_BASE_DN": "DC=prueba", "LDAP_BIND_USER": "x", "LDAP_BIND_PASSWORD": "x",
    "MAIL_HOST": "",
    "CORREO_UCVMM": "",
    "PERMITIR_LOGIN_LOCAL": "true",
    "LIMITE_VERIFICACIONES_POR_MINUTO": "0",
})
sys.path.insert(0, str(BACKEND))


def ejecutar_alembic(*argumentos: str, url: str | None = None) -> subprocess.CompletedProcess:
    """Corre alembic en un proceso aparte (como en el despliegue)."""
    entorno = os.environ.copy()
    if url:
        entorno["DATABASE_URL"] = url
    # -I: sin la carpeta actual en sys.path, para que backend/alembic (las
    # migraciones) no tape al paquete; y sin alembic.exe, que guarda la ruta del venv.
    return subprocess.run(
        [sys.executable, "-I", "-m", "alembic", *argumentos], cwd=BACKEND, capture_output=True, text=True,
        env=entorno,
    )


def crear_bd(nombre: str) -> None:
    with psycopg.connect(URL_ADMIN, autocommit=True) as cx:
        cx.execute(f'CREATE DATABASE "{nombre}"')


def borrar_bd(nombre: str) -> None:
    with psycopg.connect(URL_ADMIN, autocommit=True) as cx:
        cx.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


def url_bd(nombre: str) -> str:
    return f"{_base}/{nombre}"


@pytest.fixture(scope="session", autouse=True)
def base_de_datos():
    crear_bd(NOMBRE_BD)
    try:
        resultado = ejecutar_alembic("upgrade", "head")
        assert resultado.returncode == 0, resultado.stderr[-3000:]
        yield
    finally:
        borrar_bd(NOMBRE_BD)
        shutil.rmtree(STORAGE, ignore_errors=True)


# ── Cliente HTTP y usuarios de prueba ────────────────────────────────────────

@dataclass
class Actor:
    id:       int
    username: str
    headers:  dict[str, str]


@pytest.fixture(scope="session")
async def cliente(base_de_datos):
    import httpx
    from app.core.rate_limit import limiter
    from app.infrastructure.database import motor_bd
    from app.main import aplicacion

    limiter.enabled = False
    transporte = httpx.ASGITransport(app=aplicacion)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba/api/v1") as c:
        yield c
    await motor_bd.dispose()


async def crear_actor(
    rol: str | None, *, correo: str | None = None, agencia_id: int | None = None,
    password: str | None = None, prefijo: str = "u", ad: bool = False,
) -> Actor:
    """Crea una cuenta (local, o del AD con `ad`) con el rol dado y devuelve su token."""
    from sqlalchemy import select
    from app.core.security import crear_token_acceso, hashear_password
    from app.domain.models.rol import Rol
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal

    username = f"{prefijo}.{secrets.token_hex(3)}"
    async with SesionLocal() as s:
        rol_id = None
        if rol:
            rol_id = (await s.execute(select(Rol.id).where(Rol.nombre == rol))).scalar_one()
        u = Usuario(
            username=username, name=prefijo.capitalize(), last_name="Prueba", email=correo,
            user_type=TipoUsuario.AD if ad else TipoUsuario.LOCAL, rol_id=rol_id, agencia_id=agencia_id,
            password_hash=hashear_password(password) if password else None,
        )
        s.add(u)
        await s.commit()
        uid = u.id
    token = crear_token_acceso(subject=uid, extra={"username": username})
    return Actor(id=uid, username=username, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(scope="session")
async def admin(cliente) -> Actor:
    return await crear_actor("Administrador", correo="admin@prueba.pa", prefijo="admin")


@pytest.fixture(scope="session")
async def sysadmin(cliente) -> Actor:
    """Administración técnica: usuarios, roles y permisos (el Administrador ya no los gestiona)."""
    return await crear_actor("SysAdmin", correo="sysadmin@prueba.pa", prefijo="sysadmin")
