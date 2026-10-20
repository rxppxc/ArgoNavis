"""Asigna un rol a un usuario existente desde la consola del servidor.

Sirve para nombrar al primer SysAdmin (desde la interfaz solo un Administrador
o un SysAdmin puede asignar roles) o para recuperar el acceso si se perdió.
Queda en la bitácora como una acción hecha desde la consola.

Uso (desde backend/):
    venv\\Scripts\\python -m app.infrastructure.asignar_rol <usuario> <rol>
Ejemplo:
    venv\\Scripts\\python -m app.infrastructure.asignar_rol jperez SysAdmin
"""
import asyncio
import sys

from sqlalchemy import select

from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.rol import Rol
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.repositories.user_repository import RepositorioUsuario
from app.infrastructure.database import SesionLocal, motor_bd


async def asignar(nombre_usuario: str, nombre_rol: str) -> str:
    async with SesionLocal() as sesion:
        usuario = await RepositorioUsuario(sesion).buscar_por_nombre_usuario(nombre_usuario)
        if not usuario:
            raise SystemExit(f"No existe el usuario '{nombre_usuario}'. Agrégalo primero (AD o cuenta local).")
        rol = (await sesion.execute(select(Rol).where(Rol.nombre == nombre_rol))).scalar_one_or_none()
        if not rol:
            disponibles = ", ".join((await sesion.execute(select(Rol.nombre).order_by(Rol.nombre))).scalars())
            raise SystemExit(f"No existe el rol '{nombre_rol}'. Roles: {disponibles}.")
        anterior = usuario.rol_id
        usuario.rol_id = rol.id
        await RepositorioAuditoria(sesion).registrar(
            AccionAuditoria.USUARIO_ACTUALIZADO, username="consola",
            detalle={"usuario_id": usuario.id, "usuario": usuario.username, "rol_id": rol.id,
                     "rol": rol.nombre, "rol_anterior_id": anterior, "origen": "consola"},
        )
        await sesion.commit()
    await motor_bd.dispose()
    return f"{nombre_usuario} ahora tiene el rol {nombre_rol}."


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(asyncio.run(asignar(sys.argv[1], sys.argv[2])))
