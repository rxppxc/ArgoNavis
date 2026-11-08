"""Asigna un rol a un usuario desde la consola del servidor.

Sirve para nombrar al primer SysAdmin (desde la interfaz solo un Administrador
o un SysAdmin puede asignar roles) o para recuperar el acceso si se perdió.
Queda en la bitácora como una acción hecha desde la consola.

En una instalación nueva no hay ningún usuario, y el login del AD solo deja
entrar a cuentas ya registradas: el primero se crea aquí mismo.
  --crear-ad     si no existe, lo busca en el Active Directory y lo da de alta.
  --crear-local  si no existe, crea una cuenta local con una contraseña
                 temporal (se muestra una sola vez y hay que cambiarla al entrar;
                 necesita PERMITIR_LOGIN_LOCAL=true).

Uso (desde backend/):
    venv\\Scripts\\python -m app.infrastructure.asignar_rol <usuario> <rol> [--crear-ad | --crear-local]
Ejemplos:
    venv\\Scripts\\python -m app.infrastructure.asignar_rol jperez SysAdmin
    venv\\Scripts\\python -m app.infrastructure.asignar_rol jperez SysAdmin --crear-ad
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.config import obtener_configuracion
from app.core.ldap import servicio_ldap
from app.core.security import generar_contrasena_temporal, hashear_password
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.rol import Rol
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.repositories.user_repository import RepositorioUsuario
from app.infrastructure.database import SesionLocal, motor_bd


async def asignar(nombre_usuario: str, nombre_rol: str, *, crear: str | None = None) -> str:
    """`crear`: None (el usuario tiene que existir), "ad" o "local"."""
    mensajes: list[str] = []
    async with SesionLocal() as sesion:
        repo, bitacora = RepositorioUsuario(sesion), RepositorioAuditoria(sesion)
        rol = (await sesion.execute(select(Rol).where(Rol.nombre == nombre_rol))).scalar_one_or_none()
        if not rol:
            disponibles = ", ".join((await sesion.execute(select(Rol.nombre).order_by(Rol.nombre))).scalars())
            raise SystemExit(f"No existe el rol '{nombre_rol}'. Roles: {disponibles}.")

        usuario = await repo.buscar_por_nombre_usuario(nombre_usuario)
        if not usuario and crear is None:
            raise SystemExit(f"No existe el usuario '{nombre_usuario}'. Agrégalo con --crear-ad o --crear-local.")
        if not usuario and crear == "ad":
            datos = await asyncio.to_thread(servicio_ldap.buscar_usuario, nombre_usuario)
            if not datos:
                raise SystemExit(f"'{nombre_usuario}' no está en el Active Directory (o no se pudo consultar).")
            usuario = await repo.crear_desde_ldap(datos)
            mensajes.append(f"Se creó la cuenta del AD '{usuario.username}'.")
        elif not usuario and crear == "local":
            temporal = generar_contrasena_temporal()
            usuario = await repo.crear_local(
                username=nombre_usuario, password_hash=await asyncio.to_thread(hashear_password, temporal),
                name=None, last_name=None, email=None, rol_id=None,
            )
            mensajes.append(f"Se creó la cuenta local '{usuario.username}'. Contraseña temporal (se muestra "
                            f"una sola vez; se cambia al entrar): {temporal}")
            if not obtener_configuracion().PERMITIR_LOGIN_LOCAL:
                mensajes.append("Ojo: PERMITIR_LOGIN_LOCAL está en false; con eso la cuenta local no puede entrar.")
        if mensajes:
            await sesion.flush()
            await bitacora.registrar(
                AccionAuditoria.USUARIO_CREADO, username="consola",
                detalle={"usuario_id": usuario.id, "usuario": usuario.username, "origen": f"consola ({crear})"},
            )

        anterior = usuario.rol_id
        usuario.rol_id = rol.id
        await bitacora.registrar(
            AccionAuditoria.USUARIO_ACTUALIZADO, username="consola",
            detalle={"usuario_id": usuario.id, "usuario": usuario.username, "rol_id": rol.id,
                     "rol": rol.nombre, "rol_anterior_id": anterior, "origen": "consola"},
        )
        await sesion.commit()
    await motor_bd.dispose()
    return "\n".join([*mensajes, f"{usuario.username} ahora tiene el rol {nombre_rol}."])


if __name__ == "__main__":
    partes = argparse.ArgumentParser(description="Asigna un rol a un usuario (y lo crea si se pide).")
    partes.add_argument("usuario")
    partes.add_argument("rol")
    modo = partes.add_mutually_exclusive_group()
    modo.add_argument("--crear-ad", action="store_const", const="ad", dest="crear")
    modo.add_argument("--crear-local", action="store_const", const="local", dest="crear")
    argumentos = partes.parse_args()
    print(asyncio.run(asignar(argumentos.usuario, argumentos.rol, crear=argumentos.crear)))
