"""Verificación pública del QR de una Autorización Marítima.

Endpoints sin autenticación (los abre quien escanea el PDF, también desde un
celular sin VPN cuando la DTI publique la verificación: README → «Verificación
pública del QR»), con rate limit por IP: el código es aleatorio de 192 bits,
pero igual se frena el barrido.

  - GET /verificacion/{codigo}: lo mínimo para comprobar que la autorización es
    auténtica y si sigue vigente, con los pasaportes enmascarados.
  - GET /verificacion/{codigo}/autorizacion.pdf (2026-11-14): el PDF, la copia de
    la agencia (sin nombres de funcionarios), mientras valga y hasta
    DIAS_PDF_PUBLICO días después de la operación. Si no, lleva a la página de
    verificación, que explica por qué: quien escanea nunca queda en una pantalla
    sin salida. Los documentos del expediente nunca salen por aquí (regla 10).
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencias import auditar
from app.core.rate_limit import limite_pdf_publico, limite_verificacion, limiter
from app.domain.models.audit_log import AccionAuditoria
from app.domain.schemas.solicitud import SalidaVerificacion
from app.domain.services.solicitud_service import ServicioSolicitud
from app.informes.autorizacion_pdf import generar_pdf_autorizacion
from app.infrastructure.database import obtener_sesion_bd
from app.infrastructure.trabajo_pesado import en_hilo_con_tope

enrutador = APIRouter(prefix="/verificacion", tags=["verificacion"])

# El código del QR (secrets.token_urlsafe): solo letras, números, «-» y «_».
_FORMATO_CODIGO = r"^[A-Za-z0-9_-]{1,64}$"


@enrutador.get("/{codigo}", response_model=SalidaVerificacion)
@limiter.limit(limite_verificacion)
async def verificar_autorizacion(
    request: Request,
    codigo:  str,
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    resultado = await ServicioSolicitud(sesion).verificar(codigo)
    await auditar(sesion, request, AccionAuditoria.AUTORIZACION_VERIFICADA,
                  detalle={"numero": resultado.numero, "estado": resultado.estado, "valida": resultado.valida})
    return resultado


@enrutador.get("/{codigo}/autorizacion.pdf")
@limiter.limit(limite_pdf_publico)
async def ver_autorizacion_publica(
    request: Request,
    codigo:  str = Path(pattern=_FORMATO_CODIGO),
    sesion:  AsyncSession = Depends(obtener_sesion_bd, scope="function"),
):
    datos = await ServicioSolicitud(sesion).pdf_publico(codigo)
    if datos is None:
        # Código que no existe, o autorización que ya no se puede ver así: a la
        # página de verificación, que dice qué pasa (y no un JSON en el celular).
        return RedirectResponse(f"/verificar/{quote(codigo, safe='')}", status_code=303)
    # La conexión vuelve al pool mientras se arma el PDF (con turno, trabajo_pesado.py).
    await sesion.commit()
    contenido = await en_hilo_con_tope(generar_pdf_autorizacion, datos)
    await auditar(sesion, request, AccionAuditoria.AUTORIZACION_DESCARGADA,
                  detalle={"numero": datos.numero, "estado": datos.estado, "publica": True})
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            # En el visor del navegador (en Android se descarga y se abre): verlo es lo que se pide.
            "Content-Disposition": f'inline; filename="Autorizacion-{datos.numero}.pdf"',
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
