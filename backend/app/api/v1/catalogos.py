"""Catálogos del flujo de Autorizaciones Marítimas.

  - Lectura (cualquier usuario autenticado): puestos de control activos (con el
    número de su sector, para el cambio de puerto) y países, para llenar el
    formulario de solicitud.
  - Administración (solo admin):
      · sectores de UCVMM (Pacífico y Atlántico): su buzón y sus funcionarios
        (UCVMM y supervisores de sector), 2026-11-10;
      · puestos de control, su sector y los funcionarios asignados a cada uno;
      · agencias navieras y sus usuarios (comparten las solicitudes de la agencia);
      · marca de nacionalidades restringidas.

Las reglas viven en domain/services/catalogo_service.py (desde el 2026-11-14):
aquí se orquesta, se arma la salida y se deja la bitácora.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import auditar_admin, obtener_id_usuario_actual, requerir_admin
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl, Sector
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.schemas.catalogo import (
    DatosActualizarAgencia, DatosActualizarPais, DatosActualizarPuesto, DatosActualizarSector, DatosAsignarUsuarios,
    DatosCrearAgencia, DatosCrearPuesto, SalidaAgencia, SalidaCatalogoConUsuarios, SalidaCatalogoMini,
    SalidaPais, SalidaPuesto, SalidaPuestoFormulario, SalidaSector, UsuarioAsignado,
)
from app.domain.services.catalogo_service import ServicioCatalogos
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(tags=["catalogos"])

Entidad = PuestoControl | AgenciaNaviera


def _usuarios(entidad: Entidad | Sector) -> list[UsuarioAsignado]:
    return [UsuarioAsignado(id=u.id, username=u.username, full_name=u.full_name) for u in entidad.usuarios]


def _salida(clase: type[SalidaCatalogoConUsuarios], entidad: Entidad, totales: dict[int, int]) -> SalidaCatalogoConUsuarios:
    extra = {"sector_id": entidad.sector_id, "sector_nombre": entidad.sector.nombre} if clase is SalidaPuesto else {}
    return clase(
        id=entidad.id, nombre=entidad.nombre, correo=entidad.correo, activo=entidad.activo,
        usuarios=_usuarios(entidad), total_solicitudes=totales.get(entidad.id, 0), **extra,
    )


def _salida_sector(sector: Sector) -> SalidaSector:
    return SalidaSector(
        id=sector.id, nombre=sector.nombre, correo=sector.correo, usuarios=_usuarios(sector),
        puestos=[SalidaCatalogoMini(id=pu.id, nombre=pu.nombre) for pu in sector.puestos],
    )


# ── Lectura para el formulario ───────────────────────────────────────────────

@enrutador.get("/catalogos/puestos", response_model=list[SalidaPuestoFormulario])
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
    svc = ServicioCatalogos(sesion)
    puesto = await svc.crear_puesto(datos)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_CREADO,
                        {"puesto_id": puesto.id, "nombre": puesto.nombre, "correo": puesto.correo,
                         "sector": puesto.sector.nombre})
    puesto = await svc.puesto(puesto.id, con_usuarios=True)
    return _salida(SalidaPuesto, puesto, {})


@enrutador.patch("/admin/puestos/{puesto_id}", response_model=SalidaPuesto)
async def actualizar_puesto(
    puesto_id: int,
    datos:     DatosActualizarPuesto,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    svc = ServicioCatalogos(sesion)
    puesto, cambios = await svc.actualizar_puesto(puesto_id, datos)
    if cambios:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_ACTUALIZADO,
                            {"puesto_id": puesto.id, **cambios})
    return _salida(SalidaPuesto, puesto, await svc.repo.contar_solicitudes_por_puesto())


@enrutador.delete("/admin/puestos/{puesto_id}", status_code=204)
async def eliminar_puesto(
    puesto_id: int,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    puesto = await ServicioCatalogos(sesion).eliminar_puesto(puesto_id)
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
    svc = ServicioCatalogos(sesion)
    puesto, ids = await svc.asignar_usuarios_puesto(puesto_id, datos.usuario_ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.PUESTO_ACTUALIZADO,
                        {"puesto_id": puesto_id, "usuarios_asignados": ids})
    sesion.expire(puesto, ["usuarios"])
    puesto = await svc.puesto(puesto_id, con_usuarios=True)
    return _salida(SalidaPuesto, puesto, await svc.repo.contar_solicitudes_por_puesto())


# ── Administración de sectores de UCVMM ──────────────────────────────────────

@enrutador.get("/admin/sectores", response_model=list[SalidaSector])
async def listar_sectores(
    _admin: int = Depends(requerir_admin),
    sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Los dos sectores, con sus puestos y sus funcionarios asignados."""
    return [_salida_sector(x) for x in await RepositorioCatalogo(sesion).listar_sectores(con_usuarios=True)]


@enrutador.patch("/admin/sectores/{sector_id}", response_model=SalidaSector)
async def actualizar_sector(
    sector_id: int,
    datos:     DatosActualizarSector,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """El buzón que recibe el aviso de cada solicitud nueva del sector (sin buzón,
    va al general de UCVMM)."""
    sector, cambio = await ServicioCatalogos(sesion).cambiar_correo_sector(sector_id, datos.correo)
    if cambio:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.SECTOR_ACTUALIZADO,
                            {"sector_id": sector.id, "sector": sector.nombre, "correo": sector.correo})
    return _salida_sector(sector)


@enrutador.put("/admin/sectores/{sector_id}/usuarios", response_model=SalidaSector)
async def asignar_usuarios_sector(
    sector_id: int,
    datos:     DatosAsignarUsuarios,
    request:   Request,
    admin_id:  int = Depends(requerir_admin),
    sesion:    AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Reemplaza los funcionarios del sector. Un revisor puede estar en los dos
    (vacaciones, refuerzos): ve las solicitudes de los puestos de ambos."""
    svc = ServicioCatalogos(sesion)
    sector, ids = await svc.asignar_usuarios_sector(sector_id, datos.usuario_ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.SECTOR_ACTUALIZADO,
                        {"sector_id": sector_id, "sector": sector.nombre, "usuarios_asignados": ids})
    sesion.expire(sector, ["usuarios"])
    sector = await svc.sector(sector_id, con_usuarios=True)
    return _salida_sector(sector)


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
    svc = ServicioCatalogos(sesion)
    agencia = await svc.crear_agencia(datos)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_CREADA,
                        {"agencia_id": agencia.id, "nombre": agencia.nombre, "correo": agencia.correo})
    agencia = await svc.agencia(agencia.id, con_usuarios=True)
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
    svc = ServicioCatalogos(sesion)
    agencia, cambios = await svc.actualizar_agencia(agencia_id, datos)
    if cambios:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_ACTUALIZADA,
                            {"agencia_id": agencia.id, **cambios})
    return _salida(SalidaAgencia, agencia, await svc.repo.contar_solicitudes_por_agencia())


@enrutador.delete("/admin/agencias/{agencia_id}", status_code=204)
async def eliminar_agencia(
    agencia_id: int,
    request:    Request,
    admin_id:   int = Depends(requerir_admin),
    sesion:     AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Solo una agencia sin solicitudes; sus usuarios quedan sin agencia."""
    agencia = await ServicioCatalogos(sesion).eliminar_agencia(agencia_id)
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
    svc = ServicioCatalogos(sesion)
    ids = await svc.asignar_usuarios_agencia(agencia_id, datos.usuario_ids)
    await auditar_admin(sesion, request, admin_id, AccionAuditoria.AGENCIA_ACTUALIZADA,
                        {"agencia_id": agencia_id, "usuarios_asignados": ids})
    # Los UPDATE masivos no tocan los objetos ya cargados: se releen.
    sesion.expire_all()
    agencia = await svc.agencia(agencia_id, con_usuarios=True)
    return _salida(SalidaAgencia, agencia, await svc.repo.contar_solicitudes_por_agencia())


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
    pais, cambio = await ServicioCatalogos(sesion).marcar_restringida(codigo, datos.nacionalidad_restringida)
    if cambio:
        await auditar_admin(sesion, request, admin_id, AccionAuditoria.PAIS_ACTUALIZADO,
                            {"codigo": pais.codigo, "nombre": pais.nombre,
                             "nacionalidad_restringida": pais.nacionalidad_restringida})
    return pais
