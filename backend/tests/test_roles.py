"""Roles fijos: Administrador y SysAdmin.

  - Administrador: acceso total (el flujo, catálogos, trámites, estadísticas,
    bitácora, usuarios, roles y permisos). Decisión del usuario del 2026-10-20.
  - SysAdmin: usuarios, roles, permisos y bitácora. No ve solicitudes.
  - Los permisos de los dos son fijos y nadie cambia su propio rol.
"""
import secrets

import pytest
from sqlalchemy import select, update

from app.domain.models.rol import Rol
from app.domain.models.user import EstadoUsuario, Usuario
from app.infrastructure.database import SesionLocal
from conftest import crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _cuenta_local(rol_id: int | None = None) -> dict:
    return {"username": f"local.{secrets.token_hex(3)}", "password": "Puerto-2026-Balboa",
            "name": "Cuenta", "last_name": "Local", "email": None, "rol_id": rol_id}


async def _id_rol(nombre: str) -> int:
    async with SesionLocal() as s:
        return (await s.execute(select(Rol.id).where(Rol.nombre == nombre))).scalar_one()


async def test_sysadmin_administra_usuarios_y_no_ve_solicitudes(cliente):
    sysadmin = await crear_actor("SysAdmin", prefijo="sysadmin")

    r = await cliente.post("/admin/usuarios/local", json=_cuenta_local(await _id_rol("Naviera")), headers=sysadmin.headers)
    assert r.status_code == 201, r.text
    nuevo = r.json()
    r = await cliente.patch(f"/admin/usuarios/{nuevo['id']}/rol-personalizado",
                            json={"rol_id": await _id_rol("Sector Pacífico")}, headers=sysadmin.headers)
    assert r.status_code == 200
    for ruta in ("/admin/usuarios", "/admin/roles", "/admin/permisos", "/admin/bitacora"):
        r = await cliente.get(ruta, headers=sysadmin.headers)
        assert r.status_code == 200, ruta

    for ruta in ("/solicitudes/revision", "/solicitudes/agencia", "/solicitudes/puerto", "/admin/agencias", "/admin/stats"):
        r = await cliente.get(ruta, headers=sysadmin.headers)
        assert r.status_code == 403, f"SysAdmin no entra a {ruta}"


async def test_administrador_tiene_acceso_total(cliente, admin):
    for ruta in ("/admin/usuarios", "/admin/roles", "/admin/permisos", "/admin/bitacora", "/admin/agencias",
                 "/admin/stats", "/solicitudes/revision", "/solicitudes/puerto"):
        r = await cliente.get(ruta, headers=admin.headers)
        assert r.status_code == 200, ruta

    r = await cliente.post("/admin/usuarios/local", json=_cuenta_local(await _id_rol("Naviera")), headers=admin.headers)
    assert r.status_code == 201, r.text
    r = await cliente.patch(f"/admin/usuarios/{r.json()['id']}/rol-personalizado",
                            json={"rol_id": await _id_rol("Puesto de Control")}, headers=admin.headers)
    assert r.status_code == 200
    r = await cliente.post("/admin/roles", json={"nombre": f"Rol {secrets.token_hex(2)}", "descripcion": None},
                           headers=admin.headers)
    assert r.status_code == 201


async def test_roles_fijos_y_rol_propio(cliente, admin):
    """El SysAdmin no se da permisos del flujo y nadie se cambia el rol a sí mismo."""
    sysadmin = await crear_actor("SysAdmin", prefijo="sysadmin")
    r = await cliente.get("/admin/permisos", headers=sysadmin.headers)
    revisar = next(p["id"] for p in r.json() if p["codigo"] == "T-PROCESAR-PACIFICO")
    for nombre in ("SysAdmin", "Administrador"):
        r = await cliente.put(f"/admin/roles/{await _id_rol(nombre)}/permisos", json={"permiso_ids": [revisar]},
                              headers=sysadmin.headers)
        assert r.status_code == 400 and "fijos" in r.json()["detail"], nombre

    for actor in (admin, sysadmin):
        r = await cliente.patch(f"/admin/usuarios/{actor.id}/rol-personalizado",
                                json={"rol_id": await _id_rol("Naviera")}, headers=actor.headers)
        assert r.status_code == 400 and "propio rol" in r.json()["detail"]


async def test_no_se_queda_sin_sysadmin(cliente, admin):
    unico = await crear_actor("SysAdmin", prefijo="sysadmin")
    # Deja a `unico` como el único SysAdmin activo de la BD de pruebas.
    id_sysadmin = await _id_rol("SysAdmin")
    async with SesionLocal() as s:
        await s.execute(update(Usuario).where(Usuario.rol_id == id_sysadmin, Usuario.id != unico.id)
                        .values(status=EstadoUsuario.INACTIVO))
        await s.commit()

    r = await cliente.patch(f"/admin/usuarios/{unico.id}/rol-personalizado",
                            json={"rol_id": await _id_rol("Administrador")}, headers=admin.headers)
    assert r.status_code == 409 and "único SysAdmin" in r.json()["detail"]
    r = await cliente.patch(f"/admin/usuarios/{unico.id}/estado", json={"status": "inactive"}, headers=admin.headers)
    assert r.status_code == 409

    r = await cliente.patch(f"/admin/roles/{id_sysadmin}", json={"nombre": "Soporte"}, headers=unico.headers)
    assert r.status_code == 400, "los roles de administración no se renombran"

    # Con otro SysAdmin activo, sí se puede.
    otro = await crear_actor("SysAdmin", prefijo="sysadmin")
    r = await cliente.patch(f"/admin/usuarios/{otro.id}/estado", json={"status": "inactive"}, headers=unico.headers)
    assert r.status_code == 200
    r = await cliente.patch(f"/admin/usuarios/{unico.id}/rol-personalizado",
                            json={"rol_id": await _id_rol("Administrador")}, headers=admin.headers)
    assert r.status_code == 409, "al desactivar al otro, vuelve a ser el único"


async def test_permisos_son_de_solo_lectura(cliente):
    """Los define el sistema: borrar uno dejaba el flujo sin acceso y crear uno no servía."""
    sysadmin = await crear_actor("SysAdmin", prefijo="sysadmin")
    r = await cliente.get("/admin/permisos", headers=sysadmin.headers)
    assert r.status_code == 200
    permiso = next(p for p in r.json() if p["codigo"] == "T-PROCESAR-PACIFICO")

    r = await cliente.post("/admin/permisos", json={"codigo": "X-1", "nombre": "X"}, headers=sysadmin.headers)
    assert r.status_code == 405
    for metodo in ("PATCH", "DELETE"):
        r = await cliente.request(metodo, f"/admin/permisos/{permiso['id']}", json={"nombre": "Otro"},
                                  headers=sysadmin.headers)
        assert r.status_code in (404, 405), metodo
    r = await cliente.get("/admin/permisos", headers=sysadmin.headers)
    assert any(p["codigo"] == "T-PROCESAR-PACIFICO" for p in r.json())
