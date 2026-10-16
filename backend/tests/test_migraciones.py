"""La migración del storage al sistema, de ida y vuelta, en una BD aparte que
arranca con una transferencia suelta del storage original."""
import secrets

import psycopg

from conftest import STORAGE, URL_ADMIN, borrar_bd, crear_bd, ejecutar_alembic, url_bd

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
