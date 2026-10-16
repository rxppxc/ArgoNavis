"""Cuentas locales: bloqueo por intentos, cambio obligatorio y restablecimiento."""
import secrets

import pytest

from conftest import crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")

CLAVE = "Clave-2026-Segura"


async def login(cliente, usuario: str, clave: str):
    return await cliente.post("/auth/login", json={"username": usuario, "password": clave})


async def test_bloqueo_tras_intentos_fallidos(cliente, admin, sysadmin):
    actor = await crear_actor("Naviera", password=CLAVE, prefijo="local")

    r = await login(cliente, actor.username, CLAVE)
    assert r.status_code == 200 and not r.json()["user"]["debe_cambiar_password"]

    for _ in range(4):
        r = await login(cliente, actor.username, "incorrecta1")
        assert r.status_code == 401 and r.json()["detail"] == "Usuario o contraseña incorrectos."
    r = await login(cliente, actor.username, "incorrecta1")
    assert r.status_code == 423, "el quinto fallo bloquea la cuenta"
    r = await login(cliente, actor.username, CLAVE)
    assert r.status_code == 423, "bloqueada no entra ni con la clave correcta"

    # Los intentos fallidos quedan en la bitácora aunque la respuesta sea un error
    r = await cliente.get("/admin/bitacora", params={"accion": "LOGIN_FALLIDO", "usuario": actor.username}, headers=sysadmin.headers)
    assert r.json()["total"] == 6
    r = await cliente.get("/admin/bitacora", params={"accion": "CUENTA_BLOQUEADA", "usuario": actor.username}, headers=sysadmin.headers)
    assert r.json()["total"] == 1

    # El SysAdmin restablece: la desbloquea y da una clave temporal
    r = await cliente.post(f"/admin/usuarios/{actor.id}/restablecer-contrasena", headers=sysadmin.headers)
    assert r.status_code == 200
    temporal = r.json()["contrasena_temporal"]
    r = await login(cliente, actor.username, temporal)
    assert r.status_code == 200 and r.json()["user"]["debe_cambiar_password"]


async def test_cambio_obligatorio(cliente, admin, sysadmin):
    r = await cliente.post("/admin/usuarios/local", json={
        "username": "agencia.nueva", "password": CLAVE, "name": "Agencia", "last_name": "Nueva",
    }, headers=sysadmin.headers)
    assert r.status_code == 201 and r.json()["debe_cambiar_password"]
    r = await cliente.post("/admin/usuarios/local", json={"username": "clave.debil", "password": "abc12"}, headers=sysadmin.headers)
    assert r.status_code == 422, "la política exige 12 caracteres con mayúscula, minúscula, número y especial"

    r = await login(cliente, "agencia.nueva", CLAVE)
    token = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await cliente.get("/tramites", headers=token)
    assert r.status_code == 403 and r.headers.get("x-cambio-contrasena") == "requerido"
    r = await cliente.get("/auth/me", headers=token)
    assert r.status_code == 200, "el perfil sí se puede consultar"

    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": "otra-cosa-1", "nueva": "Nueva.Clave-2026"}, headers=token)
    assert r.status_code == 400
    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": CLAVE, "nueva": "corta1"}, headers=token)
    assert r.status_code == 422
    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": CLAVE, "nueva": CLAVE}, headers=token)
    assert r.status_code == 400, "la nueva debe ser distinta"
    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": CLAVE, "nueva": "Agencia.Nueva-2026"},
                           headers=token)
    assert r.status_code == 400 and "nombre de usuario" in r.json()["detail"]
    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": CLAVE, "nueva": "Nueva.Clave-2026"}, headers=token)
    assert r.status_code == 200 and not r.json()["user"]["debe_cambiar_password"]
    nuevo = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await cliente.get("/tramites", headers=nuevo)
    assert r.status_code == 200, "sigue con el token que devuelve el cambio"
    r = await cliente.get("/auth/me", headers=token)
    assert r.status_code == 401, "el cambio de contraseña cierra las sesiones anteriores"
    r = await login(cliente, "agencia.nueva", "Nueva.Clave-2026")
    assert r.status_code == 200 and not r.json()["user"]["debe_cambiar_password"]
    r = await cliente.get("/admin/bitacora", params={"accion": "CONTRASENA_CAMBIADA", "usuario": "agencia.nueva"}, headers=sysadmin.headers)
    assert r.json()["total"] == 1


async def test_restablecer_solo_cuentas_locales(cliente, sysadmin):
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal

    async with SesionLocal() as s:
        usuario_ad = Usuario(username="cuenta.ad", user_type=TipoUsuario.AD)
        s.add(usuario_ad)
        await s.commit()
        uid = usuario_ad.id
    r = await cliente.post(f"/admin/usuarios/{uid}/restablecer-contrasena", headers=sysadmin.headers)
    assert r.status_code == 400


async def test_cambiar_contrasena_cuenta_ad(cliente):
    actor = await crear_actor("Naviera", prefijo="ad")
    from sqlalchemy import update
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal

    async with SesionLocal() as s:
        await s.execute(update(Usuario).where(Usuario.id == actor.id).values(user_type=TipoUsuario.AD))
        await s.commit()
    r = await cliente.post("/auth/cambiar-contrasena", json={"actual": "x", "nueva": "Nueva.Clave-2026"}, headers=actor.headers)
    assert r.status_code == 400 and "Active Directory" in r.json()["detail"]


async def _entrar(cliente, actor_usuario: str, clave: str = CLAVE) -> dict[str, str]:
    r = await login(cliente, actor_usuario, clave)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_cerrar_sesion_invalida_el_token(cliente):
    actor = await crear_actor("Naviera", password=CLAVE, prefijo="local")
    token = await _entrar(cliente, actor.username)
    assert (await cliente.get("/auth/me", headers=token)).status_code == 200

    r = await cliente.post("/auth/logout", headers=token)
    assert r.status_code == 204
    r = await cliente.get("/auth/me", headers=token)
    assert r.status_code == 401, "un token copiado no sigue sirviendo tras cerrar sesión"
    assert (await cliente.post("/auth/refresh", headers=token)).status_code == 401

    nuevo = await _entrar(cliente, actor.username)
    assert (await cliente.get("/auth/me", headers=nuevo)).status_code == 200, "volver a entrar (mismo segundo) funciona"


async def test_restablecer_cierra_la_sesion(cliente):
    sysadmin = await crear_actor("SysAdmin", prefijo="sysadmin")
    actor = await crear_actor("Naviera", password=CLAVE, prefijo="local")
    token = await _entrar(cliente, actor.username)
    r = await cliente.post(f"/admin/usuarios/{actor.id}/restablecer-contrasena", headers=sysadmin.headers)
    assert r.status_code == 200
    assert (await cliente.get("/auth/me", headers=token)).status_code == 401


async def test_renovar_conserva_el_inicio_de_la_sesion(cliente):
    from datetime import datetime, timedelta, timezone

    from app.core.config import obtener_configuracion
    from app.core.security import crear_token_acceso, decodificar_token

    actor = await crear_actor("Naviera", prefijo="local")
    maximo = timedelta(hours=obtener_configuracion().SESION_MAXIMA_HORAS)
    inicio = datetime.now(timezone.utc).replace(microsecond=0) - maximo + timedelta(minutes=5)
    viejo = crear_token_acceso(actor.id, {"username": actor.username}, inicio_sesion=inicio)

    r = await cliente.post("/auth/refresh", headers={"Authorization": f"Bearer {viejo}"})
    assert r.status_code == 200
    carga = decodificar_token(r.json()["access_token"])
    assert carga["ini"] == int(inicio.timestamp()), "la renovación no reinicia la sesión"
    assert carga["exp"] <= int((inicio + maximo).timestamp()), "ningún token pasa de la duración máxima"


async def test_clave_que_ya_no_cumple_la_politica_obliga_a_cambiarla(cliente):
    """Cuentas con una contraseña de la política anterior (10 caracteres con
    letras y números): entran, pero tienen que cambiarla antes de seguir."""
    actor = await crear_actor("Naviera", password="Clave2026Vieja", prefijo="local")
    r = await login(cliente, actor.username, "Clave2026Vieja")
    assert r.status_code == 200 and r.json()["user"]["debe_cambiar_password"]
    token = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await cliente.get("/tramites", headers=token)
    assert r.status_code == 403 and r.headers.get("x-cambio-contrasena") == "requerido"


async def test_agencia_desactivada_deja_fuera_a_sus_usuarios(cliente, admin):
    r = await cliente.post("/admin/agencias", json={"nombre": f"Agencia Apagada {secrets.token_hex(2)}"},
                           headers=admin.headers)
    agencia_id = r.json()["id"]
    actor = await crear_actor("Naviera", password=CLAVE, prefijo="local", agencia_id=agencia_id)
    token = await _entrar(cliente, actor.username)

    r = await cliente.patch(f"/admin/agencias/{agencia_id}", json={"activo": False}, headers=admin.headers)
    assert r.status_code == 200
    r = await cliente.get("/auth/me", headers=token)
    assert r.status_code == 401 and "agencia" in r.json()["detail"], "la sesión abierta se corta"
    r = await login(cliente, actor.username, CLAVE)
    assert r.status_code == 403 and "agencia" in r.json()["detail"]
    r = await login(cliente, actor.username, "Otra-Clave-2026")
    assert r.status_code == 401, "sin la contraseña correcta no revela que la agencia está desactivada"

    r = await cliente.patch(f"/admin/agencias/{agencia_id}", json={"activo": True}, headers=admin.headers)
    assert r.status_code == 200
    assert (await login(cliente, actor.username, CLAVE)).status_code == 200, "reactivada, vuelve a entrar"
