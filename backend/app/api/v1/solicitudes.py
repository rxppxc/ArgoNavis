"""Endpoints del flujo de Autorizaciones Marítimas.

Solo orquestan: las reglas viven en ServicioSolicitud y el armado de los
correos en ServicioNotificacion. Acá se registra la bitácora de cada acción y
se programan los avisos (salen después del commit, en segundo plano).
"""
import asyncio
from datetime import date
from typing import Annotated, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import usuario_actual
from app.core.email import Aviso, enviar_aviso
from app.core.http_utils import obtener_agente, obtener_ip
from app.core.pdf_autorizacion import generar_pdf_autorizacion
from app.core.permisos import PERMISO_PUERTO, PERMISO_REVISAR, PERMISO_SOLICITAR, requerir_permiso
from app.core.rate_limit import clave_usuario, limite_envios, limiter
from app.domain.models.audit_log import AccionAuditoria
from app.domain.models.solicitud import Solicitud
from app.domain.models.user import Usuario
from app.domain.repositories.audit_repository import RepositorioAuditoria
from app.domain.schemas.solicitud import (
    ConsultaBandeja, DatosAprobacion, DatosComentario, DatosCorregirSolicitud, DatosCrearSolicitud, DatosFinalizar,
    DatosImpedimentos, DatosMotivo, PaginaSolicitudes, SalidaEstadisticasSolicitudes, SalidaSolicitud,
)
from app.domain.services.notificacion_service import ServicioNotificacion
from app.domain.services.solicitud_service import ContextoAcceso, ServicioSolicitud
from app.infrastructure.database import obtener_sesion_bd

enrutador = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

M = TypeVar("M", bound=BaseModel)

_ETIQUETAS_CAMPO = {
    "codigo_tramite": "tipo de trámite",
    "puesto_control_id": "puesto de control", "fecha_operacion": "fecha de la operación",
    "nombre_buque": "nombre del buque", "imo": "IMO", "bandera": "bandera",
    "nombre_puerto": "nombre del puerto", "puerto_desembarque": "puerto de desembarque",
    "motivo": "motivo", "clinica_hospital": "clínica u hospital", "observaciones": "observaciones",
    "nombre": "nombre", "apellido": "apellido", "fecha_nacimiento": "fecha de nacimiento",
    "pais_nacimiento": "país de nacimiento", "nacionalidad": "nacionalidad", "sexo": "sexo",
    "pasaporte": "N° de pasaporte", "pasaporte_expira": "vencimiento del pasaporte",
    "libreta_marino": "N° de seamanbook", "libreta_expira": "vencimiento del seamanbook",
    "rango": "rango", "ocupacion": "ocupación",
}


# ── Dependencias y utilidades ────────────────────────────────────────────────

def _servicio(sesion: AsyncSession = Depends(obtener_sesion_bd, scope="function")) -> ServicioSolicitud:
    return ServicioSolicitud(sesion)


async def _contexto(
    usuario: Usuario = Depends(usuario_actual),
    svc:     ServicioSolicitud = Depends(_servicio),
) -> ContextoAcceso:
    return await svc.contexto(usuario)


def _describir_errores(exc: ValidationError) -> str:
    """Errores de validación del JSON del formulario, en lenguaje de usuario."""
    errores = exc.errors()
    partes = []
    for err in errores[:6]:
        loc = err.get("loc", ())
        if len(loc) >= 3 and loc[0] == "tripulantes" and isinstance(loc[1], int):
            sujeto = f"Tripulante {loc[1] + 1}, {_ETIQUETAS_CAMPO.get(str(loc[2]), str(loc[2]))}"
        elif loc:
            sujeto = _ETIQUETAS_CAMPO.get(str(loc[-1]), str(loc[-1]))
        else:
            sujeto = "formulario"
        tipo = err.get("type", "")
        if tipo == "missing":
            mensaje = "es obligatorio"
        elif tipo == "string_too_short":
            mensaje = "está vacío o es muy corto"
        elif tipo == "string_too_long":
            mensaje = "es demasiado largo"
        elif tipo.startswith("date"):
            mensaje = "no es una fecha válida"
        elif tipo == "literal_error":
            mensaje = "tiene un valor no permitido"
        else:
            mensaje = "no es válido"
        partes.append(f"{sujeto}: {mensaje}")
    extra = len(errores) - 6
    return "Revisa el formulario — " + "; ".join(partes) + (f" (y {extra} más)." if extra > 0 else ".")


def _leer_formulario(modelo: type[M], texto: str) -> M:
    try:
        return modelo.model_validate_json(texto)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_describir_errores(exc))


async def _auditar(
    sesion: AsyncSession, request: Request, usuario: Usuario,
    accion: AccionAuditoria, s: Solicitud, **extra,
) -> None:
    await RepositorioAuditoria(sesion).registrar(
        accion,
        user_id=usuario.id, username=usuario.username,
        detalle={"solicitud_id": s.id, "numero": s.numero, "estado": s.estado, **extra},
        ip=obtener_ip(request), agente=obtener_agente(request),
    )


def _programar(background_tasks: BackgroundTasks, avisos: list[Aviso]) -> None:
    for aviso in avisos:
        background_tasks.add_task(enviar_aviso, aviso)


# ── Bandejas ─────────────────────────────────────────────────────────────────

@enrutador.get("/agencia", response_model=PaginaSolicitudes)
async def bandeja_agencia(
    consulta: Annotated[ConsultaBandeja, Query()],
    _perm: int = Depends(requerir_permiso(PERMISO_SOLICITAR)),
    ctx:   ContextoAcceso = Depends(_contexto),
    svc:   ServicioSolicitud = Depends(_servicio),
):
    """Solicitudes de la agencia del usuario."""
    return await svc.bandeja_agencia(ctx, consulta)


@enrutador.get("/revision", response_model=PaginaSolicitudes)
async def bandeja_revision(
    consulta: Annotated[ConsultaBandeja, Query()],
    _perm: int = Depends(requerir_permiso(PERMISO_REVISAR)),
    ctx:   ContextoAcceso = Depends(_contexto),
    svc:   ServicioSolicitud = Depends(_servicio),
):
    """Todas las solicitudes, para UCVMM."""
    return await svc.bandeja_revision(ctx, consulta)


@enrutador.get("/puerto", response_model=PaginaSolicitudes)
async def bandeja_puerto(
    consulta: Annotated[ConsultaBandeja, Query()],
    _perm: int = Depends(requerir_permiso(PERMISO_PUERTO)),
    ctx:   ContextoAcceso = Depends(_contexto),
    svc:   ServicioSolicitud = Depends(_servicio),
):
    """Autorizaciones aprobadas de los puestos de control del usuario."""
    return await svc.bandeja_puerto(ctx, consulta)


@enrutador.get("/estadisticas", response_model=SalidaEstadisticasSolicitudes)
async def estadisticas(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    _perm: int = Depends(requerir_permiso(PERMISO_REVISAR)),
    svc:   ServicioSolicitud = Depends(_servicio),
):
    """Autorizaciones recibidas, aprobadas, denegadas y expiradas."""
    return await svc.estadisticas(desde, hasta)


# ── Agencia: crear y corregir ────────────────────────────────────────────────

@enrutador.post("", response_model=SalidaSolicitud, status_code=201)
@limiter.limit(limite_envios, key_func=clave_usuario)
async def crear_solicitud(
    request:          Request,
    background_tasks: BackgroundTasks,
    files:     list[UploadFile] = File(default=[], description="Un archivo por cada asignación."),
    solicitud: str              = Form(..., description="JSON con la cabecera, los tripulantes y las asignaciones."),
    _perm:   int            = Depends(requerir_permiso(PERMISO_SOLICITAR)),
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Envía una solicitud de autorización de la agencia a la cola de UCVMM."""
    datos = _leer_formulario(DatosCrearSolicitud, solicitud)
    s = await svc.crear(ctx, datos, files)

    await _auditar(
        sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_CREADA, s,
        tramite=datos.codigo_tramite, tripulantes=s.cantidad_tripulantes, documentos=len(s.documentos),
    )
    _programar(background_tasks, ServicioNotificacion(sesion).recibida(s, corregida=False))
    return await svc.construir_detalle(ctx, s)


@enrutador.put("/{solicitud_id}", response_model=SalidaSolicitud)
@limiter.limit(limite_envios, key_func=clave_usuario)
async def corregir_solicitud(
    solicitud_id:     int,
    request:          Request,
    background_tasks: BackgroundTasks,
    files:     list[UploadFile] = File(default=[], description="Documentos nuevos o de reemplazo."),
    solicitud: str              = Form(..., description="JSON con la solicitud corregida."),
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Reenvía a revisión una solicitud devuelta a corrección."""
    datos = _leer_formulario(DatosCorregirSolicitud, solicitud)
    s = await svc.corregir(ctx, solicitud_id, datos, files)

    await _auditar(
        sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_CORREGIDA, s,
        tripulantes=s.cantidad_tripulantes, documentos_nuevos=len(files),
    )
    _programar(background_tasks, ServicioNotificacion(sesion).recibida(s, corregida=True))
    return await svc.construir_detalle(ctx, s)


# ── Expediente ───────────────────────────────────────────────────────────────

@enrutador.get("/{solicitud_id}", response_model=SalidaSolicitud)
async def obtener_solicitud(
    solicitud_id: int,
    request: Request,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    s = await svc.obtener(ctx, solicitud_id)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_CONSULTADA, s)
    return await svc.construir_detalle(ctx, s)


@enrutador.get("/{solicitud_id}/documentos/{documento_id}")
async def obtener_documento(
    solicitud_id: int,
    documento_id: int,
    request:   Request,
    descargar: bool = Query(default=False, description="Descarga (true) o vista previa (false)."),
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Un documento del expediente. Solo con sesión y acceso a la solicitud;
    cada vista previa o descarga queda en la bitácora con el usuario real."""
    s, documento, ruta = await svc.obtener_documento(ctx, solicitud_id, documento_id)
    await _auditar(
        sesion, request, ctx.usuario,
        AccionAuditoria.DOCUMENTO_DESCARGADO if descargar else AccionAuditoria.DOCUMENTO_VISTO, s,
        documento_id=documento.id, nombre=documento.nombre_original,
    )
    return FileResponse(
        ruta,
        media_type=documento.tipo_mime or "application/octet-stream",
        filename=documento.nombre_original,
        content_disposition_type="attachment" if descargar else "inline",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@enrutador.get("/{solicitud_id}/autorizacion.pdf")
async def descargar_autorizacion(
    solicitud_id: int,
    request: Request,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """PDF de la autorización aprobada, verificable con su código QR."""
    s = await svc.obtener(ctx, solicitud_id)
    datos = await svc.preparar_pdf(ctx, s)
    contenido = await asyncio.to_thread(generar_pdf_autorizacion, datos)

    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.AUTORIZACION_DESCARGADA, s)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Autorizacion-{datos.numero}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# ── UCVMM: revisión ──────────────────────────────────────────────────────────

@enrutador.post("/{solicitud_id}/impedimentos", response_model=SalidaSolicitud)
async def registrar_impedimentos(
    solicitud_id: int,
    datos:   DatosImpedimentos,
    request: Request,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Registra (o corrige) la verificación de impedimentos (SIMPLUS) de cada tripulante y, opcional, un comentario."""
    s = await svc.registrar_impedimentos(ctx, solicitud_id, datos)
    await _auditar(
        sesion, request, ctx.usuario, AccionAuditoria.IMPEDIMENTOS_REGISTRADOS, s,
        con_impedimento=[d.tripulante_id for d in datos.tripulantes if d.con_impedimento],
        comentario=datos.comentario,
        motivo_correccion=datos.motivo_correccion,
    )
    return await svc.construir_detalle(ctx, s)


@enrutador.post("/{solicitud_id}/aprobar", response_model=SalidaSolicitud)
async def aprobar_solicitud(
    solicitud_id:     int,
    datos:            DatosAprobacion,
    request:          Request,
    background_tasks: BackgroundTasks,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Aprueba la autorización: avisa a la agencia y al puesto de control."""
    s = await svc.aprobar(ctx, solicitud_id, datos.observacion)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_APROBADA, s, observacion=datos.observacion)
    _programar(background_tasks, await ServicioNotificacion(sesion).aprobada(s))
    return await svc.construir_detalle(ctx, s)


@enrutador.post("/{solicitud_id}/devolver", response_model=SalidaSolicitud)
async def devolver_solicitud(
    solicitud_id:     int,
    datos:            DatosMotivo,
    request:          Request,
    background_tasks: BackgroundTasks,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Devuelve la solicitud a la agencia para que la corrija dentro del plazo."""
    s = await svc.devolver(ctx, solicitud_id, datos.motivo)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_DEVUELTA, s, motivo=datos.motivo)
    _programar(background_tasks, await ServicioNotificacion(sesion).devuelta(s))
    return await svc.construir_detalle(ctx, s)


@enrutador.post("/{solicitud_id}/negar", response_model=SalidaSolicitud)
async def negar_solicitud(
    solicitud_id:     int,
    datos:            DatosMotivo,
    request:          Request,
    background_tasks: BackgroundTasks,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    s = await svc.negar(ctx, solicitud_id, datos.motivo)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_NEGADA, s, motivo=datos.motivo)
    _programar(background_tasks, await ServicioNotificacion(sesion).negada(s))
    return await svc.construir_detalle(ctx, s)


# ── Puesto de control ────────────────────────────────────────────────────────

@enrutador.post("/{solicitud_id}/comentarios", response_model=SalidaSolicitud)
async def comentar_solicitud(
    solicitud_id: int,
    datos:   DatosComentario,
    request: Request,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """Comentario del puesto de control (queda con fecha, hora y usuario)."""
    s = await svc.comentar(ctx, solicitud_id, datos.comentario)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_COMENTADA, s, comentario=datos.comentario)
    return await svc.construir_detalle(ctx, s)


@enrutador.post("/{solicitud_id}/finalizar", response_model=SalidaSolicitud)
async def finalizar_solicitud(
    solicitud_id: int,
    datos:   DatosFinalizar,
    request: Request,
    ctx:     ContextoAcceso = Depends(_contexto),
    svc:     ServicioSolicitud = Depends(_servicio),
    sesion:  AsyncSession   = Depends(obtener_sesion_bd, scope="function"),
):
    """El puesto de control registra la operación y cierra la autorización,
    indicando en qué puesto terminó (por defecto, el autorizado)."""
    s = await svc.finalizar(ctx, solicitud_id, datos.comentario, datos.puesto_finalizacion_id)
    await _auditar(sesion, request, ctx.usuario, AccionAuditoria.SOLICITUD_FINALIZADA, s,
                   comentario=datos.comentario, puesto_finalizacion=s.puesto_finalizacion_nombre)
    return await svc.construir_detalle(ctx, s)
