"""La cuenta de la base de datos con la que entra la aplicación, con lo justo
(infrastructure/permisos_bd.py, 2026-11-08). Antes, en Docker, la aplicación
entraba como superusuario: una inyección SQL tenía poder total sobre la base y
podía ejecutar programas en el servidor (COPY ... TO PROGRAM)."""
import os
import secrets

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege
from sqlalchemy.engine import URL, make_url

from app.domain.models.audit_log import AccionAuditoria, RegistroAuditoria
from app.domain.models.user import TipoUsuario, Usuario
from app.infrastructure.database import SesionLocal
from app.infrastructure.permisos_bd import aplicar
from app.main import aplicacion  # noqa: F401  (registra todos los modelos antes de usar el ORM)

pytestmark = pytest.mark.asyncio(loop_scope="session")

URL_DUENA = os.environ["DATABASE_URL"]   # la BD temporal de las pruebas (conftest)


def _psycopg(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def _url_de(rol: str, clave: str) -> str:
    return make_url(URL_DUENA).set(username=rol, password=clave).render_as_string(hide_password=False)


@pytest.fixture
def rol_app(base_de_datos):
    rol = f"argonavis_app_prueba_{secrets.token_hex(3)}"
    yield rol
    with psycopg.connect(_psycopg(URL_DUENA), autocommit=True) as cx:
        if cx.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (rol,)).fetchone():
            cx.execute(f'DROP OWNED BY "{rol}"')
            cx.execute(f'DROP ROLE "{rol}"')


def _puede(cx: psycopg.Connection, tabla: str, privilegio: str) -> bool:
    return cx.execute("SELECT has_table_privilege(current_user, %s, %s)", (tabla, privilegio)).fetchone()[0]


async def test_la_cuenta_de_la_aplicacion_tiene_lo_justo(rol_app):
    url = _url_de(rol_app, secrets.token_hex(12))
    assert "creada" in aplicar(URL_DUENA, url)
    with psycopg.connect(_psycopg(url), autocommit=True) as cx:
        atributos = cx.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user").fetchone()
        assert atributos == (False, False, False)
        for tabla in ("solicitudes", "solicitud_tripulantes", "users", "correos_salida", "solicitud_documentos"):
            assert all(_puede(cx, tabla, p) for p in ("SELECT", "INSERT", "UPDATE", "DELETE")), tabla
        for tabla in ("audit_logs", "solicitud_eventos"):
            assert _puede(cx, tabla, "SELECT") and _puede(cx, tabla, "INSERT"), tabla
            assert not any(_puede(cx, tabla, p) for p in ("UPDATE", "DELETE", "TRUNCATE")), \
                f"{tabla}: la bitácora y el historial solo se agregan"
        assert not _puede(cx, "alembic_version", "SELECT")

        marca = f"permisos.{secrets.token_hex(3)}"
        cx.execute("INSERT INTO audit_logs (accion, username) VALUES ('LOGIN_EXITOSO', %s)", (marca,))
        for intento in (f"UPDATE audit_logs SET username = 'otro' WHERE username = '{marca}'",
                        f"DELETE FROM audit_logs WHERE username = '{marca}'",
                        "CREATE TABLE intrusa (id int)",
                        "COPY (SELECT 1) TO PROGRAM 'echo hola'"):
            with pytest.raises(InsufficientPrivilege):
                cx.execute(intento)
    with psycopg.connect(_psycopg(URL_DUENA), autocommit=True) as cx:
        cx.execute("DELETE FROM audit_logs WHERE username = %s", (marca,))


async def test_borrar_un_usuario_con_bitacora_no_necesita_editarla(rol_app):
    """La FK de la bitácora (ON DELETE SET NULL) la aplica PostgreSQL con la cuenta
    dueña: la aplicación borra un usuario sin poder editar la bitácora."""
    url = _url_de(rol_app, secrets.token_hex(12))
    aplicar(URL_DUENA, url)
    nombre = f"borrar.{secrets.token_hex(3)}"
    async with SesionLocal() as s:
        usuario = Usuario(username=nombre, user_type=TipoUsuario.LOCAL)
        s.add(usuario)
        await s.flush()
        s.add(RegistroAuditoria(accion=AccionAuditoria.LOGIN_EXITOSO, user_id=usuario.id, username=nombre))
        await s.commit()
        usuario_id = usuario.id
    with psycopg.connect(_psycopg(url), autocommit=True) as cx:
        cx.execute("DELETE FROM users WHERE id = %s", (usuario_id,))
    with psycopg.connect(_psycopg(URL_DUENA), autocommit=True) as cx:
        assert cx.execute("SELECT user_id FROM audit_logs WHERE username = %s", (nombre,)).fetchone() == (None,)
        cx.execute("DELETE FROM audit_logs WHERE username = %s", (nombre,))


async def test_es_idempotente_y_pone_al_dia_la_clave(rol_app):
    vieja, nueva = secrets.token_hex(12), secrets.token_hex(12)
    assert "creada" in aplicar(URL_DUENA, _url_de(rol_app, vieja))
    assert "al día" in aplicar(URL_DUENA, _url_de(rol_app, nueva))
    with psycopg.connect(_psycopg(_url_de(rol_app, nueva))) as cx:
        assert cx.execute("SELECT current_user").fetchone() == (rol_app,)
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(_psycopg(_url_de(rol_app, vieja))).close()


async def test_sin_cuenta_aparte_no_toca_nada():
    assert "misma cuenta" in aplicar(URL_DUENA, URL_DUENA)


async def test_la_cuenta_de_la_aplicacion_necesita_clave():
    # URL.create y no .set(password=None): .set deja la clave que había.
    base = make_url(URL_DUENA)
    sin_clave = URL.create(base.drivername, username="sin_clave", host=base.host, port=base.port, database=base.database)
    with pytest.raises(SystemExit, match="no tiene clave"):
        aplicar(URL_DUENA, sin_clave.render_as_string(hide_password=False))
