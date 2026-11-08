"""Notificaciones internas: la campana de la cabecera (reunión del 2026-10-30).

  - Pendientes: lo que le toca hacer a cada rol, con el mismo alcance que su
    bandeja. UCVMM, por revisar; la agencia, por corregir; el puesto de
    control, por finalizar; el Administrador, lo de UCVMM y del puesto.
  - Novedades: los pasos recientes de esas solicitudes, sacados del historial
    (`solicitud_eventos`) y filtrados como en el expediente (`evento_para`).
    No se cuentan las acciones del propio usuario.

No hay una tabla de notificaciones: lo único que se guarda es hasta cuándo vio
cada usuario sus novedades (`users.novedades_vistas_hasta`).
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.solicitud import EstadoSolicitud, TipoEventoSolicitud
from app.domain.models.user import Usuario
from app.domain.repositories.solicitud_repository import FiltrosBandeja, RepositorioSolicitud
from app.domain.schemas.pendientes import SalidaNovedad, SalidaPendiente, SalidaPendientes
from app.domain.services.solicitud_service import ServicioSolicitud, ahora_utc

VENTANA_NOVEDADES = timedelta(days=30)
MAX_NOVEDADES     = 20

Evento = TipoEventoSolicitud
# Qué pasos le interesan a cada rol (ninguno es interno del SNM).
EVENTOS_REVISION = {Evento.CREADA.value, Evento.CORREGIDA.value}
EVENTOS_PUERTO   = {Evento.APROBADA.value, Evento.EXPIRADA.value}
EVENTOS_AGENCIA  = {
    Evento.DEVUELTA.value, Evento.APROBADA.value, Evento.NEGADA.value, Evento.EXPIRADA.value, Evento.FINALIZADA.value,
}


@dataclass
class _Fuente:
    """Una bandeja del usuario: su pendiente y los pasos que le interesan."""
    clave:   str
    texto:   str
    bandeja: str
    estado:  str
    filtros: FiltrosBandeja
    eventos: set[str]


class ServicioPendientes:
    def __init__(self, sesion: AsyncSession):
        self.sesion      = sesion
        self.repo        = RepositorioSolicitud(sesion)
        self.solicitudes = ServicioSolicitud(sesion)

    async def _fuentes(self, usuario: Usuario) -> tuple[list[_Fuente], bool]:
        """Las bandejas del usuario, con el mismo alcance que en el panel, y si
        es personal del SNM (ve lo interno)."""
        ctx = await self.solicitudes.contexto(usuario)
        fuentes: list[_Fuente] = []
        if ctx.puede_revisar:
            fuentes.append(_Fuente("por_revisar", "Por revisar", "revision", EstadoSolicitud.EN_REVISION.value,
                                   FiltrosBandeja(), EVENTOS_REVISION))
        if ctx.es_admin or ctx.es_puerto:
            filtros = FiltrosBandeja(puestos_ids=None if ctx.es_admin else ctx.puestos_ids, solo_aprobadas_alguna_vez=True)
            fuentes.append(_Fuente("por_finalizar", "Por finalizar", "puerto", EstadoSolicitud.APROBADA.value,
                                   filtros, EVENTOS_PUERTO))
        if ctx.agencia_id is not None and (ctx.es_naviera or ctx.es_admin):
            fuentes.append(_Fuente("por_corregir", "Por corregir", "agencia", EstadoSolicitud.EN_CORRECCION.value,
                                   FiltrosBandeja(agencia_id=ctx.agencia_id), EVENTOS_AGENCIA))
        return fuentes, ctx.es_personal_snm

    async def consultar(self, usuario: Usuario) -> SalidaPendientes:
        fuentes, interno = await self._fuentes(usuario)
        if not fuentes:
            return SalidaPendientes(disponible=False)

        pendientes = []
        for f in fuentes:
            cantidad, vence_en = await self.repo.pendiente_en(f.filtros, f.estado)
            pendientes.append(SalidaPendiente(
                clave=f.clave, texto=f.texto, cantidad=cantidad, bandeja=f.bandeja, estado=f.estado,
                vence_en=vence_en,
            ))

        por_eventos = [(f.filtros, f.eventos) for f in fuentes]
        desde = ahora_utc() - VENTANA_NOVEDADES
        vistas = usuario.novedades_vistas_hasta
        novedades = []
        for evento, numero, titulo in await self.repo.novedades(
            por_eventos, desde=desde, excluir_usuario_id=usuario.id, limite=MAX_NOVEDADES,
        ):
            visible = ServicioSolicitud.evento_para(evento, interno)
            if visible is None:
                continue
            novedades.append(SalidaNovedad(
                id=evento.id, solicitud_id=evento.solicitud_id, numero=numero, titulo=titulo, tipo=visible.tipo,
                comentario=visible.comentario, usuario_nombre=visible.usuario_nombre, creado_en=visible.creado_en,
                no_leida=visible.creado_en > vistas,
            ))
        no_leidas = await self.repo.contar_novedades(
            por_eventos, despues_de=max(vistas, desde), excluir_usuario_id=usuario.id,
        )
        return SalidaPendientes(disponible=True, pendientes=pendientes, novedades=novedades, no_leidas=no_leidas)

    async def marcar_vistas(self, usuario: Usuario) -> None:
        """Abrió la campana: las novedades hasta ahora quedan leídas."""
        usuario.novedades_vistas_hasta = ahora_utc()
        await self.sesion.flush()
