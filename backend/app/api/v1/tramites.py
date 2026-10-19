from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import obtener_sesion_bd
from app.core.security import obtener_id_usuario_actual
from app.domain.models.tramite import TipoTramite, TramiteDocumento
from app.domain.repositories.tramite_repository import RepositorioTramite
from app.domain.schemas.tramite import (
    SalidaTipoTramite, SalidaTramiteDocumento,
)

enrutador = APIRouter(prefix="/tramites", tags=["tramites"])


def _mapear_documento(td: TramiteDocumento) -> SalidaTramiteDocumento:
    """Aplana el puente + el documento del catálogo en una fila del checklist."""
    return SalidaTramiteDocumento(
        id=td.id,
        documento_id=td.documento_id,
        codigo=td.documento.codigo,
        nombre=td.documento.nombre,
        descripcion=td.documento.descripcion,
        alcance=td.alcance,
        condicion=td.condicion,
        orden=td.orden or 0,
        requiere_libreta=td.documento.requiere_libreta,
    )


def mapear_tipo(tipo: TipoTramite) -> SalidaTipoTramite:
    return SalidaTipoTramite(
        id=tipo.id,
        codigo=tipo.codigo,
        nombre=tipo.nombre,
        formulario=tipo.formulario,
        requiere_buque=tipo.requiere_buque,
        requiere_puerto=tipo.requiere_puerto,
        requiere_puerto_desembarque=tipo.requiere_puerto_desembarque,
        requiere_motivo=tipo.requiere_motivo,
        requiere_clinica=tipo.requiere_clinica,
        valida_vigencia=tipo.valida_vigencia,
        rangos_permitidos=tipo.rangos_permitidos,
        aviso_custodia=tipo.aviso_custodia,
        descripcion=tipo.descripcion,
        nota=tipo.nota,
        orden=tipo.orden or 0,
        activo=tipo.activo,
        documentos=[_mapear_documento(td) for td in tipo.documentos],
    )


@enrutador.get("", response_model=list[SalidaTipoTramite])
async def listar_tipos_tramite(
    incluir_inactivos: bool = Query(default=False),
    _user_id: int = Depends(obtener_id_usuario_actual),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    """Catálogo de tipos de trámite con el checklist de documentos de cada uno.

    Lo consume el formulario de solicitud para saber qué campos y qué
    documentos pedir según el trámite que elija la naviera."""
    tipos = await RepositorioTramite(sesion).listar_tipos(solo_activos=not incluir_inactivos)
    return [mapear_tipo(t) for t in tipos]


@enrutador.get("/{codigo}", response_model=SalidaTipoTramite)
async def obtener_tipo_tramite(
    codigo:   str,
    _user_id: int = Depends(obtener_id_usuario_actual),
    sesion:   AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    tipo = await RepositorioTramite(sesion).buscar_tipo_por_codigo(codigo)
    if not tipo:
        raise HTTPException(status_code=404, detail=f"Tipo de trámite no encontrado: {codigo}.")
    return mapear_tipo(tipo)
