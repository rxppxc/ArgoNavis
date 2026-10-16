"""Endurecimiento: login sin enumeración de usuarios, subidas que no dejan rastro
y efectos fuera de la BD (borrar archivos) solo cuando la transacción se confirma."""
import asyncio
import io
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, UploadFile

from sqlalchemy import text

from app.core.config import obtener_configuracion
from app.core.ldap import servicio_ldap
from app.domain.models.user import EstadoUsuario, Usuario
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal, al_confirmar
from conftest import crear_actor

asincrona = pytest.mark.asyncio(loop_scope="session")

GENERICO = "Usuario o contraseña incorrectos."


async def _motivo_en_bitacora(cliente, admin, usuario: str) -> str:
    r = await cliente.get("/admin/bitacora", params={"accion": "LOGIN_FALLIDO", "usuario": usuario},
                          headers=admin.headers)
    return r.json()["items"][0]["detalle"]["motivo"]


def _ad_falso(monkeypatch, *, clave_correcta: str = "Correcta2026", espera: float = 0) -> list[str]:
    """AD de mentira: conoce cualquier nombre salvo los que empiezan con
    "borrado" y acepta solo `clave_correcta`. Devuelve los nombres por los que
    ARGO NAVIS le preguntó."""
    consultas: list[str] = []

    def buscar(nombre):
        consultas.append(nombre)
        return None if nombre.startswith("borrado") else {"dn": f"CN={nombre}", "username": nombre}

    def autenticar(dn, clave):
        time.sleep(espera)
        return clave == clave_correcta

    monkeypatch.setattr(servicio_ldap, "buscar_usuario", buscar)
    monkeypatch.setattr(servicio_ldap, "autenticar", autenticar)
    return consultas


async def _entrar(cliente, usuario: str, clave: str):
    return await cliente.post("/auth/login", json={"username": usuario, "password": clave})


@asincrona
async def test_login_no_revela_si_el_usuario_existe(cliente, admin, monkeypatch):
    """Nombre que no es de ARGO NAVIS, cuenta del AD con la contraseña equivocada,
    borrada del AD o desactivada: la misma respuesta. El motivo real queda en
    la bitácora."""
    consultas = _ad_falso(monkeypatch)

    # Cuenta del dominio no registrada en ARGO NAVIS, con su contraseña correcta:
    # antes respondía "no tienes acceso" (un oráculo de contraseñas del AD
    # para cualquiera en la VPN). Ahora ni se le pregunta al AD.
    r = await _entrar(cliente, "no.registrado", "Correcta2026")
    assert r.status_code == 401 and r.json()["detail"] == GENERICO
    assert consultas == []
    assert await _motivo_en_bitacora(cliente, admin, "no.registrado") == \
        "Usuario no registrado en ARGO NAVIS: no se consultó el AD."

    ad = await crear_actor(None, ad=True, prefijo="ad")
    r = await _entrar(cliente, ad.username, "mala")
    assert r.status_code == 401 and r.json()["detail"] == GENERICO
    assert await _motivo_en_bitacora(cliente, admin, ad.username) == "Contraseña incorrecta (Active Directory)."

    borrada = await crear_actor(None, ad=True, prefijo="borrado")
    r = await _entrar(cliente, borrada.username, "Correcta2026")
    assert r.status_code == 401 and r.json()["detail"] == GENERICO
    assert await _motivo_en_bitacora(cliente, admin, borrada.username) == "Usuario no encontrado en Active Directory."

    # Desactivada en ARGO NAVIS: tampoco se le pregunta al AD (no confirma su contraseña).
    async with SesionLocal() as s:
        (await s.get(Usuario, ad.id)).status = EstadoUsuario.INACTIVO
        await s.commit()
    consultas.clear()
    r = await _entrar(cliente, ad.username, "Correcta2026")
    assert r.status_code == 401 and r.json()["detail"] == GENERICO and consultas == []
    assert await _motivo_en_bitacora(cliente, admin, ad.username) == "Cuenta desactivada: no se consultó el AD."

    # Sin distinguir mayúsculas, como el AD; al AD se le pregunta por el nombre registrado.
    activa = await crear_actor(None, ad=True, prefijo="ad")
    consultas.clear()
    r = await _entrar(cliente, f"  {activa.username.upper()} ", "Correcta2026")
    assert r.status_code == 200 and consultas == [activa.username]


def _subida(nombre: str, contenido: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(contenido), filename=nombre)


@asincrona
async def test_archivo_rechazado_no_queda_en_disco(tmp_path, monkeypatch):
    destino = tmp_path / "solicitud"
    valido = b"%PDF-1.4\n%%EOF\n"

    # Supera el tamaño: 413 y no queda nada (en Windows el archivo se borraba abierto → 500)
    grande = valido + b"0" * almacenamiento.TAMANO_MAXIMO_BYTES
    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(destino, [_subida("grande.pdf", grande)])
    assert error.value.status_code == 413
    assert not list(destino.iterdir())

    # El segundo no es un PDF: se borra también el primero, que sí lo era
    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(destino, [_subida("bueno.pdf", valido), _subida("falso.pdf", b"hola")])
    assert error.value.status_code == 415
    assert not list(destino.iterdir())


@asincrona
async def test_tope_de_2_mb_por_archivo(tmp_path):
    """2 MB justos entran; un byte más, no (cualquier formato)."""
    assert almacenamiento.TAMANO_MAXIMO_BYTES == 2 * 1024 * 1024
    cabeza, cola = b"%PDF-1.4\n", b"\n%%EOF\n"
    relleno = b"0" * (almacenamiento.TAMANO_MAXIMO_BYTES - len(cabeza) - len(cola))
    guardados = await almacenamiento.guardar_archivos(tmp_path / "justo", [_subida("justo.pdf", cabeza + relleno + cola)])
    assert guardados[0].tamano == almacenamiento.TAMANO_MAXIMO_BYTES

    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(tmp_path / "grande", [_subida("grande.pdf", cabeza + relleno + b"0" + cola)])
    assert error.value.status_code == 413 and "2 MB" in error.value.detail


def test_rutas_de_documentos_relativas_al_storage(tmp_path, monkeypatch):
    """La BD guarda la ruta relativa a STORAGE_PATH: la carpeta se puede mover
    cambiando solo STORAGE_PATH. Nada que se salga de ella se sirve."""
    monkeypatch.setattr(almacenamiento.configuracion, "STORAGE_PATH", str(tmp_path))
    archivo = almacenamiento.carpeta_solicitud(7) / "abc.pdf"
    archivo.parent.mkdir(parents=True)
    archivo.write_bytes(b"%PDF-1.4")
    assert almacenamiento.ruta_relativa(archivo) == "solicitud-7/abc.pdf"
    assert almacenamiento.ruta_segura("solicitud-7/abc.pdf") == archivo.resolve()
    for afuera in ("../fuera.pdf", "solicitud-7/../../fuera.pdf", str(tmp_path.parent / "fuera.pdf")):
        assert almacenamiento.ruta_segura(afuera) is None, afuera


def test_nombre_de_archivo_largo_se_recorta():
    nombre = almacenamiento._sanear_nombre("a" * 600 + ".pdf")
    assert len(nombre) <= 200 and nombre.endswith(".pdf")
    assert almacenamiento._sanear_nombre('../ruta\\con:raros?.pdf') == "_ruta_con_raros_.pdf"


@asincrona
async def test_al_confirmar_solo_corre_si_hay_commit():
    hechas: list[str] = []
    async with SesionLocal() as s:
        al_confirmar(s, lambda: hechas.append("revertida"))
        await s.execute(text("select 1"))
        await s.rollback()
        # Lo descartado por el rollback no se dispara con un commit posterior.
        al_confirmar(s, lambda: hechas.append("confirmada"))
        await s.execute(text("select 1"))
        await s.commit()
    assert hechas == ["confirmada"]


@asincrona
async def test_word_y_excel_se_validan_por_su_contenido(tmp_path):
    """Además de PDF se aceptan Word y Excel, pero el contenido tiene que ser
    de verdad de ese formato: un archivo renombrado no pasa."""
    from ayudas import MIME_DOCX, MIME_XLSX, docx, xlsx

    def subida(archivo):
        return _subida(archivo[0], archivo[1])

    guardados = await almacenamiento.guardar_archivos(tmp_path / "a", [subida(docx("carta")), subida(xlsx("lista"))])
    assert [g.tipo_mime for g in guardados] == [MIME_DOCX, MIME_XLSX]

    for nombre, contenido in [("falso.docx", b"no es un zip"), ("excel.docx", xlsx("x")[1]),
                              ("falso.xls", b"texto plano"), ("programa.exe", b"MZ")]:
        destino = tmp_path / nombre
        with pytest.raises(HTTPException) as error:
            await almacenamiento.guardar_archivos(destino, [_subida(nombre, contenido)])
        assert error.value.status_code == 415, nombre
        assert not list(destino.iterdir()), nombre


@asincrona
async def test_office_con_macros_se_rechaza(tmp_path, monkeypatch):
    from ayudas import docx

    nombre, contenido, _ = docx("con-macros", "word/vbaProject.bin")
    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(tmp_path / "a", [_subida(nombre, contenido)])
    assert error.value.status_code == 415 and "macros" in error.value.detail

    # .doc (formato binario OLE2): lo decide oletools
    ole2 = bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 512
    monkeypatch.setattr(almacenamiento, "_tiene_macros_sync", lambda ruta: True)
    with pytest.raises(HTTPException) as error:
        await almacenamiento.guardar_archivos(tmp_path / "b", [_subida("viejo.doc", ole2)])
    assert error.value.status_code == 415 and "macros" in error.value.detail
    monkeypatch.setattr(almacenamiento, "_tiene_macros_sync", lambda ruta: False)
    [guardado] = await almacenamiento.guardar_archivos(tmp_path / "c", [_subida("viejo.doc", ole2)])
    assert guardado.tipo_mime == "application/msword"


@asincrona
async def test_freno_del_login_contra_el_ad(cliente, admin, monkeypatch):
    """Tras LOGIN_AD_MAX_FALLOS fallos seguidos, ARGO NAVIS deja de consultar al AD
    por esa cuenta durante LOGIN_AD_MINUTOS_ESPERA: nadie puede usarlo para
    bloquearle la cuenta del dominio a un funcionario."""
    maximo = obtener_configuracion().LOGIN_AD_MAX_FALLOS
    consultas = _ad_falso(monkeypatch)
    ad = await crear_actor(None, ad=True, prefijo="ad")

    for _ in range(maximo - 1):
        assert (await _entrar(cliente, ad.username, "mala")).status_code == 401
    r = await _entrar(cliente, ad.username, "mala")
    assert r.status_code == 429 and "espera" in r.json()["detail"]
    assert len(consultas) == maximo
    r = await cliente.get("/admin/bitacora", params={"accion": "CUENTA_BLOQUEADA", "usuario": ad.username},
                          headers=admin.headers)
    assert r.json()["items"][0]["detalle"]["origen"] == "ad"

    # Frenada: ni con la contraseña correcta se le pregunta al AD.
    r = await _entrar(cliente, ad.username, "Correcta2026")
    assert r.status_code == 429 and len(consultas) == maximo

    # Pasada la espera entra, y el contador vuelve a cero.
    async with SesionLocal() as s:
        (await s.get(Usuario, ad.id)).bloqueado_hasta = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()
    assert (await _entrar(cliente, ad.username, "Correcta2026")).status_code == 200
    assert (await _entrar(cliente, ad.username, "mala")).status_code == 401


@asincrona
async def test_freno_del_ad_con_intentos_en_paralelo(cliente, monkeypatch):
    """Los intentos en paralelo con una misma cuenta van de a uno (fila
    bloqueada): al AD llegan exactamente LOGIN_AD_MAX_FALLOS contraseñas, no
    una por pedido."""
    maximo = obtener_configuracion().LOGIN_AD_MAX_FALLOS
    consultas = _ad_falso(monkeypatch, espera=0.05)   # que se pisen si no fueran de a uno
    ad = await crear_actor(None, ad=True, prefijo="ad")

    respuestas = await asyncio.gather(*(_entrar(cliente, ad.username, "mala") for _ in range(maximo + 3)))
    assert sorted(r.status_code for r in respuestas) == [401] * (maximo - 1) + [429] * 4
    assert len(consultas) == maximo


@asincrona
async def test_limite_de_envios_por_usuario(cliente, monkeypatch):
    """Crear o corregir solicitudes (que suben archivos) tiene un tope por cuenta."""
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit._config, "LIMITE_ENVIOS_POR_HORA", 2)
    monkeypatch.setattr(rate_limit.limiter, "enabled", True)
    rate_limit.limiter.reset()
    try:
        uno, otro = await crear_actor("Naviera", prefijo="nav"), await crear_actor("Naviera", prefijo="nav")
        for _ in range(2):
            r = await cliente.post("/solicitudes", data={"solicitud": "{}"}, headers=uno.headers)
            assert r.status_code != 429
        r = await cliente.post("/solicitudes", data={"solicitud": "{}"}, headers=uno.headers)
        assert r.status_code == 429 and "Espera" in r.json()["detail"]
        r = await cliente.post("/solicitudes", data={"solicitud": "{}"}, headers=otro.headers)
        assert r.status_code != 429, "el tope es por cuenta, no global"
    finally:
        rate_limit.limiter.reset()


def test_produccion_no_arranca_con_una_clave_debil():
    from app.core.config import Configuracion

    for clave in ("corta", "REEMPLAZAR_CON_CLAVE_GENERADA_REEMPLAZAR_CON_CLAVE"):
        with pytest.raises(ValueError):
            Configuracion(APP_ENV="production", SECRET_KEY=clave)
    assert Configuracion(APP_ENV="production", SECRET_KEY="x" * 48).es_produccion


def test_solo_estas_rutas_responden_sin_sesion():
    """Si alguien agrega un endpoint sin exigir el token, esta prueba lo frena."""
    from fastapi.routing import APIRoute

    from app.core.security import esquema_bearer
    from app.main import aplicacion

    def exige_token(dependant) -> bool:
        return dependant.call is esquema_bearer or any(exige_token(d) for d in dependant.dependencies)

    def rutas(lista, prefijo=""):
        for ruta in lista:
            if isinstance(ruta, APIRoute):
                yield f"{prefijo}{ruta.path}", ruta
            elif hasattr(ruta, "original_router"):
                yield from rutas(ruta.original_router.routes, prefijo + "/api/v1")

    publicas = {f"{metodo} {camino}" for camino, ruta in rutas(aplicacion.routes)
                if not exige_token(ruta.dependant) for metodo in ruta.methods}
    permitidas = {"POST /api/v1/auth/login", "GET /api/v1/verificacion/{codigo}", "GET /api/health",
                  "GET /{ruta_completa:path}"}   # la última solo existe si hay frontend compilado
    assert publicas - permitidas == set(), publicas - permitidas
    assert {"POST /api/v1/auth/login", "GET /api/v1/verificacion/{codigo}"} <= publicas
