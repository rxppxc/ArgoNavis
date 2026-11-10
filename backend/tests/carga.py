"""Prueba de carga: ¿aguanta ARGO NAVIS 100 usuarios trabajando a la vez? (2026-11-08)

Levanta el backend de verdad (uvicorn con 2 procesos, como el compose) contra una
BD temporal, siembra agencias, cuentas y solicitudes, y durante un rato pone a N
usuarios a trabajar a la vez, mucho más rápido que una persona: cada uno pide algo
cada 1 a 3 segundos (bandejas, campana, expedientes, documentos, estadísticas y
envíos nuevos). Al final: la latencia de cada pantalla, los errores y cuántas
conexiones a la BD llegó a usar.

No la corre pytest (tarda y carga la máquina). Desde backend/:
    venv\\Scripts\\python tests\\carga.py [--usuarios 100] [--segundos 90]

Usa el servidor de TEST_DATABASE_URL o el de DATABASE_URL del .env, con una BD
temporal que borra al terminar. No envía correos ni toca la BD de desarrollo. Las
sesiones se firman aquí (el login tiene su propio tope por IP); el login se mide
aparte, con 10 a la vez.
"""
import argparse
import asyncio
import json
import os
import random
import secrets
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import psycopg
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent.parent
PUERTO = 8002
BASE = f"http://127.0.0.1:{PUERTO}"
NOMBRE_BD = f"argonavis_carga_{secrets.token_hex(3)}"
STORAGE = Path(tempfile.mkdtemp(prefix="argonavis_carga_"))
CLAVE = "Carga-Prueba-2026!"

_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
if not _url:
    raise SystemExit("Define TEST_DATABASE_URL o DATABASE_URL en backend/.env.")
_base = _url.rpartition("/")[0]
URL_ADMIN = f"{_base}/postgres".replace("postgresql+asyncpg://", "postgresql://")
URL_BD = f"{_base}/{NOMBRE_BD}"

ENTORNO = {
    **os.environ,
    "DATABASE_URL": URL_BD, "MIGRACIONES_DATABASE_URL": "",
    "STORAGE_PATH": str(STORAGE), "APP_ENV": "test", "SECRET_KEY": secrets.token_urlsafe(32),
    "LDAP_HOST": "ldap.invalido", "LDAP_BASE_DN": "DC=prueba", "LDAP_BIND_USER": "x", "LDAP_BIND_PASSWORD": "x",
    "MAIL_HOST": "", "CORREO_UCVMM": "", "LOG_CARPETA": "", "LOG_NIVEL": "WARNING",
    "PERMITIR_LOGIN_LOCAL": "true", "LIMITE_VERIFICACIONES_POR_MINUTO": "0", "LIMITE_ENVIOS_POR_HORA": "0",
}
os.environ.update(ENTORNO)
sys.path.insert(0, str(BACKEND))

MANANA = (datetime.now(ZoneInfo("America/Panama")).date() + timedelta(days=1)).isoformat()
VIGENTE = (datetime.now(ZoneInfo("America/Panama")).date() + timedelta(days=400)).isoformat()


def _sql_admin(sentencia: str) -> None:
    with psycopg.connect(URL_ADMIN, autocommit=True) as cx:
        cx.execute(sentencia)


def _conexiones_abiertas() -> int:
    with psycopg.connect(URL_ADMIN, autocommit=True) as cx:
        return cx.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (NOMBRE_BD,)).fetchone()[0]


def preparar_bd() -> None:
    _sql_admin(f'CREATE DATABASE "{NOMBRE_BD}"')
    r = subprocess.run([sys.executable, "-I", "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=ENTORNO,
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-3000:])


async def sembrar(navieras: int, ucvmm: int, puesto: int) -> dict:
    from sqlalchemy import insert, select

    from app.core.security import crear_token_acceso, hashear_password
    from app.domain.models.catalogo import AgenciaNaviera, PuestoControl, Sector, usuarios_puestos, usuarios_sectores
    from app.domain.models.rol import Rol
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal, motor_bd
    from app.main import aplicacion  # noqa: F401  (registra todos los modelos)

    clave = hashear_password(CLAVE)
    async with SesionLocal() as s:
        agencias = [AgenciaNaviera(nombre=f"Agencia Carga {i}") for i in range(10)]
        # Un puesto en cada sector; los revisores, en los dos (ven todo, como antes).
        sectores = [x.id for x in (await s.execute(select(Sector).order_by(Sector.id))).scalars()]
        puestos = [PuestoControl(nombre=f"Puesto Carga {i}", sector_id=sectores[i % 2]) for i in range(2)]
        s.add_all(agencias + puestos)
        await s.flush()
        roles = {r.nombre: r.id for r in (await s.execute(select(Rol))).scalars()}

        def cuenta(nombre: str, rol: str, agencia_id: int | None = None) -> Usuario:
            u = Usuario(username=nombre, name=nombre, user_type=TipoUsuario.LOCAL, password_hash=clave,
                        rol_id=roles[rol], agencia_id=agencia_id)
            s.add(u)
            return u

        de_agencias = [cuenta(f"carga.naviera{i}", "Naviera", agencias[i % 10].id) for i in range(navieras)]
        de_ucvmm = [cuenta(f"carga.ucvmm{i}", "UCVMM") for i in range(ucvmm)]
        de_puesto = [cuenta(f"carga.puesto{i}", "Puesto de Control") for i in range(puesto)]
        await s.flush()
        for i, u in enumerate(de_puesto):
            await s.execute(insert(usuarios_puestos).values(usuario_id=u.id, puesto_id=puestos[i % 2].id))
        for u in de_ucvmm:
            for sector_id in sectores:
                await s.execute(insert(usuarios_sectores).values(usuario_id=u.id, sector_id=sector_id))
        await s.commit()
        datos = {
            "naviera": [u.id for u in de_agencias], "ucvmm": [u.id for u in de_ucvmm],
            "puesto": [u.id for u in de_puesto], "puestos": [p.id for p in puestos],
            "nombres": [u.username for u in de_ucvmm[:10]],
        }
    await motor_bd.dispose()
    datos["tokens"] = {uid: crear_token_acceso(uid) for rol in ("naviera", "ucvmm", "puesto") for uid in datos[rol]}
    return datos


def _pdf(nombre: str) -> tuple[str, bytes, str]:
    return (f"{nombre}.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + os.urandom(40_000), "application/pdf")


def _solicitud(puesto_id: int) -> tuple[dict, list]:
    datos = {
        "codigo_tramite": "F3-CAMBIO-NAVE", "puesto_control_id": puesto_id, "fecha_operacion": MANANA,
        "nombre_buque": "MSC AURORA", "imo": "IMO 9074729", "bandera": "PAN", "observaciones": "Prueba de carga",
        "tripulantes": [{
            "nombre": "Luis", "apellido": "Pérez", "fecha_nacimiento": "1990-05-01", "pais_nacimiento": "PHL",
            "nacionalidad": "PHL", "sexo": "M", "pasaporte": f"P{secrets.token_hex(3)}", "pasaporte_expira": VIGENTE,
            "rango": "marino", "ocupacion": "Marinero", "libreta_marino": f"SB{secrets.token_hex(2)}", "libreta_expira": VIGENTE,
        }],
        "asignaciones": [
            {"documento_codigo": "DOC-VISA-MARINO", "indice_tripulante": 0},
            {"documento_codigo": "DOC-GENERALES-PASAPORTE", "indice_tripulante": 0},
        ],
    }
    return datos, [_pdf("visa"), _pdf("pasaporte")]


class Medidas:
    def __init__(self):
        self.tiempos: dict[str, list[float]] = defaultdict(list)
        self.estados: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.fallas_red: dict[str, int] = defaultdict(int)

    async def pedir(self, cliente: httpx.AsyncClient, accion: str, metodo: str, ruta: str, **opciones) -> httpx.Response | None:
        inicio = time.perf_counter()
        try:
            r = await cliente.request(metodo, ruta, **opciones)
        except httpx.HTTPError:
            self.fallas_red[accion] += 1
            return None
        self.tiempos[accion].append((time.perf_counter() - inicio) * 1000)
        self.estados[accion][r.status_code] += 1
        return r


async def usuario_virtual(cliente, medidas: Medidas, rol: str, token: str, ids: list[int], hasta: float, puestos: list[int]):
    cabecera = {"Authorization": f"Bearer {token}"}
    mios: list[int] = list(ids)
    while time.monotonic() < hasta:
        await asyncio.sleep(random.uniform(1, 3))
        dado = random.random()
        if rol == "naviera":
            if dado < 0.35:
                await medidas.pedir(cliente, "campana", "GET", "/api/v1/pendientes", headers=cabecera)
            elif dado < 0.65:
                await medidas.pedir(cliente, "bandeja de la agencia", "GET", "/api/v1/solicitudes/agencia", headers=cabecera)
            elif dado < 0.92 and mios:
                r = await medidas.pedir(cliente, "expediente", "GET", f"/api/v1/solicitudes/{random.choice(mios)}", headers=cabecera)
                documentos = (r.json().get("documentos") or []) if r is not None and r.status_code == 200 else []
                if documentos and random.random() < 0.3:
                    d = random.choice(documentos)
                    await medidas.pedir(cliente, "ver documento", "GET", f"/api/v1/solicitudes/{r.json()['id']}/documentos/{d['id']}", headers=cabecera)
            else:
                datos, archivos = _solicitud(random.choice(puestos))
                r = await medidas.pedir(cliente, "enviar solicitud", "POST", "/api/v1/solicitudes", headers=cabecera,
                                        data={"solicitud": json.dumps(datos)}, files=[("files", a) for a in archivos])
                if r is not None and r.status_code == 201:
                    mios.append(r.json()["id"])
        elif rol == "ucvmm":
            if dado < 0.35:
                await medidas.pedir(cliente, "bandeja de revisión", "GET", "/api/v1/solicitudes/revision",
                                    params={"pagina": random.randint(1, 3)}, headers=cabecera)
            elif dado < 0.65:
                await medidas.pedir(cliente, "campana", "GET", "/api/v1/pendientes", headers=cabecera)
            elif dado < 0.95 and mios:
                await medidas.pedir(cliente, "expediente", "GET", f"/api/v1/solicitudes/{random.choice(mios)}", headers=cabecera)
            else:
                await medidas.pedir(cliente, "estadísticas", "GET", "/api/v1/solicitudes/estadisticas", headers=cabecera)
        else:
            if dado < 0.5:
                await medidas.pedir(cliente, "campana", "GET", "/api/v1/pendientes", headers=cabecera)
            else:
                await medidas.pedir(cliente, "bandeja del puesto", "GET", "/api/v1/solicitudes/puerto", headers=cabecera)


def _percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))]


def informe(titulo: str, medidas: Medidas, segundos: float) -> None:
    print(f"\n{titulo}")
    print(f"  {'Acción':<24}{'pedidos':>8}{'errores':>9}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'máx ms':>9}")
    total = errores5 = errores4 = 0
    for accion in sorted(medidas.tiempos):
        t = medidas.tiempos[accion]
        e5 = sum(n for estado, n in medidas.estados[accion].items() if estado >= 500)
        e4 = sum(n for estado, n in medidas.estados[accion].items() if 400 <= estado < 500)
        total += len(t)
        errores5 += e5
        errores4 += e4
        print(f"  {accion:<24}{len(t):>8}{e5 + e4 + medidas.fallas_red[accion]:>9}{statistics.median(t):>9.0f}"
              f"{_percentil(t, 95):>9.0f}{_percentil(t, 99):>9.0f}{max(t):>9.0f}")
    red = sum(medidas.fallas_red.values())
    print(f"  Total: {total} pedidos en {segundos:.0f} s ({total / segundos:.1f} por segundo). "
          f"5xx: {errores5} · 4xx: {errores4} · fallas de red: {red}")
    for accion, estados in medidas.estados.items():
        raros = {e: n for e, n in estados.items() if e >= 400}
        if raros:
            print(f"    {accion}: {raros}")


def _detener(proceso: subprocess.Popen) -> None:
    if os.name == "nt":   # uvicorn con varios procesos: hay que cerrar el árbol entero
        subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"], capture_output=True)
    else:
        proceso.terminate()
    proceso.wait(timeout=30)


async def principal(usuarios: int, segundos: int) -> None:
    navieras = round(usuarios * 0.8)
    ucvmm = round(usuarios * 0.15)
    puesto = max(1, usuarios - navieras - ucvmm)
    print(f"BD temporal {NOMBRE_BD}: migrando y sembrando {navieras} cuentas de agencias, {ucvmm} de UCVMM y {puesto} de puestos…")
    preparar_bd()
    datos = await sembrar(navieras, ucvmm, puesto)

    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:aplicacion", "--host", "127.0.0.1", "--port", str(PUERTO),
         "--workers", "2", "--log-level", "warning"], cwd=BACKEND, env=ENTORNO)
    try:
        limites = httpx.Limits(max_connections=usuarios * 2, max_keepalive_connections=usuarios * 2)
        async with httpx.AsyncClient(base_url=BASE, timeout=30, limits=limites) as cliente:
            for _ in range(120):
                try:
                    if (await cliente.get("/api/health")).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
            else:
                raise SystemExit("El backend no arrancó.")
            print(f"Backend en {BASE} con 2 procesos (equipo con {os.cpu_count()} núcleos).")

            # Cada agencia envía una solicitud, 20 a la vez: hay expedientes para mirar.
            previas = Medidas()
            ids_por_usuario: dict[int, list[int]] = defaultdict(list)
            inicio = time.monotonic()
            for lote in range(0, navieras, 20):
                async def enviar(uid: int):
                    datos_s, archivos = _solicitud(random.choice(datos["puestos"]))
                    r = await previas.pedir(cliente, "enviar solicitud", "POST", "/api/v1/solicitudes",
                                            headers={"Authorization": f"Bearer {datos['tokens'][uid]}"},
                                            data={"solicitud": json.dumps(datos_s)}, files=[("files", a) for a in archivos])
                    if r is not None and r.status_code == 201:
                        ids_por_usuario[uid].append(r.json()["id"])
                await asyncio.gather(*(enviar(uid) for uid in datos["naviera"][lote:lote + 20]))
            informe("Siembra: cada agencia envía una solicitud, 20 a la vez", previas, time.monotonic() - inicio)
            todas = [i for ids in ids_por_usuario.values() for i in ids]

            # El login, con bcrypt: 10 a la vez.
            login = Medidas()
            await asyncio.gather(*(login.pedir(cliente, "login (10 a la vez)", "POST", "/api/v1/auth/login",
                                               json={"username": nombre, "password": CLAVE}) for nombre in datos["nombres"]))
            informe("Login", login, 1)

            # La carga: todos a la vez durante `segundos`.
            medidas = Medidas()
            hasta = time.monotonic() + segundos
            maximo_conexiones = 0

            async def vigilar_conexiones():
                nonlocal maximo_conexiones
                while time.monotonic() < hasta:
                    maximo_conexiones = max(maximo_conexiones, await asyncio.to_thread(_conexiones_abiertas))
                    await asyncio.sleep(2)

            virtuales = (
                [usuario_virtual(cliente, medidas, "naviera", datos["tokens"][u], ids_por_usuario[u], hasta, datos["puestos"])
                 for u in datos["naviera"]]
                + [usuario_virtual(cliente, medidas, "ucvmm", datos["tokens"][u], todas, hasta, datos["puestos"]) for u in datos["ucvmm"]]
                + [usuario_virtual(cliente, medidas, "puesto", datos["tokens"][u], [], hasta, datos["puestos"]) for u in datos["puesto"]]
            )
            print(f"\nCarga: {len(virtuales)} usuarios a la vez durante {segundos} s…")
            inicio = time.monotonic()
            await asyncio.gather(vigilar_conexiones(), *virtuales)
            informe(f"Carga: {len(virtuales)} usuarios, cada uno pide algo cada 1 a 3 s", medidas, time.monotonic() - inicio)
            print(f"  Conexiones a la BD: máximo {maximo_conexiones} (tope: 2 procesos × 15 = 30)")
    finally:
        _detener(servidor)
        _sql_admin(f'DROP DATABASE IF EXISTS "{NOMBRE_BD}" WITH (FORCE)')
        shutil.rmtree(STORAGE, ignore_errors=True)


if __name__ == "__main__":
    partes = argparse.ArgumentParser(description="Prueba de carga de ARGO NAVIS (BD temporal).")
    partes.add_argument("--usuarios", type=int, default=100)
    partes.add_argument("--segundos", type=int, default=90)
    argumentos = partes.parse_args()
    asyncio.run(principal(argumentos.usuarios, argumentos.segundos))
