"""La cuenta de la base de datos con la que entra la aplicación: con lo justo.

La aplicación no se conecta con la cuenta dueña de las tablas ni con un
superusuario (hasta el 2026-11-08, en Docker entraba como `postgres`). Si algún
día hubiera una inyección SQL, el atacante quedaría con lo que puede esta
cuenta, que:
  - lee y escribe filas (SELECT, INSERT, UPDATE, DELETE), pero no crea, cambia
    ni borra tablas, ni ejecuta programas del servidor (COPY ... TO PROGRAM);
  - solo AGREGA a la bitácora (`audit_logs`) y al historial (`solicitud_eventos`):
    no puede editarlos ni borrarlos, que es justo lo que se esperaría que
    intentara alguien que quiere tapar lo que hizo;
  - no toca `alembic_version`.

Las migraciones corren con la cuenta dueña (MIGRACIONES_DATABASE_URL) y después
este módulo crea o pone al día la de la aplicación (DATABASE_URL): su clave y
sus permisos, también sobre las tablas nuevas. Es idempotente.

    MIGRACIONES_DATABASE_URL=<dueña> DATABASE_URL=<aplicación> python -m app.infrastructure.permisos_bd

Lo corren docker-entrypoint.sh y migrate.bat después de migrar. Si las dos
direcciones usan la misma cuenta (o no hay MIGRACIONES_DATABASE_URL), no hace nada.
"""
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

TABLAS_SOLO_AGREGAR = ("audit_logs", "solicitud_eventos")
TABLAS_SIN_ACCESO = ("alembic_version",)


def _para_psycopg(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def aplicar(url_duena: str, url_aplicacion: str) -> str:
    """Crea o pone al día la cuenta de `url_aplicacion` usando la de `url_duena`.
    Devuelve qué hizo, para el log del despliegue."""
    duena, aplicacion = make_url(url_duena), make_url(url_aplicacion)
    if not aplicacion.username or aplicacion.username == duena.username:
        return "La aplicación usa la misma cuenta que las migraciones: no hay permisos que ajustar."
    if not aplicacion.password:
        raise SystemExit("La cuenta de la aplicación no tiene clave (DATABASE_URL). En Docker: POSTGRES_APP_PASSWORD.")
    rol = sql.Identifier(aplicacion.username)
    base = sql.Identifier(aplicacion.database or duena.database)

    with psycopg.connect(_para_psycopg(url_duena), autocommit=True) as cx:
        fila = cx.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s", (aplicacion.username,)).fetchone()
        if fila and fila[0]:
            raise SystemExit(f"La cuenta {aplicacion.username} es superusuario: la aplicación debe entrar con una común.")
        accion = "ALTER" if fila else "CREATE"
        cx.execute(sql.SQL(accion + " ROLE {} WITH LOGIN PASSWORD {}").format(rol, sql.Literal(aplicacion.password)))
        sentencias = [
            "GRANT CONNECT ON DATABASE {base} TO {rol}",
            "GRANT USAGE ON SCHEMA public TO {rol}",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rol}",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {rol}",
            # Las tablas y secuencias que creen las migraciones siguientes (las crea esta cuenta).
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rol}",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {rol}",
        ]
        sentencias += [f"REVOKE UPDATE, DELETE, TRUNCATE ON {t} FROM {{rol}}" for t in TABLAS_SOLO_AGREGAR]
        sentencias += [f"REVOKE ALL ON {t} FROM {{rol}}" for t in TABLAS_SIN_ACCESO]
        for sentencia in sentencias:
            cx.execute(sql.SQL(sentencia).format(rol=rol, base=base))
    verbo = "creada" if accion == "CREATE" else "al día"
    return f"Cuenta de la aplicación {aplicacion.username}: {verbo}, con lo justo (bitácora e historial solo para agregar)."


def main() -> None:
    # Las dos direcciones, del entorno o del .env (Windows), como el resto de la configuración.
    from app.core.config import obtener_configuracion
    configuracion = obtener_configuracion()
    if not configuracion.MIGRACIONES_DATABASE_URL:
        print("Sin MIGRACIONES_DATABASE_URL: la aplicación usa la cuenta de las migraciones.")
        return
    print(aplicar(configuracion.MIGRACIONES_DATABASE_URL, configuracion.DATABASE_URL))


if __name__ == "__main__":
    main()
