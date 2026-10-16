"""Catálogos del flujo de Autorizaciones Marítimas.

  - Lectura (cualquier usuario autenticado): puestos de control activos y
    países, para llenar el formulario de solicitud.
  - Administración (solo admin):
      · puestos de control y los funcionarios asignados a cada uno;
      · agencias navieras y sus usuarios (comparten las solicitudes de la agencia);
      · marca de nacionalidades restringidas.
"""
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import auditar_admin
from app.core.permisos import requerir_admin
from app.core.security import obtener_id_usuario_actual
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.catalogo import (
    DatosActualizarAgencia, DatosActualizarPais, DatosActualizarPuesto, DatosAsignarUsuarios,
    DatosCrearAgencia, DatosCrearPuesto, SalidaAgencia, SalidaCatalogoConUsuarios, SalidaCatalogoMini,
    SalidaPais, SalidaPuesto, UsuarioAsignado,
)
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(tags=["catalogos"])

Entidad = PuestoControl | AgenciaNaviera


def _salida(clase: type[SalidaCatalogoConUsuarios], entidad: Entidad, totales: dict[int, int]) -> SalidaCatalogoConUsuarios:
    return clase(
        id=entidad.id, nombre=entidad.nombre, correo=entidad.correo, activo=entidad.activo,
        usuarios=[
            UsuarioAsignado(id=u.id, username=u.username, full_name=u.full_name)
            for u in entidad.usuarios
        ],
        total_solicitudes=totales.get(entidad.id, 0),
    )


async def _aplicar_cambios(
    entidad: Entidad,
    datos: DatosActualizarPuesto | DatosActualizarAgencia,
    buscar_por_nombre: Callable[[str], Awaitable[Entidad | None]],
    duplicado: str,
) -> dict:
    """Aplica nombre/correo/activo y devuelve lo que cambió (para la bitácora)."""
    cambios: dict = {}
    if datos.nombre is not None and datos.nombre != entidad.nombre:
        otro = await buscar_por_nombre(datos.nombre)
        if otro and otro.id != entidad.id:
            raise HTTPException(status_code=409, detail=duplicado)
        cambios["nombre"] = entidad.nombre = datos.nombre
    if "correo" in datos.model_fields_set and datos.correo != entidad.correo:
        cambios["correo"] = entidad.correo = datos.correo
    if datos.activo is not None and datos.activo != entidad.activo:
        cambios["activo"] = entidad.activo = datos.activo
    return cambios


async def _validar_usuarios(sesion: AsyncSession, usuario_ids: list[int]) -> list[int]:
    ids = sorted(set(usuario_ids))
    faltan = set(ids) - await RepositorioUsuario(sesion).ids_existentes(ids)
    if faltan:
        raise HTTPException(status_code=400, detail=f"Usuarios no encontrados: {sorted(faltan)}.")
    return ids


# ── Lectura para el formulario ───────────────────────────────────────────────

@enrutador.get("/catalogos/puestos", response_model=list[SalidaCatalogoMini])
async def listar_puestos_activos(
    _user_id: int = Depends(obtener_id_usuario_actual),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    return await RepositorioCatalogo(sesion).listar_puestos(solo_activos=True)


@enrutador.get("/catalogos/paises", response_model=list[SalidaPais])
async def listar_paises(
    _user_id: int = Depends(obtener_id_usuario_actual),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    return await RepositorioCatalogo(sesion).listar_paises()


# ── Administración de puestos de control ─────────────────────────────────────

@enrutador.get("/admin/puestos", response_model=list[SalidaPuesto])
async def listar_puestos(
    _admin: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    totales = await repo.contar_solicitudes_por_puesto()
    return [_salida(SalidaPuesto, p, totales) for p in await repo.listar_puestos(con_usuarios=True)]


@enrutador.post("/admin/puestos", response_model=SalidaPuesto, status_code=201)
async def crear_puesto(
    datos:    DatosCrearPuesto,
    request:  Request,
    admin_id: int = Depends(requerir_admin),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    if await repo.buscar_puesto_por_nombre(datos.nombre):
        raise HTTPException(status_code=409, detail="Ya existe un puesto de control con ese nombre.")
    puesto = PuestoControl(nombre=datos.nombre, correo=datos.correo, activo=True)
    repo.agregar(puesto)
    await sesion.flush()
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_CREADO,
                        {"puesto_id": puesto.id, "nombre": puesto.nombre, "correo": puesto.correo})
    puesto = await repo.buscar_puesto(puesto.id, con_usuarios=True)
    return _salida(SalidaPuesto, puesto, {})


@enrutador.patch("/admin/puestos/{puesto_id}", response_model=SalidaPuesto)
async def actualizar_puesto(
    puesto_id: int,
    datos:     DatosActualizarPuesto,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    puesto = await repo.buscar_puesto(puesto_id, con_usuarios=True)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto de control no encontrado.")
    cambios = await _aplicar_cambios(
        puesto, datos, repo.buscar_puesto_por_nombre, "Ya existe otro puesto de control con ese nombre.",
    )
    await sesion.flush()
    if cambios:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_ACTUALIZADO,
                            {"puesto_id": puesto.id, **cambios})
    return _salida(SalidaPuesto, puesto, await repo.contar_solicitudes_por_puesto())


@enrutador.delete("/admin/puestos/{puesto_id}", status_code=204)
async def eliminar_puesto(
    puesto_id: int,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    puesto = await repo.buscar_puesto(puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto de control no encontrado.")
    if await repo.puesto_en_uso(puesto_id):
        raise HTTPException(
            status_code=409,
            detail="El puesto tiene solicitudes registradas (autorizadas o finalizadas en él): "
                   "desactívalo en lugar de eliminarlo.",
        )
    await repo.eliminar(puesto)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_ELIMINADO,
                        {"puesto_id": puesto_id, "nombre": puesto.nombre})


@enrutador.put("/admin/puestos/{puesto_id}/usuarios", response_model=SalidaPuesto)
async def asignar_usuarios_puesto(
    puesto_id: int,
    datos:     DatosAsignarUsuarios,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Reemplaza la lista de funcionarios asignados al puesto."""
    repo = RepositorioCatalogo(sesion)
    puesto = await repo.buscar_puesto(puesto_id)
    if not puesto:
        raise HTTPException(status_code=404, detail="Puesto de control no encontrado.")
    ids = await _validar_usuarios(sesion, datos.usuario_ids)
    await repo.reemplazar_usuarios_de_puesto(puesto_id, ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_ACTUALIZADO,
                        {"puesto_id": puesto_id, "usuarios_asignados": ids})

    sesion.expire(puesto, ["usuarios"])
    puesto = await repo.buscar_puesto(puesto_id, con_usuarios=True)
    return _salida(SalidaPuesto, puesto, await repo.contar_solicitudes_por_puesto())


# ── Administración de agencias navieras ──────────────────────────────────────

@enrutador.get("/admin/agencias", response_model=list[SalidaAgencia])
async def listar_agencias(
    _admin: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    totales = await repo.contar_solicitudes_por_agencia()
    return [_salida(SalidaAgencia, a, totales) for a in await repo.listar_agencias(con_usuarios=True)]


@enrutador.post("/admin/agencias", response_model=SalidaAgencia, status_code=201)
async def crear_agencia(
    datos:    DatosCrearAgencia,
    request:  Request,
    admin_id: int = Depends(requerir_admin),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    repo = RepositorioCatalogo(sesion)
    if await repo.buscar_agencia_por_nombre(datos.nombre):
        raise HTTPException(status_code=409, detail="Ya existe una agencia naviera con ese nombre.")
    agencia = AgenciaNaviera(nombre=datos.nombre, correo=datos.correo, activo=True)
    repo.agregar(agencia)
    await sesion.flush()
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_CREADA,
                        {"agencia_id": agencia.id, "nombre": agencia.nombre, "correo": agencia.correo})
    agencia = await repo.buscar_agencia(agencia.id, con_usuarios=True)
    return _salida(SalidaAgencia, agencia, {})


@enrutador.patch("/admin/agencias/{agencia_id}", response_model=SalidaAgencia)
async def actualizar_agencia(
    agencia_id: int,
    datos:      DatosActualizarAgencia,
    request:    Request,
    admin_id:   int = Depends(requerir_admin),
    sesion:     AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Nombre, buzón y estado. Las solicitudes ya enviadas conservan el nombre
    que tenía la agencia al enviarlas. Una agencia inactiva no envía nuevas."""
    repo = RepositorioCatalogo(sesion)
    agencia = await repo.buscar_agencia(agencia_id, con_usuarios=True)
    if not agencia:
        raise HTTPException(status_code=404, detail="Agencia naviera no encontrada.")
    cambios = await _aplicar_cambios(
        agencia, datos, repo.buscar_agencia_por_nombre, "Ya existe otra agencia naviera con ese nombre.",
    )
    await sesion.flush()
    if cambios:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_ACTUALIZADA,
                            {"agencia_id": agencia.id, **cambios})
    return _salida(SalidaAgencia, agencia, await repo.contar_solicitudes_por_agencia())


@enrutador.delete("/admin/agencias/{agencia_id}", status_code=204)
async def eliminar_agencia(
    agencia_id: int,
    request:    Request,
    admin_id:   int = Depends(requerir_admin),
    sesion:     AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Solo una agencia sin solicitudes; sus usuarios quedan sin agencia."""
    repo = RepositorioCatalogo(sesion)
    agencia = await repo.buscar_agencia(agencia_id)
    if not agencia:
        raise HTTPException(status_code=404, detail="Agencia naviera no encontrada.")
    if (await repo.contar_solicitudes_por_agencia()).get(agencia_id):
        raise HTTPException(
            status_code=409,
            detail="La agencia tiene solicitudes registradas: desactívala en lugar de eliminarla.",
        )
    await repo.eliminar(agencia)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_ELIMINADA,
                        {"agencia_id": agencia_id, "nombre": agencia.nombre})


@enrutador.put("/admin/agencias/{agencia_id}/usuarios", response_model=SalidaAgencia)
async def asignar_usuarios_agencia(
    agencia_id: int,
    datos:      DatosAsignarUsuarios,
    request:    Request,
    admin_id:   int = Depends(requerir_admin),
    sesion:     AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Reemplaza los usuarios de la agencia. Un usuario es de una sola agencia:
    asignarlo aquí lo saca de la que tuviera."""
    repo = RepositorioCatalogo(sesion)
    agencia = await repo.buscar_agencia(agencia_id)
    if not agencia:
        raise HTTPException(status_code=404, detail="Agencia naviera no encontrada.")
    ids = await _validar_usuarios(sesion, datos.usuario_ids)
    await repo.reemplazar_usuarios_de_agencia(agencia_id, ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_ACTUALIZADA,
                        {"agencia_id": agencia_id, "usuarios_asignados": ids})

    # Los UPDATE masivos no tocan los objetos ya cargados: se releen.
    sesion.expire_all()
    agencia = await repo.buscar_agencia(agencia_id, con_usuarios=True)
    return _salida(SalidaAgencia, agencia, await repo.contar_solicitudes_por_agencia())


# ── Administración de países (nacionalidades restringidas) ───────────────────

@enrutador.patch("/admin/paises/{codigo}", response_model=SalidaPais)
async def actualizar_pais(
    codigo:   str,
    datos:    DatosActualizarPais,
    request:  Request,
    admin_id: int = Depends(requerir_admin),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Marca o desmarca una nacionalidad como restringida. Aplica a las
    solicitudes que se envíen desde ahora (las ya enviadas guardan su foto)."""
    pais = await RepositorioCatalogo(sesion).buscar_pais(codigo)
    if not pais:
        raise HTTPException(status_code=404, detail="País no encontrado.")
    if pais.nacionalidad_restringida != datos.nacionalidad_restringida:
        pais.nacionalidad_restringida = datos.nacionalidad_restringida
        await sesion.flush()
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.PAIS_ACTUALIZADO,
                            {"codigo": pais.codigo, "nombre": pais.nombre,
                             "nacionalidad_restringida": pais.nacionalidad_restringida})
    return pais
