"""Separación entre Administrador (funcional) y SysAdmin (técnico).

  - SysAdmin: usuarios, roles, permisos y bitácora. No ve solicitudes.
  - Administrador: catálogos, trámites, estadísticas, bitácora y el flujo;
    puede listar usuarios y roles (para asignarlos a agencias y puestos),
    pero no crearlos ni cambiarlos.
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


async def test_administrador_lista_pero_no_crea_usuarios(cliente, admin):
    for ruta in ("/admin/usuarios", "/admin/roles", "/admin/bitacora", "/admin/agencias"):
        r = await cliente.get(ruta, headers=admin.headers)
        assert r.status_code == 200, ruta

    r = await cliente.post("/admin/usuarios/local", json=_cuenta_local(), headers=admin.headers)
    assert r.status_code == 403 and "SysAdmin" in r.json()["detail"]
    r = await cliente.post("/admin/roles", json={"nombre": f"Rol {secrets.token_hex(2)}", "descripcion": None},
                           headers=admin.headers)
    assert r.status_code == 403
    r = await cliente.get("/admin/permisos", headers=admin.headers)
    assert r.status_code == 403


async def test_no_se_queda_sin_sysadmin(cliente):
    unico = await crear_actor("SysAdmin", prefijo="sysadmin")
    # Deja a `unico` como el único SysAdmin activo de la BD de pruebas.
    id_sysadmin = await _id_rol("SysAdmin")
    async with SesionLocal() as s:
        await s.execute(update(Usuario).where(Usuario.rol_id == id_sysadmin, Usuario.id != unico.id)
                        .values(status=EstadoUsuario.INACTIVO))
        await s.commit()

    r = await cliente.patch(f"/admin/usuarios/{unico.id}/rol-personalizado",
                            json={"rol_id": await _id_rol("Administrador")}, headers=unico.headers)
    assert r.status_code == 409 and "único SysAdmin" in r.json()["detail"]

    r = await cliente.patch(f"/admin/roles/{id_sysadmin}", json={"nombre": "Soporte"}, headers=unico.headers)
    assert r.status_code == 400, "los roles de administración no se renombran"

    # Con otro SysAdmin activo, sí se puede.
    otro = await crear_actor("SysAdmin", prefijo="sysadmin")
    r = await cliente.patch(f"/admin/usuarios/{otro.id}/estado", json={"status": "inactive"}, headers=unico.headers)
    assert r.status_code == 200
    r = await cliente.patch(f"/admin/usuarios/{unico.id}/rol-personalizado",
                            json={"rol_id": await _id_rol("Administrador")}, headers=unico.headers)
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
