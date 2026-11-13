"""Topes de recursos (revisión del 2026-11-10: «¿no hay riesgo de sobrecarga?»).

- El cuerpo de cada petición tiene tope antes de leerse: 1 MB en la API y, en crear
  y corregir una solicitud, lo más que pesa un envío válido. nginx tiene los mismos.
- Exportar las estadísticas y descargar el PDF tienen tope por cuenta y por hora.
- Cada proceso arma como mucho TRABAJOS_PESADOS_A_LA_VEZ archivos a la vez.
- Sin espacio en el disco de los documentos, no se reciben archivos (507).
"""
import asyncio
import io
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app import main
from app.core.config import obtener_configuracion
from app.domain.models.solicitud import RangoMarino
from app.domain.repositories.tramite_repository import RepositorioTramite
from app.domain.services.solicitud_service import (
    MAX_DOCUMENTOS_DE_LA_SOLICITUD, MAX_DOCUMENTOS_POR_TRIPULANTE, TOPE_CUERPO_ENVIO_MB,
)
from app.domain.services.tramite_service import ServicioTramite, TripulanteChecklist
from app.infrastructure import almacenamiento, trabajo_pesado
from app.infrastructure.database import SesionLocal

asincrona = pytest.mark.asyncio(loop_scope="session")

RAIZ = Path(__file__).resolve().parents[2]
MB = 1024 * 1024


async def _trozos(total: int, trozo: int = 256 * 1024):
    """Un cuerpo enviado por partes, sin Content-Length."""
    for inicio in range(0, total, trozo):
        yield b"x" * min(trozo, total - inicio)


# ── Tope del cuerpo ─────────────────────────────────────────────────────────

@asincrona
async def test_el_tope_de_un_envio_alcanza_para_el_catalogo():
    """Con el catálogo de hoy, ningún trámite pide más documentos por pasajero ni por
    solicitud de los que cuenta TOPE_CUERPO_ENVIO_MB. Si UCVMM agrega uno, esta prueba
    falla: sube MAX_DOCUMENTOS_* (solicitud_service.py) y client_max_body_size (nginx.conf)."""
    async with SesionLocal() as sesion:
        tipos = await RepositorioTramite(sesion).listar_tipos()
    # Todas las combinaciones que cambian el checklist, juntas en una solicitud.
    pasajeros = [
        TripulanteChecklist(nombre=f"{rango.value}-{panameno}-{restringida}", es_panameno=panameno,
                            rango=rango.value, nacionalidad_restringida=restringida)
        for rango in RangoMarino for panameno in (False, True) for restringida in (False, True)
    ]
    servicio = ServicioTramite()
    por_pasajero = de_la_solicitud = 0
    for tipo in tipos:
        casillas = servicio.construir_casillas(tipo, pasajeros)
        de_la_solicitud = max(de_la_solicitud, sum(c.indice_tripulante is None for c in casillas))
        for indice in range(len(pasajeros)):
            por_pasajero = max(por_pasajero, sum(c.indice_tripulante == indice for c in casillas))
    assert tipos and por_pasajero and de_la_solicitud
    assert por_pasajero <= MAX_DOCUMENTOS_POR_TRIPULANTE, f"un trámite pide {por_pasajero} documentos por pasajero"
    assert de_la_solicitud <= MAX_DOCUMENTOS_DE_LA_SOLICITUD, f"un trámite pide {de_la_solicitud} por solicitud"
    assert TOPE_CUERPO_ENVIO_MB == 285   # 30 × 4 + 2 + 20 = 142 archivos de 2 MB, más 1 MB


def test_nginx_tiene_los_mismos_topes_que_el_backend():
    conf = (RAIZ / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    api = re.search(r"location /api/ \{.*?client_max_body_size (\d+)m;", conf, re.S)
    envio = re.search(r"location ~ (\S+) \{[^}]*client_max_body_size (\d+)m;", conf)
    assert api and int(api.group(1)) == main.TOPE_CUERPO_MB
    assert envio and int(envio.group(2)) == TOPE_CUERPO_ENVIO_MB
    assert f"hasta {almacenamiento.TAMANO_MAXIMO_MB} MB" in conf   # el 413 de nginx dice el tope por archivo
    # La ruta de los envíos es la misma en nginx y en el backend.
    for ruta, es_envio in (("/api/v1/solicitudes", True), ("/api/v1/solicitudes/15", True),
                           ("/api/v1/solicitudes/15/aprobar", False), ("/api/v1/auth/login", False)):
        assert (main.tope_del_cuerpo("POST", ruta) == TOPE_CUERPO_ENVIO_MB * MB) is es_envio, ruta
        assert bool(re.search(envio.group(1), ruta)) is es_envio, ruta


@asincrona
async def test_un_cuerpo_grande_se_corta_sin_leerlo(cliente):
    """Antes el login leía cualquier cuerpo entero (a la memoria) antes de responder."""
    grande = b"x" * (main.TOPE_CUERPO_MB * MB + 1)
    r = await cliente.post("/auth/login", content=grande, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["detail"] == "El contenido de la petición supera el máximo permitido."
    assert r.headers.get("x-request-id"), "pasa por el código de pedido"

    # Por partes, sin Content-Length: se cuenta lo que llega.
    r = await cliente.post("/auth/login", content=_trozos(2 * MB), headers={"Content-Type": "application/json"})
    assert r.status_code == 413

    # Lo normal sigue igual (aquí, 422 por el JSON inválido).
    r = await cliente.post("/auth/login", content=b"x" * 1000, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


@asincrona
async def test_un_envio_mas_grande_que_el_tope(cliente, admin, monkeypatch):
    monkeypatch.setattr(main, "TOPE_CUERPO_ENVIO_MB", 2)
    archivo = {"archivos": ("grande.pdf", b"%PDF-1.4\n" + b"0" * (3 * MB), "application/pdf")}
    # Sin sesión también: se corta antes de leer el cuerpo (no llega a comprobar el token).
    for cabeceras in ({}, admin.headers):
        r = await cliente.post("/solicitudes", data={"solicitud": "{}"}, files=archivo, headers=cabeceras)
        assert r.status_code == 413, r.text
        assert r.json()["detail"] == ("El envío pesa más de 2 MB, lo máximo para una solicitud. "
                                      f"Cada archivo puede pesar hasta {almacenamiento.TAMANO_MAXIMO_MB} MB.")
    r = await cliente.put("/solicitudes/1", data={"solicitud": "{}"}, files=archivo, headers=admin.headers)
    assert r.status_code == 413
    # Por partes, sin Content-Length: un formulario válido con un archivo que no termina.
    async def formulario_por_partes():
        yield (b'--xyz\r\nContent-Disposition: form-data; name="archivos"; filename="a.pdf"\r\n'
               b"Content-Type: application/pdf\r\n\r\n%PDF-1.4\n")
        async for trozo in _trozos(3 * MB):
            yield trozo
    r = await cliente.post("/solicitudes", content=formulario_por_partes(), headers={
        **admin.headers, "Content-Type": "multipart/form-data; boundary=xyz"})
    assert r.status_code == 413, r.text


@asincrona
async def test_los_archivos_de_un_envio_pasan_al_disco_temporal():
    """Starlette deja en memoria cada archivo de hasta 1 MB; main.py lo baja a 64 KB.
    Si Starlette dejara de usar spool_max_size, el de 100 KB seguiría en memoria."""
    from starlette.formparsers import MultiPartParser
    from starlette.requests import Request

    assert MultiPartParser.spool_max_size == 64 * 1024
    cuerpo = (b'--xyz\r\nContent-Disposition: form-data; name="archivos"; filename="a.pdf"\r\n'
              b"Content-Type: application/pdf\r\n\r\n" + b"0" * 100_000 + b"\r\n--xyz--\r\n")
    mensajes = [{"type": "http.request", "body": cuerpo, "more_body": False}]

    async def recibir():
        return mensajes.pop(0) if mensajes else {"type": "http.disconnect"}

    scope = {"type": "http", "method": "POST", "path": "/",
             "headers": [(b"content-type", b"multipart/form-data; boundary=xyz")]}
    async with Request(scope, recibir).form() as formulario:
        assert formulario["archivos"].file._rolled, "el archivo de 100 KB sigue en memoria"


# ── Topes por cuenta y turnos ───────────────────────────────────────────────

@asincrona
async def test_exportar_tiene_tope_por_cuenta(cliente, admin, monkeypatch):
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit._config, "LIMITE_EXPORTACIONES_POR_HORA", 2)
    monkeypatch.setattr(rate_limit.limiter, "enabled", True)
    rate_limit.limiter.reset()
    try:
        for _ in range(2):
            r = await cliente.get("/solicitudes/estadisticas/exportar", params={"formato": "csv"}, headers=admin.headers)
            assert r.status_code == 200, r.text
        r = await cliente.get("/solicitudes/estadisticas/exportar", params={"formato": "csv"}, headers=admin.headers)
        assert r.status_code == 429 and "Espera" in r.json()["detail"]
    finally:
        rate_limit.limiter.reset()


@asincrona
async def test_los_trabajos_pesados_esperan_su_turno():
    """Como mucho TRABAJOS_PESADOS_A_LA_VEZ a la vez por proceso; los demás esperan."""
    tope = obtener_configuracion().TRABAJOS_PESADOS_A_LA_VEZ
    candado = threading.Lock()
    estado = {"a_la_vez": 0, "maximo": 0}

    def trabajo(numero: int) -> int:
        with candado:
            estado["a_la_vez"] += 1
            estado["maximo"] = max(estado["maximo"], estado["a_la_vez"])
        time.sleep(0.05)
        with candado:
            estado["a_la_vez"] -= 1
        return numero

    resultados = await asyncio.gather(*(trabajo_pesado.en_hilo_con_tope(trabajo, n) for n in range(4 * tope)))
    assert resultados == list(range(4 * tope))
    assert estado["maximo"] == tope


# ── Disco ───────────────────────────────────────────────────────────────────

@asincrona
async def test_sin_espacio_en_disco_no_se_reciben_archivos(tmp_path, monkeypatch):
    minimo = almacenamiento.configuracion.ESPACIO_MINIMO_LIBRE_MB
    assert minimo > 0
    monkeypatch.setattr(almacenamiento.shutil, "disk_usage", lambda _ruta: SimpleNamespace(free=(minimo - 1) * MB))
    destino = tmp_path / "solicitud"
    pdf = b"%PDF-1.4\n%%EOF\n"
    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(destino, [UploadFile(file=io.BytesIO(pdf), filename="a.pdf")])
    assert error.value.status_code == 507 and "espacio en disco" in error.value.detail
    assert not list(destino.iterdir())

    # Con 0, sin control.
    monkeypatch.setattr(almacenamiento.configuracion, "ESPACIO_MINIMO_LIBRE_MB", 0)
    guardados = await almacenamiento.guardar_archivos(destino, [UploadFile(file=io.BytesIO(pdf), filename="a.pdf")])
    assert len(guardados) == 1
