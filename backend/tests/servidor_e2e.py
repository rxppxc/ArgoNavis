"""Backend para el recorrido completo del frontend (Playwright: frontend/e2e).

Crea la BD `argonavis_e2e` en el servidor de TEST_DATABASE_URL o DATABASE_URL
(la de desarrollo no se toca), la migra y siembra una agencia, un puesto y una
cuenta local por rol. Levanta la API en 127.0.0.1:8001 sin correos ni límite de
peticiones. Si quedó la BD de una corrida interrumpida, la borra al empezar.

Lo arranca Playwright (playwright.config.ts) y, al terminar, lo vuelve a llamar
con --limpiar para borrar la BD (en Windows corta el servidor sin dejarlo cerrar).
A mano:
    cd backend
    venv\\Scripts\\python tests\\servidor_e2e.py [--limpiar]
"""
import asyncio
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent.parent
PUERTO = int(os.environ.get("E2E_PUERTO_API", "8001"))
URL_WEB = os.environ.get("E2E_URL_WEB", "http://localhost:5174")
NOMBRE_BD = "argonavis_e2e"
STORAGE = Path(tempfile.gettempdir()) / "argonavis_e2e_documentos"

# Solo existen en la BD temporal. Espejo de frontend/e2e/datos.ts.
CLAVE = "Prueba-E2e-2026!"
AGENCIA = "Agencia E2E, S.A."
PUESTO = "Puesto E2E"
CUENTAS = [  # usuario, nombre, apellido, rol, ¿de la agencia?, ¿del puesto?
    ("e2e.agencia", "Laura", "Agencia", "Naviera", True, False),
    ("e2e.ucvmm", "Ricardo", "Revisor", "Sector Pacífico", False, False),
    ("e2e.puesto", "Ana", "Puesto", "Puesto de Control", False, True),
    ("e2e.admin", "José", "Administrador", "Administrador", False, False),
]

# ── Entorno (antes de importar la app: la configuración se lee una sola vez) ──

_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
if not _url:
    raise SystemExit("Define TEST_DATABASE_URL o DATABASE_URL en backend/.env.")
_base = _url.rpartition("/")[0]
URL_ADMIN = f"{_base}/postgres".replace("postgresql+asyncpg://", "postgresql://")

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
    "APP_URL": URL_WEB,
    "FRONTEND_URL": URL_WEB,
})
sys.path.insert(0, str(BACKEND))


def _sql_admin(sentencia: str) -> None:
    with psycopg.connect(URL_ADMIN, autocommit=True) as cx:
        cx.execute(sentencia)


def limpiar() -> None:
    _sql_admin(f'DROP DATABASE IF EXISTS "{NOMBRE_BD}" WITH (FORCE)')
    shutil.rmtree(STORAGE, ignore_errors=True)


def preparar_bd() -> None:
    limpiar()
    _sql_admin(f'CREATE DATABASE "{NOMBRE_BD}"')
    # -I: sin la carpeta actual en sys.path, para que backend/alembic no tape al paquete.
    migracion = subprocess.run(
        [sys.executable, "-I", "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=os.environ.copy(),
        capture_output=True, text=True,
    )
    if migracion.returncode:
        raise SystemExit(migracion.stderr[-3000:])


async def sembrar() -> None:
    from sqlalchemy import insert, select

    from app.core.security import hashear_password
    from app.domain.models.catalogo import AgenciaNaviera, PuestoControl, usuarios_puestos
    from app.domain.models.rol import Rol
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal, motor_bd

    async with SesionLocal() as s:
        agencia, puesto = AgenciaNaviera(nombre=AGENCIA), PuestoControl(nombre=PUESTO)
        s.add_all([agencia, puesto])
        await s.flush()
        clave = hashear_password(CLAVE)
        for usuario, nombre, apellido, rol, de_agencia, de_puesto in CUENTAS:
            rol_id = (await s.execute(select(Rol.id).where(Rol.nombre == rol))).scalar_one()
            u = Usuario(username=usuario, name=nombre, last_name=apellido, user_type=TipoUsuario.LOCAL,
                        password_hash=clave, rol_id=rol_id, agencia_id=agencia.id if de_agencia else None)
            s.add(u)
            await s.flush()
            if de_puesto:
                await s.execute(insert(usuarios_puestos).values(usuario_id=u.id, puesto_id=puesto.id))
        await s.commit()
    await motor_bd.dispose()


def main() -> None:
    if "--limpiar" in sys.argv:
        limpiar()
        return
    preparar_bd()
    asyncio.run(sembrar())

    import uvicorn

    from app.core.rate_limit import limiter
    from app.main import aplicacion

    limiter.enabled = False
    try:
        uvicorn.run(aplicacion, host="127.0.0.1", port=PUERTO, log_level="warning")
    finally:
        limpiar()


if __name__ == "__main__":
    main()
