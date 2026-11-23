"""La migración del storage al sistema, de ida y vuelta, en una BD aparte que
arranca con una transferencia suelta del storage original."""
import secrets

import psycopg
from sqlalchemy.engine import make_url

from conftest import STORAGE, URL_ADMIN, borrar_bd, crear_bd, ejecutar_alembic, sql_admin, url_bd

REVISION_STORAGE = "e2a6b8f3d1c7"


def _consultar(nombre_bd: str, sql: str):
    url = URL_ADMIN.rpartition("/")[0] + f"/{nombre_bd}"
    with psycopg.connect(url, autocommit=True) as cx:
        return cx.execute(sql).fetchone()


def test_migracion_ida_y_vuelta():
    nombre = f"argonavis_migracion_{secrets.token_hex(4)}"
    url = url_bd(nombre)
    crear_bd(nombre)
    try:
        r = ejecutar_alembic("upgrade", REVISION_STORAGE, url=url)
        assert r.returncode == 0, r.stderr[-3000:]

        token = secrets.token_urlsafe(24)
        carpeta = STORAGE / token
        carpeta.mkdir(parents=True)
        (carpeta / "archivo.pdf").write_bytes(b"%PDF-1.4")
        url_sync = URL_ADMIN.rpartition("/")[0] + f"/{nombre}"
        with psycopg.connect(url_sync, autocommit=True) as cx:
            uid = cx.execute(
                "INSERT INTO users (username, user_type, status) VALUES ('legado', 'LOCAL', 'ACTIVO') RETURNING id"
            ).fetchone()[0]
            tid = cx.execute(
                "INSERT INTO transfers (user_id, token, title, downloads) VALUES (%s, %s, 'Suelta', 0) RETURNING id",
                (uid, token),
            ).fetchone()[0]
            cx.execute(
                "INSERT INTO transfer_files (transfer_id, original_name, stored_name, path, size) "
                "VALUES (%s, 'archivo.pdf', 'archivo.pdf', %s, 8)",
                (tid, str(carpeta / "archivo.pdf")),
            )

        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        assert _consultar(nombre, "SELECT to_regclass('transfers'), to_regclass('solicitudes')") == (None, "solicitudes")
        assert not carpeta.exists(), "las carpetas del storage suelto se borran"
        assert _consultar(nombre, "SELECT count(*) FROM users WHERE username = 'legado'") == (1,), "los usuarios se conservan"

        r = ejecutar_alembic("downgrade", REVISION_STORAGE, url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        assert _consultar(nombre, "SELECT to_regclass('transfers'), to_regclass('solicitudes')") == ("transfers", None)

        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
    finally:
        borrar_bd(nombre)


def test_foto_del_checklist_de_las_solicitudes_existentes():
    """7e3f1a9c2d64: las solicitudes que ya existían quedan juzgadas con lo que
    presentaron (con lo que cumplieron al enviarse), aunque el catálogo haya
    cambiado después: p. ej. un Reporte Médico subido "para la solicitud"."""
    nombre = f"argonavis_casillas_{secrets.token_hex(4)}"
    url = url_bd(nombre)
    crear_bd(nombre)
    try:
        r = ejecutar_alembic("upgrade", "0a1c93f169d4", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        url_sync = URL_ADMIN.rpartition("/")[0] + f"/{nombre}"
        with psycopg.connect(url_sync, autocommit=True) as cx:
            uid = cx.execute("INSERT INTO users (username, user_type, status) VALUES ('legado', 'LOCAL', 'ACTIVO') RETURNING id").fetchone()[0]
            agencia = cx.execute("INSERT INTO agencias_navieras (nombre) VALUES ('Agencia') RETURNING id").fetchone()[0]
            puesto = cx.execute("INSERT INTO puestos_control (nombre) VALUES ('Puesto') RETURNING id").fetchone()[0]
            tipo = cx.execute("SELECT id FROM tipos_tramite WHERE codigo = 'F3-URGENCIA-MEDICA'").fetchone()[0]
            reporte, generales = (cx.execute("SELECT id FROM documentos_requeridos WHERE codigo = %s", (c,)).fetchone()[0]
                                  for c in ("DOC-REPORTE-MEDICO", "DOC-GENERALES-PASAPORTE"))
            sid = cx.execute(
                "INSERT INTO solicitudes (agencia_id, agencia_nombre, creada_por_id, tipo_tramite_id, puesto_control_id,"
                " puesto_nombre, titulo, fecha_operacion, cantidad_tripulantes, enviada_en)"
                " VALUES (%s, 'Agencia', %s, %s, %s, 'Puesto', 'Urgencia', current_date, 1, now()) RETURNING id",
                (agencia, uid, tipo, puesto),
            ).fetchone()[0]
            tid = cx.execute(
                "INSERT INTO solicitud_tripulantes (solicitud_id, nombre, apellido, fecha_nacimiento, pais_nacimiento,"
                " nacionalidad, sexo, pasaporte, pasaporte_expira, rango, ocupacion)"
                " VALUES (%s, 'Arjun', 'Mehta', '1987-04-12', 'IND', 'IND', 'M', 'Z1', '2030-01-01', 'marino', 'Marinero')"
                " RETURNING id", (sid,),
            ).fetchone()[0]
            for documento, tripulante in ((reporte, None), (generales, tid), (None, None)):
                cx.execute(
                    "INSERT INTO solicitud_documentos (solicitud_id, tripulante_id, documento_id, nombre_original,"
                    " nombre_almacenado, ruta, tamano) VALUES (%s, %s, %s, 'x.pdf', 'x.pdf', 'x.pdf', 1)",
                    (sid, tripulante, documento),
                )

        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            casillas = set(cx.execute(
                "SELECT documento_id, tripulante_id FROM solicitud_casillas WHERE solicitud_id = %s", (sid,),
            ).fetchall())
        assert casillas == {(reporte, None), (generales, tid)}, "lo presentado, tal cual; el adicional no es casilla"

        r = ejecutar_alembic("downgrade", "0a1c93f169d4", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
    finally:
        borrar_bd(nombre)


def test_rutas_de_documentos_relativas():
    """b5c2e8f4a713: las rutas absolutas de los documentos (de Windows o de
    Linux) quedan relativas a STORAGE_PATH; al bajar, vuelven a absolutas."""
    nombre = f"argonavis_rutas_{secrets.token_hex(4)}"
    url = url_bd(nombre)
    crear_bd(nombre)
    try:
        r = ejecutar_alembic("upgrade", "7e3f1a9c2d64", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        url_sync = URL_ADMIN.rpartition("/")[0] + f"/{nombre}"
        with psycopg.connect(url_sync, autocommit=True) as cx:
            uid = cx.execute("INSERT INTO users (username, user_type, status) VALUES ('legado', 'LOCAL', 'ACTIVO') RETURNING id").fetchone()[0]
            agencia = cx.execute("INSERT INTO agencias_navieras (nombre) VALUES ('Agencia') RETURNING id").fetchone()[0]
            puesto = cx.execute("INSERT INTO puestos_control (nombre) VALUES ('Puesto') RETURNING id").fetchone()[0]
            tipo = cx.execute("SELECT id FROM tipos_tramite WHERE codigo = 'F3-EMBARQUE'").fetchone()[0]
            sid = cx.execute(
                "INSERT INTO solicitudes (agencia_id, agencia_nombre, creada_por_id, tipo_tramite_id, puesto_control_id,"
                " puesto_nombre, titulo, fecha_operacion, cantidad_tripulantes, enviada_en)"
                " VALUES (%s, 'Agencia', %s, %s, %s, 'Puesto', 'Embarque', current_date, 1, now()) RETURNING id",
                (agencia, uid, tipo, puesto),
            ).fetchone()[0]
            for ruta in (r"C:\datos\storage\solicitud-7\a.pdf", "/app/storage/solicitud-7/b.pdf", "c.pdf"):
                cx.execute(
                    "INSERT INTO solicitud_documentos (solicitud_id, nombre_original, nombre_almacenado, ruta, tamano)"
                    " VALUES (%s, 'x.pdf', 'x.pdf', %s, 1)", (sid, ruta),
                )

        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            rutas = sorted(f[0] for f in cx.execute("SELECT ruta FROM solicitud_documentos").fetchall())
        assert rutas == ["c.pdf", "solicitud-7/a.pdf", "solicitud-7/b.pdf"], "lo que no tiene la forma esperada, tal cual"

        r = ejecutar_alembic("downgrade", "7e3f1a9c2d64", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            rutas = sorted(f[0] for f in cx.execute("SELECT ruta FROM solicitud_documentos").fetchall())
        assert rutas == sorted(str(STORAGE.resolve() / r) for r in ("c.pdf", "solicitud-7/a.pdf", "solicitud-7/b.pdf"))
    finally:
        borrar_bd(nombre)


def test_consulta_de_anios():
    """c6e2a9f1d438: las solicitudes ya revisadas quedan con el sector que su puesto tiene hoy;
    las que están en revisión, sin sector. El texto para buscar lo calcula PostgreSQL, también
    el de las filas que ya estaban. La corre la dueña de la base, sin ser superusuario."""
    sufijo = secrets.token_hex(4)
    nombre, duena = f"argonavis_anios_{sufijo}", f"duena_{sufijo}"
    url_sync = URL_ADMIN.rpartition("/")[0] + f"/{nombre}"
    crear_bd(nombre)
    try:
        with psycopg.connect(url_sync, autocommit=True) as cx:
            cx.execute(f"CREATE ROLE {duena} LOGIN PASSWORD 'prueba' NOSUPERUSER")
            cx.execute(f'ALTER DATABASE "{nombre}" OWNER TO {duena}')
            cx.execute(f"GRANT ALL ON SCHEMA public TO {duena}")
        url = make_url(url_bd(nombre)).set(username=duena, password="prueba").render_as_string(hide_password=False)
        r = ejecutar_alembic("upgrade", "b5e1c8d4f207", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            uid = cx.execute("INSERT INTO users (username, user_type, status) VALUES ('legado', 'LOCAL', 'ACTIVO') RETURNING id").fetchone()[0]
            agencia = cx.execute("INSERT INTO agencias_navieras (nombre) VALUES ('Agencia Ñandú') RETURNING id").fetchone()[0]
            tipo = cx.execute("SELECT id FROM tipos_tramite WHERE codigo = 'F3-EMBARQUE'").fetchone()[0]
            sector = cx.execute("SELECT id FROM sectores WHERE nombre = 'Sector Atlántico'").fetchone()[0]
            puesto = cx.execute("INSERT INTO puestos_control (nombre, sector_id) VALUES ('Puesto', %s) RETURNING id", (sector,)).fetchone()[0]
            for estado in ("review", "returned", "approved", "denied", "finalized", "expired"):
                sid = cx.execute(
                    "INSERT INTO solicitudes (agencia_id, agencia_nombre, creada_por_id, tipo_tramite_id, puesto_control_id,"
                    " puesto_nombre, titulo, fecha_operacion, cantidad_tripulantes, enviada_en, estado)"
                    " VALUES (%s, 'Agencia Ñandú', %s, %s, %s, 'Puesto', 'Embarque', current_date, 1, now(), %s) RETURNING id",
                    (agencia, uid, tipo, puesto, estado),
                ).fetchone()[0]
                cx.execute(
                    "INSERT INTO solicitud_tripulantes (solicitud_id, nombre, apellido, fecha_nacimiento, pais_nacimiento,"
                    " nacionalidad, sexo, pasaporte, pasaporte_expira, rango)"
                    " VALUES (%s, 'José', 'Núñez', '1987-04-12', 'PAN', 'PAN', 'M', 'Z1', '2030-01-01', 'marino')", (sid,),
                )

        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            sectores = dict(cx.execute("SELECT estado, sector_revision_id FROM solicitudes").fetchall())
            assert sectores == {"review": None, **dict.fromkeys(("returned", "approved", "denied", "finalized", "expired"), sector)}
            assert cx.execute("SELECT DISTINCT busqueda FROM solicitudes").fetchall() == [(" embarque   agencia nandu puesto ",)]
            assert cx.execute("SELECT DISTINCT busqueda FROM solicitud_tripulantes").fetchall() == [("jose nunez z1 ",)]
            assert cx.execute("SELECT tableowner FROM pg_tables WHERE tablename = 'solicitudes'").fetchone() == (duena,)

        r = ejecutar_alembic("downgrade", "b5e1c8d4f207", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
    finally:
        borrar_bd(nombre)
        sql_admin(URL_ADMIN, f"DROP ROLE IF EXISTS {duena}")


def test_historial_completo():
    """d7f3b0c5e849: al quitar un tripulante, sus documentos quedan sin dueño en vez de borrarse.
    Al bajar, los retirados salen de la tabla y la llave vuelve a ser la de antes."""
    nombre = f"argonavis_historial_{secrets.token_hex(4)}"
    url = url_bd(nombre)
    url_sync = URL_ADMIN.rpartition("/")[0] + f"/{nombre}"
    crear_bd(nombre)
    try:
        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            uid = cx.execute("INSERT INTO users (username, user_type, status) VALUES ('legado', 'LOCAL', 'ACTIVO') RETURNING id").fetchone()[0]
            agencia = cx.execute("INSERT INTO agencias_navieras (nombre) VALUES ('Agencia') RETURNING id").fetchone()[0]
            sector = cx.execute("SELECT min(id) FROM sectores").fetchone()[0]
            puesto = cx.execute("INSERT INTO puestos_control (nombre, sector_id) VALUES ('Puesto', %s) RETURNING id", (sector,)).fetchone()[0]
            tipo = cx.execute("SELECT id FROM tipos_tramite WHERE codigo = 'F3-EMBARQUE'").fetchone()[0]
            sid = cx.execute(
                "INSERT INTO solicitudes (agencia_id, agencia_nombre, creada_por_id, tipo_tramite_id, puesto_control_id,"
                " puesto_nombre, titulo, fecha_operacion, cantidad_tripulantes, enviada_en)"
                " VALUES (%s, 'Agencia', %s, %s, %s, 'Puesto', 'Embarque', current_date, 1, now()) RETURNING id",
                (agencia, uid, tipo, puesto),
            ).fetchone()[0]

            def con_documento(documento: str, **extra) -> int:
                tid = cx.execute(
                    "INSERT INTO solicitud_tripulantes (solicitud_id, nombre, apellido, fecha_nacimiento, pais_nacimiento,"
                    " nacionalidad, sexo, pasaporte, pasaporte_expira, rango)"
                    " VALUES (%s, 'Ana', 'Ríos', '1987-04-12', 'PAN', 'PAN', 'F', 'Z1', '2030-01-01', 'marino') RETURNING id", (sid,),
                ).fetchone()[0]
                columnas = {"solicitud_id": sid, "tripulante_id": tid, "nombre_original": documento,
                            "nombre_almacenado": documento, "ruta": documento, "tamano": 1, **extra}
                cx.execute(f"INSERT INTO solicitud_documentos ({', '.join(columnas)}) VALUES ({', '.join(['%s'] * len(columnas))})",
                           list(columnas.values()))
                return tid

            quitado = con_documento("retirado.pdf", retirado_en="2026-11-22", tripulante_nombre="Ana Ríos")
            con_documento("vigente.pdf")
            cx.execute("DELETE FROM solicitud_tripulantes WHERE id = %s", (quitado,))
            documentos = dict(cx.execute("SELECT nombre_original, tripulante_id FROM solicitud_documentos").fetchall())
            assert documentos["retirado.pdf"] is None and documentos["vigente.pdf"], "se conserva, sin dueño"

        r = ejecutar_alembic("downgrade", "c6e2a9f1d438", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
        with psycopg.connect(url_sync, autocommit=True) as cx:
            assert cx.execute("SELECT nombre_original FROM solicitud_documentos").fetchall() == [("vigente.pdf",)]
            cx.execute("DELETE FROM solicitud_tripulantes")
            assert cx.execute("SELECT count(*) FROM solicitud_documentos").fetchone() == (0,), "como antes: se van con el tripulante"
        r = ejecutar_alembic("upgrade", "head", url=url)
        assert r.returncode == 0, r.stderr[-3000:]
    finally:
        borrar_bd(nombre)
