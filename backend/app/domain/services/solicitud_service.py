"""Flujo de Autorizaciones Marítimas (según el documento de UCVMM).

    Agencia envía ──► review ──aprobar──► approved ──finalizar──► finalized
                       │  ▲                  │
              devolver │  │ corregir         └─(no se finalizó a tiempo)─► expired
                       ▼  │
                     returned ──(no se corrigió en el plazo)──► expired

    review ──negar──► denied

  - La solicitud es de la agencia naviera: cualquier usuario de la agencia
    (permiso T-CREAR-BASICA) la ve, la corrige y descarga la autorización.
  - UCVMM (T-PROCESAR-PACIFICO) revisa: registra la verificación de
    impedimentos (obligatoria para aprobar), aprueba, devuelve a corrección
    con plazo (PLAZO_CORRECCION_DIAS) o niega. Nadie revisa una solicitud que
    creó o que es de su propia agencia (separación de funciones).
  - El puesto de control (T-FINALIZAR-PUERTO + asignación en
    `usuarios_puestos`) ve las aprobadas de sus puestos, verifica los
    impedimentos (obligatoria para finalizar) y las finaliza. Con cambio de
    puerto (2026-11-13), las ve y las finaliza el puesto nuevo
    (`puesto_autorizado_id`); el primero no las ve desde el 2026-11-22.
  - Cada transición bloquea la fila (SELECT ... FOR UPDATE): dos usuarios no
    pueden, por ejemplo, aprobar y negar la misma solicitud a la vez.
  - Cada paso queda en `solicitud_eventos` (historial con usuario y hora).
"""
import asyncio
import logging
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obtener_configuracion
from app.core.horario import TEXTO_HORARIO, ZONA_PANAMA, fuera_de_horario, texto_costo
from app.core.identidad import INSTITUCION
from app.core.permisos import (
    PERMISO_PUERTO, PERMISO_REVISAR, PERMISO_SOLICITAR, PERMISO_SUPERVISAR_SECTOR, PERMISO_SUPERVISAR_TODO,
    codigos_permiso, es_admin_efectivo,
)
from app.domain.models.boleta import BoletaRecargo
from app.domain.models.catalogo import PuestoControl
from app.domain.models.solicitud import (
    aviso_impedimentos,
    ETIQUETA_OPERACION, RANGOS_CON_LIBRETA, CasillaSolicitud, DocumentoEmitido, DocumentoSolicitud,
    EstadoSolicitud, EventoSolicitud, OperacionTecnico, Solicitud, TipoEmitido, TipoEventoSolicitud,
    TripulanteSolicitud, VersionSolicitud, texto_dias, vigencia_minima_pasaporte,
)
from app.domain.models.tramite import AlcanceDocumento, TipoTramite, TramiteDocumento
from app.domain.models.user import Usuario
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.solicitud_repository import (
    AlcanceSectores, AlcanceSnm, FiltrosBandeja, RepositorioSolicitud,
)
from app.domain.repositories.tramite_repository import RepositorioTramite
from app.domain.schemas.solicitud import (
    AccionesSolicitud, AsignacionArchivo, ConsultaBandeja, ConsultaHistorica, DatosCorregirSolicitud,
    DatosCrearSolicitud, DatosImpedimentos, DatosTripulanteEntrada, FilaEstadisticaPuesto, FilaSector,
    FilaEstadisticaTipo, FilaFueraHorario, FilaPorHora, PaginaSolicitudes,
    SalidaArchivo, SalidaCasilla,
    SalidaDocumentoSolicitud, SalidaEstadisticasSolicitudes, SalidaEvento, SalidaRegistro, SalidaSolicitud,
    OpcionFiltro, SalidaOpcionesHistorico, SalidaSolicitudResumen, SalidaTripulante,
    SalidaTripulanteEncontrado, SalidaTripulanteVerificacion, SalidaVerificacion, SalidaVersion,
    _DatosFormularioSolicitud, SalidaBoleta,
)
from app.domain.services.acceso import AlcanceEstadisticas, ContextoAcceso
from app.domain.services.series import meses_antes, periodos_anio, periodos_dia, periodos_mes, serie
from app.domain.services.tramite_service import (
    CasillaChecklist, ServicioTramite, TripulanteChecklist, normalizar_imo,
)
from app.domain.services.version_expediente import DOCUMENTO_ADICIONAL, comparar, foto
from app.informes.autorizacion_pdf import DatosPdfAutorizacion, TripulantePdf
from app.informes.boleta_recargo_pdf import DatosPdfBoleta
from app.informes.historico_excel import DatosHistorico, FilaHistorico, FiltrosAplicados
from app.infrastructure import almacenamiento
from app.infrastructure.almacenamiento import ArchivoGuardado

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

CODIGO_PANAMA = "PAN"
Estado        = EstadoSolicitud
MAX_ERRORES_MOSTRADOS      = 8
MAX_DOCUMENTOS_ADICIONALES = 20
MAX_TRIPULANTES            = 30   # por solicitud (reunión del 2026-10-30); espejo en el frontend
# Lo más que pesa un envío válido (crear o corregir), que lleva juntos todos los archivos
# de la solicitud: es el tope del cuerpo de esas dos rutas (TopeDelCuerpo en api/middleware.py y
# client_max_body_size en frontend/nginx.conf, revisión de recursos del 2026-11-10). Con
# el catálogo de hoy, a un tripulante se le piden como mucho 5 documentos (uno de
# nacionalidad restringida en Desembarque, Urgencia médica o Renovación, con la Visa
# desde el 2026-11-14) y a la solicitud, 12 (el Formulario No. 3, la Form. 7 con hasta 10
# archivos desde el 2026-11-27 y la Lista de Tripulantes o la garantía): 30 × 5 + 12 + 20
# adicionales = 182 archivos de 2 MB, más 1 MB para los datos y los separadores. tests/test_recursos.py falla si el catálogo
# pide más, o si nginx no coincide.
MAX_DOCUMENTOS_POR_TRIPULANTE  = 5
MAX_DOCUMENTOS_DE_LA_SOLICITUD = 12   # desde el 2026-11-27: la Form. 7 admite hasta 10
MAX_ARCHIVOS_EN_UN_ENVIO = (MAX_TRIPULANTES * MAX_DOCUMENTOS_POR_TRIPULANTE + MAX_DOCUMENTOS_DE_LA_SOLICITUD
                            + MAX_DOCUMENTOS_ADICIONALES)
TOPE_CUERPO_ENVIO_MB = MAX_ARCHIVOS_EN_UN_ENVIO * almacenamiento.TAMANO_MAXIMO_MB + 1
MAX_FUERA_HORARIO_LISTADAS = 50   # estadísticas: las aprobadas fuera del horario que se listan
MAX_FILAS_EXPORTACION = 5000      # consulta histórica (2026-11-11): las primeras, según el orden
# Estadísticas: cuántos días, meses y años muestra la serie, como mucho (los últimos del periodo).
DIAS_EN_SERIE  = 31
MESES_EN_SERIE = 12
ANIOS_EN_SERIE = 10

# (casilla del checklist o None si es un documento adicional, índice del tripulante)
Asignacion = tuple[TramiteDocumento | None, int | None]

# Historial que ve la agencia (ver ServicioSolicitud.evento_para).
_EVENTOS_INTERNOS = {
    TipoEventoSolicitud.IMPEDIMENTOS.value,
    TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS.value,
    TipoEventoSolicitud.IMPEDIMENTOS_PUESTO.value,
    TipoEventoSolicitud.IMPEDIMENTOS_PUESTO_CORREGIDOS.value,
    TipoEventoSolicitud.COMENTARIO.value,   # ya no se registran: quedan los de antes
    TipoEventoSolicitud.BOLETA_GENERADA.value,   # la boleta de recargo no la ve la agencia (2026-11-16)
    TipoEventoSolicitud.BOLETA_ANULADA.value,
}
# Los de la boleta, además, solo para quien la ve (`ve_boletas`): el puesto de control y el
# supervisor general tampoco (2026-11-27).
_EVENTOS_BOLETA = {TipoEventoSolicitud.BOLETA_GENERADA.value, TipoEventoSolicitud.BOLETA_ANULADA.value}
_ETIQUETA_EMITIDO = {
    TipoEmitido.APROBADA.value:   "Autorización aprobada",
    TipoEmitido.FINALIZADA.value: "Autorización finalizada",
}
_SIN_TEXTO_PARA_AGENCIA = {TipoEventoSolicitud.APROBADA.value, TipoEventoSolicitud.FINALIZADA.value}
# A la agencia no se le nombran las unidades internas (UCVMM, los sectores): ve
# a la institución (INSTITUCION, 2026-11-11; antes, "UCVMM").
_AUTOR_PARA_AGENCIA = {
    TipoEventoSolicitud.DEVUELTA.value:   INSTITUCION,
    TipoEventoSolicitud.APROBADA.value:   INSTITUCION,
    TipoEventoSolicitud.NEGADA.value:     INSTITUCION,
    TipoEventoSolicitud.FINALIZADA.value: "Puesto de control",
}


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def hoy_panama() -> date:
    return datetime.now(ZONA_PANAMA).date()


def fin_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time(23, 59, 59), tzinfo=ZONA_PANAMA)


def _resultado(con_impedimento: bool | None) -> str:
    """Resultado de un tripulante en SIMPLUS, para el historial."""
    return "con impedimento" if con_impedimento else "sin impedimento"


def _con_punto(texto: str) -> str:
    """Cierra una frase del historial (sin duplicar la puntuación del usuario)."""
    return texto if texto.endswith((".", "!", "?")) else f"{texto}."


def _error(codigo: int, detalle: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=detalle)


@dataclass
class _TripulanteResuelto:
    """Tripulante del formulario ya validado contra el catálogo de países."""
    entrada:     DatosTripulanteEntrada
    restringido: bool

    @property
    def porta_libreta(self) -> bool:
        return self.entrada.rango in RANGOS_CON_LIBRETA

    def para_checklist(self) -> TripulanteChecklist:
        return TripulanteChecklist(
            nombre=f"{self.entrada.nombre} {self.entrada.apellido}",
            es_panameno=self.entrada.nacionalidad == CODIGO_PANAMA,
            rango=self.entrada.rango,
            nacionalidad_restringida=self.restringido,
        )


@dataclass(frozen=True)
class _EtapaVerificacion:
    """Dónde guarda su verificación de impedimentos cada etapa: UCVMM al
    revisar y el puesto de control antes de finalizar (2026-11-06). Son
    columnas aparte, para que una verificación no pise a la otra."""
    tripulante:       str   # columna de solicitud_tripulantes con el resultado
    verificados:      str   # columnas de solicitudes
    comentario:       str
    en:               str
    por_id:           str
    evento:           TipoEventoSolicitud
    evento_corregido: TipoEventoSolicitud


_VERIFICACION_UCVMM = _EtapaVerificacion(
    tripulante="con_impedimento", verificados="impedimentos_verificados",
    comentario="comentario_impedimentos", en="impedimentos_verificados_en",
    por_id="impedimentos_verificados_por_id",
    evento=TipoEventoSolicitud.IMPEDIMENTOS, evento_corregido=TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS,
)
_VERIFICACION_PUESTO = _EtapaVerificacion(
    tripulante="con_impedimento_puesto", verificados="impedimentos_puesto_verificados",
    comentario="comentario_impedimentos_puesto", en="impedimentos_puesto_en",
    por_id="impedimentos_puesto_por_id",
    evento=TipoEventoSolicitud.IMPEDIMENTOS_PUESTO,
    evento_corregido=TipoEventoSolicitud.IMPEDIMENTOS_PUESTO_CORREGIDOS,
)


@dataclass
class Vencimiento:
    """Una solicitud que el proceso automático acaba de expirar."""
    solicitud:       Solicitud
    estado_anterior: str
    motivo:          str


class ServicioSolicitud:
    def __init__(self, sesion: AsyncSession):
        self.sesion         = sesion
        self.repo           = RepositorioSolicitud(sesion)
        self.repo_tramites  = RepositorioTramite(sesion)
        self.repo_catalogos = RepositorioCatalogo(sesion)
        self.tramites       = ServicioTramite()

    # ── Acceso ───────────────────────────────────────────────────────────────

    async def contexto(self, usuario: Usuario) -> ContextoAcceso:
        codigos = await codigos_permiso(self.sesion, usuario)
        es_admin = es_admin_efectivo(usuario)
        es_revisor = PERMISO_REVISAR in codigos
        es_supervisor_sector = PERMISO_SUPERVISAR_SECTOR in codigos and not es_admin
        # El Administrador tiene todos los permisos por el atajo, pero no es un
        # supervisor ni necesita sector: ya ve todo.
        sectores = (
            await self.repo_catalogos.sectores_de_usuario(usuario.id)
            if not es_admin and (es_revisor or es_supervisor_sector) else set()
        )
        return ContextoAcceso(
            usuario=usuario,
            es_admin=es_admin,
            es_naviera=PERMISO_SOLICITAR in codigos,
            es_revisor=es_revisor,
            es_puerto=PERMISO_PUERTO in codigos,
            puestos_ids=await self.repo_catalogos.puestos_de_usuario(usuario.id),
            agencia_id=usuario.agencia_id,
            es_supervisor_sector=es_supervisor_sector,
            es_supervisor_general=PERMISO_SUPERVISAR_TODO in codigos and not es_admin,
            sectores_ids=sectores,
            puestos_de_sectores=await self.repo_catalogos.puestos_de_sectores(sectores),
        )

    @staticmethod
    def _es_del_puerto(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """Es del puesto que la finaliza: con cambio de puerto, el nuevo."""
        return ctx.es_admin or (ctx.es_puerto and s.puesto_autorizado_id in ctx.puestos_ids)

    @staticmethod
    def _tiene_conflicto(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """Separación de funciones: nadie revisa lo que creó ni lo de su agencia."""
        return s.creada_por_id == ctx.usuario.id or (
            ctx.agencia_id is not None and s.agencia_id == ctx.agencia_id
        )

    def puede_ver(self, ctx: ContextoAcceso, s: Solicitud) -> bool:
        """La ven su agencia y el admin; UCVMM y el supervisor de sector, si es de
        sus sectores; el supervisor general, si es de un trámite que
        supervisa (el de Técnico, 2026-11-16); el puesto de control, solo las que
        finaliza (con cambio de puerto, el nuevo) y desde que se aprueban. La consulta
        histórica aplica lo mismo en SQL (`_alcance_historico`): si cambias uno,
        cambia el otro."""
        if ctx.ve_todos_los_sectores or ctx.es_de_su_agencia(s):
            return True
        if (ctx.es_revisor or ctx.es_supervisor_sector) and ctx.en_sus_sectores(s):
            return True
        if ctx.supervisa_tramite(s):
            return True
        return s.aprobada_en is not None and self._es_del_puerto(ctx, s)

    def acciones(self, ctx: ContextoAcceso, s: Solicitud) -> AccionesSolicitud:
        ahora      = ahora_utc()
        vigente    = s.estado == Estado.APROBADA.value and (s.vigente_hasta is None or s.vigente_hasta >= ahora)
        en_plazo   = s.plazo_correccion is None or s.plazo_correccion >= ahora
        del_puerto = vigente and self._es_del_puerto(ctx, s)
        revisable  = ctx.puede_revisar_esta(s) and s.estado == Estado.EN_REVISION.value
        conflicto  = revisable and self._tiene_conflicto(ctx, s)
        boleta_vigente = next((b for b in s.boletas if b.vigente), None)
        return AccionesSolicitud(
            corregir=ctx.es_de_su_agencia(s) and s.estado == Estado.EN_CORRECCION.value and en_plazo,
            revisar=revisable and not conflicto,
            finalizar=del_puerto,
            descargar_autorizacion=self._hay_pdf(ctx, s) and self.puede_ver(ctx, s),
            conflicto_revision=conflicto,
            generar_boleta=self.puede_generar_boleta(ctx, s) and boleta_vigente is None,
            anular_boleta=boleta_vigente is not None and self.puede_anular_boleta(ctx, s, boleta_vigente),
            ver_registro=ctx.ve_registro(s),
        )

    @staticmethod
    def con_impedimento_al_devolver(s: Solicitud) -> list[str]:
        """Los tripulantes con impedimento según la verificación de UCVMM, que la agencia ve
        mientras la solicitud está devuelta (pedido del usuario del 2026-11-26): la solicitud no
        puede avanzar con ellos. En los demás estados la verificación sigue siendo interna."""
        if s.estado != Estado.EN_CORRECCION.value:
            return []
        return [t.nombre_completo for t in s.tripulantes if t.con_impedimento]

    @staticmethod
    def horas_vigencia(s: Solicitud) -> int | None:
        """Las horas que vale desde la aprobación, si se aprobó con la regla de horas de su trámite
        (Urgencia médica, 120: 2026-11-26). Se mira la solicitud y no solo el catálogo: las
        aprobadas antes valen hasta el final del día y no las dicen."""
        horas = s.tipo_tramite.horas_vigencia
        if horas and s.aprobada_en and s.vigente_hasta and s.vigente_hasta - s.aprobada_en == timedelta(hours=horas):
            return horas
        return None

    @staticmethod
    def _hay_pdf(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """La autorización en PDF: aprobada o finalizada. La que se aprobó y venció sin
        finalizarse la ve el SNM, con su sello (2026-11-22); la agencia no."""
        vencida = s.estado == Estado.EXPIRADA.value and s.aprobada_en is not None
        return s.estado in (Estado.APROBADA.value, Estado.FINALIZADA.value) or (vencida and ctx.es_personal_snm)

    # ── La boleta de recargo (2026-11-16): quién la ve y quién la gestiona (2026-11-27) ──

    @staticmethod
    def ve_boletas(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """La ven y la descargan UCVMM y el supervisor de sector (de sus sectores) y el
        Administrador. El puesto de control, el supervisor general y la agencia no la ven
        (2026-11-27; antes el puesto la generaba y el general la descargaba)."""
        return ctx.es_admin or ((ctx.es_revisor or ctx.es_supervisor_sector) and ctx.en_sus_sectores(s))

    @staticmethod
    def _es_ucvmm_de(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """UCVMM de los sectores de la solicitud. El Administrador no: solo ve (2026-11-27)."""
        return ctx.es_revisor and not ctx.es_admin and ctx.en_sus_sectores(s)

    def puede_generar_boleta(self, ctx: ContextoAcceso, s: Solicitud) -> bool:
        """El número de oficio lo pone el analista de UCVMM que la aprobó fuera del horario; si
        no está, otro de UCVMM del sector, y queda dicho en lugar de quién (`en_lugar_de`)."""
        return s.costo_fuera_de_horario is not None and s.aprobada_en is not None and self._es_ucvmm_de(ctx, s)

    def puede_anular_boleta(self, ctx: ContextoAcceso, s: Solicitud, boleta: BoletaRecargo) -> bool:
        """Anula (con motivo, para poner otro número) quien la aprobó o quien generó esa boleta.
        Nadie más toca una boleta que no puso."""
        return self._es_ucvmm_de(ctx, s) and ctx.usuario.id in (s.aprobada_por_id, boleta.generada_por_id)

    async def en_lugar_de(self, ctx: ContextoAcceso, s: Solicitud) -> str | None:
        """Quien aprobó la solicitud, si la boleta la pone otro: queda en la bitácora y en el historial."""
        if s.aprobada_por_id is None or s.aprobada_por_id == ctx.usuario.id:
            return None
        aprobador = await self.sesion.get(Usuario, s.aprobada_por_id)
        return aprobador.full_name if aprobador else None

    async def obtener(self, ctx: ContextoAcceso, solicitud_id: int, *, bloquear: bool = False) -> Solicitud:
        """La solicitud, si el usuario puede verla. Con `bloquear`, además toma
        el bloqueo de la fila hasta el fin de la transacción (transiciones)."""
        s = await self.repo.buscar_por_id(solicitud_id, bloquear=bloquear)
        if not s:
            raise _error(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada.")
        if not self.puede_ver(ctx, s):
            raise _error(status.HTTP_403_FORBIDDEN, "No tienes acceso a esta solicitud.")
        return s

    async def _recargar(self, solicitud_id: int) -> Solicitud:
        s = await self.repo.buscar_por_id(solicitud_id, refrescar=True)
        assert s is not None
        return s

    async def obtener_documento(
        self, ctx: ContextoAcceso, solicitud_id: int, documento_id: int,
    ) -> tuple[Solicitud, DocumentoSolicitud, Path]:
        """Un documento del expediente y su ruta en disco (validada dentro de
        STORAGE_PATH), si sigue siendo el que se subió. Lo ve quien puede ver la solicitud;
        uno retirado en una corrección, quien ve el registro (2026-11-22)."""
        s = await self.obtener(ctx, solicitud_id)
        documento = next((d for d in s.documentos if d.id == documento_id), None)
        if documento is None and ctx.ve_registro(s):
            documento = await self.repo.documento_retirado(s.id, documento_id)
        if documento is None:
            raise _error(status.HTTP_404_NOT_FOUND, "Documento no encontrado en esta solicitud.")
        return s, documento, await self._archivo_intacto(documento.ruta, documento.sha256, f"El documento {documento.id}")

    @staticmethod
    async def _archivo_intacto(ruta: str, sha256: str | None, que_es: str) -> Path:
        """La ruta en disco de un archivo, si está y coincide con su huella (2026-11-22):
        dentro de muchos años, lo que se ve es lo que se subió o se emitió."""
        archivo = almacenamiento.ruta_segura(ruta)
        if not archivo or not archivo.is_file():
            logger.error("[archivos] %s no está en el disco (%s).", que_es, ruta)
            raise _error(status.HTTP_404_NOT_FOUND, "El archivo no está disponible. Avisa al administrador.")
        if sha256 and await asyncio.to_thread(almacenamiento.huella_de, archivo) != sha256:
            logger.error("[archivos] %s no coincide con su huella (%s): se dañó o alguien lo cambió.", que_es, ruta)
            raise _error(status.HTTP_409_CONFLICT,
                         "El archivo no coincide con el original: se dañó o alguien lo cambió. Avisa al administrador.")
        return archivo

    # ── Bandejas ─────────────────────────────────────────────────────────────

    async def _pagina(
        self, ctx: ContextoAcceso, filtros: FiltrosBandeja, consulta: ConsultaBandeja | ConsultaHistorica, orden: str,
    ) -> PaginaSolicitudes:
        pagina = await self.repo.listar(
            filtros, pagina=consulta.pagina, por_pagina=consulta.por_pagina, orden=orden,
        )
        ids = [s.id for s in pagina.solicitudes]
        alertas = await self.repo.alertas_de(ids)
        # Al buscar un tripulante, cuál de ellos es (consulta histórica, 2026-11-22).
        encontrados = await self.repo.tripulantes_encontrados(ids, filtros.pasajero) if filtros.pasajero else None
        return PaginaSolicitudes(
            total=pagina.total, pagina=consulta.pagina, por_pagina=consulta.por_pagina, conteos=pagina.conteos,
            autorizadas=pagina.autorizadas,
            items=[self.construir_resumen(
                s, interno=ctx.es_personal_snm, alertas=alertas.get(s.id, (0, False)),
                encontrados=None if encontrados is None else encontrados.get(s.id, []),
            ) for s in pagina.solicitudes],
        )

    @staticmethod
    def _filtros(consulta: ConsultaBandeja, **alcance) -> FiltrosBandeja:
        return FiltrosBandeja(
            estado=consulta.estado, texto=consulta.texto, desde=consulta.desde, hasta=consulta.hasta,
            **alcance,
        )

    async def bandeja_agencia(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Las solicitudes de la agencia del usuario."""
        if ctx.agencia_id is None:
            raise _error(
                status.HTTP_409_CONFLICT,
                "Tu usuario no tiene una agencia naviera asignada. Pide al administrador que te asigne a la tuya.",
            )
        return await self._pagina(ctx, self._filtros(consulta, agencia_id=ctx.agencia_id), consulta, "recientes")

    @staticmethod
    def _exigir_sector(ctx: ContextoAcceso) -> None:
        """UCVMM y el supervisor de sector necesitan su sector: sin él no verían nada.
        El Administrador y el supervisor general no lo necesitan."""
        if not ctx.es_admin and (ctx.es_revisor or ctx.es_supervisor_sector) and not ctx.sectores_ids:
            raise _error(
                status.HTTP_409_CONFLICT,
                "Tu usuario no tiene un sector asignado (Pacífico o Atlántico). Pide al administrador que te "
                "asigne al tuyo.",
            )

    async def bandeja_revision(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Las solicitudes de sus sectores, para UCVMM (el admin, todas). Las
        pendientes salen en orden de llegada (la más antigua primero)."""
        if not ctx.puede_revisar:
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_REVISAR}.")
        self._exigir_sector(ctx)
        orden = "cola" if consulta.estado == Estado.EN_REVISION.value else "recientes"
        filtros = self._filtros(consulta, sectores=None if ctx.es_admin else ctx.alcance_sectores)
        return await self._pagina(ctx, filtros, consulta, orden)

    async def bandeja_supervision(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Solo lectura (2026-11-10): las de sus sectores (supervisor de sector) o las
        del trámite de Técnico de los dos sectores (supervisor general, 2026-11-16).
        Sin acciones de decisión: lo dice `acciones`."""
        if not (ctx.es_admin or ctx.es_supervisor):
            raise _error(status.HTTP_403_FORBIDDEN, "No tienes permiso para supervisar las solicitudes.")
        self._exigir_sector(ctx)
        alcance = None if ctx.es_admin else AlcanceSnm(
            sectores=ctx.alcance_sectores if ctx.es_supervisor_sector else None,
            supervision_general=ctx.es_supervisor_general,
        )
        filtros = self._filtros(consulta, alcance_snm=alcance)
        return await self._pagina(ctx, filtros, consulta, "recientes")

    async def bandeja_puerto(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Autorizaciones aprobadas que finalizan los puestos del usuario (el
        admin ve todos): con cambio de puerto, en la bandeja del nuevo. Las
        pendientes de finalizar salen por fecha de operación."""
        if not (ctx.es_admin or ctx.es_puerto):
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_PUERTO}.")
        filtros = self._filtros(
            consulta, puestos_autorizados=None if ctx.es_admin else ctx.puestos_ids, solo_aprobadas_alguna_vez=True,
        )
        orden = "operacion" if consulta.estado == Estado.APROBADA.value else "recientes"
        return await self._pagina(ctx, filtros, consulta, orden)

    # ── Consulta histórica (2026-11-11) ──────────────────────────────────────

    def _alcance_historico(self, ctx: ContextoAcceso) -> AlcanceSnm | None:
        """Lo que ve en la consulta histórica: lo mismo que `puede_ver`, sin la vía
        de la agencia (la consulta es del personal del SNM). None = todas. El
        supervisor general (2026-11-16) y el puesto de control (2026-11-22) no la
        tienen: con otro permiso que la abra, también les muestra lo suyo, como el
        expediente."""
        if not ctx.ve_historico:
            raise _error(status.HTTP_403_FORBIDDEN,
                         "La consulta histórica es para UCVMM y los supervisores de sector.")
        if ctx.ve_todos_los_sectores:
            return None
        de_sector = ctx.es_revisor or ctx.es_supervisor_sector
        if de_sector and not ctx.es_puerto:
            self._exigir_sector(ctx)
        return AlcanceSnm(
            sectores=ctx.alcance_sectores if de_sector else None,
            puestos_aprobadas=frozenset(ctx.puestos_ids) if ctx.es_puerto else frozenset(),
            supervision_general=ctx.es_supervisor_general,
        )

    def _filtros_historico(self, ctx: ContextoAcceso, consulta: ConsultaHistorica) -> FiltrosBandeja:
        return FiltrosBandeja(
            alcance_snm=self._alcance_historico(ctx), agencia_id=consulta.agencia_id,
            puesto_id=consulta.puesto_id, tipo_tramite_id=consulta.tipo_tramite_id, estado=consulta.estado,
            texto=consulta.texto, pasajero=consulta.pasajero, autorizadas=consulta.autorizadas,
            fuera_de_horario=consulta.fuera_de_horario,
            fecha_por=consulta.fecha, desde=consulta.desde, hasta=consulta.hasta,
        )

    @staticmethod
    def _orden_historico(consulta: ConsultaHistorica) -> str:
        return "operacion_reciente" if consulta.fecha == "operacion" else "recientes"

    async def consulta_historica(self, ctx: ContextoAcceso, consulta: ConsultaHistorica) -> PaginaSolicitudes:
        """Las solicitudes que ve, de cualquier año, de la más reciente a la más
        antigua (por la fecha de envío o por la de la operación)."""
        filtros = self._filtros_historico(ctx, consulta)
        return await self._pagina(ctx, filtros, consulta, self._orden_historico(consulta))

    async def opciones_historico(self, ctx: ContextoAcceso) -> SalidaOpcionesHistorico:
        alcance = self._alcance_historico(ctx)
        puestos = await self.repo_catalogos.listar_puestos()
        # Los que ya no son de su sector, pero de los que conserva solicitudes (2026-11-22).
        de_antes: set[int] = set()
        if alcance is not None and not alcance.supervision_general:
            sectores = alcance.sectores or AlcanceSectores()
            de_hoy = sectores.puestos | alcance.puestos_aprobadas
            de_antes = await self.repo.puestos_revisados_por(sectores.sectores) - de_hoy
            puestos = [p for p in puestos if p.id in de_hoy or p.id in de_antes]
        return SalidaOpcionesHistorico(
            agencias=[OpcionFiltro(id=a.id, nombre=a.nombre, activo=a.activo)
                      for a in await self.repo_catalogos.listar_agencias()],
            puestos=[OpcionFiltro(id=p.id, activo=p.activo,
                                  nombre=f"{p.nombre} (hoy, {p.sector.nombre})" if p.id in de_antes else p.nombre)
                     for p in puestos],
            tramites=[OpcionFiltro(id=t.id, nombre=t.nombre, activo=t.activo)
                      for t in await self.repo_tramites.listar_tipos(solo_activos=False)],
        )

    async def _texto_alcance(self, ctx: ContextoAcceso) -> str:
        if ctx.ve_todos_los_sectores:
            return "Todos los sectores"
        partes = []
        if ctx.es_revisor or ctx.es_supervisor_sector:
            sectores = [x.nombre for x in await self.repo_catalogos.listar_sectores() if x.id in ctx.sectores_ids]
            if sectores:
                partes.append(" y ".join(sectores))
        if ctx.es_puerto:
            puestos = [p.nombre for p in await self.repo_catalogos.listar_puestos() if p.id in ctx.puestos_ids]
            if puestos:
                partes.append("Puestos: " + ", ".join(puestos))
        return " · ".join(partes) or "Sin puestos ni sectores asignados"

    async def exportacion_historica(self, ctx: ContextoAcceso, consulta: ConsultaHistorica) -> DatosHistorico:
        """Lo que cumple los filtros (hasta MAX_FILAS_EXPORTACION), en datos planos
        para armar el Excel en un hilo."""
        filtros = self._filtros_historico(ctx, consulta)
        total, solicitudes = await self.repo.para_exportar(
            filtros, orden=self._orden_historico(consulta), limite=MAX_FILAS_EXPORTACION,
        )
        agencia = await self.repo_catalogos.buscar_agencia(consulta.agencia_id) if consulta.agencia_id else None
        puesto = await self.repo_catalogos.buscar_puesto(consulta.puesto_id) if consulta.puesto_id else None
        tipo = await self.repo_tramites.buscar_tipo_por_id(consulta.tipo_tramite_id) if consulta.tipo_tramite_id else None
        return DatosHistorico(
            filas=[
                FilaHistorico(
                    numero=s.numero, estado=s.estado, tramite=s.tipo_tramite.nombre, agencia=s.agencia_nombre,
                    puesto=(f"{s.puesto_nombre} → {s.puesto_destino_nombre}" if s.puesto_destino_nombre
                            else s.puesto_nombre),
                    sector=s.sector.nombre,
                    buque=s.nombre_buque, imo=s.imo, fecha_operacion=s.fecha_operacion,
                    cantidad_tripulantes=s.cantidad_tripulantes, enviada_en=s.enviada_en, aprobada_en=s.aprobada_en,
                    finalizada_en=s.finalizada_en,
                    fuera_de_horario=s.aprobada_en is not None and fuera_de_horario(s.aprobada_en),
                    costo=s.costo_fuera_de_horario,
                )
                for s in solicitudes
            ],
            total=total,
            filtros=FiltrosAplicados(
                texto=consulta.texto, pasajero=consulta.pasajero,
                agencia=agencia.nombre if agencia else (f"#{consulta.agencia_id}" if consulta.agencia_id else None),
                puesto=puesto.nombre if puesto else (f"#{consulta.puesto_id}" if consulta.puesto_id else None),
                tramite=tipo.nombre if tipo else (f"#{consulta.tipo_tramite_id}" if consulta.tipo_tramite_id else None),
                estado=consulta.estado, autorizadas=consulta.autorizadas,
                fuera_de_horario=consulta.fuera_de_horario, fecha=consulta.fecha,
                desde=consulta.desde, hasta=consulta.hasta,
            ),
            alcance=await self._texto_alcance(ctx),
            generado_por=ctx.usuario.full_name, generado_en=datetime.now(ZONA_PANAMA),
            ordenadas_por="fecha de la operación" if consulta.fecha == "operacion" else "fecha de envío",
        )

    # ── Validación del formulario ────────────────────────────────────────────

    async def _validar_cambio_de_puerto(
        self, puesto: PuestoControl, puesto_destino_id: int | None,
    ) -> PuestoControl | None:
        """El nuevo puesto de un cambio de puerto (2026-11-13): activo y distinto del
        primero, de cualquier sector desde el 2026-11-18 (antes, del mismo). La revisa
        UCVMM del sector del primer puesto y la finaliza el nuevo."""
        if puesto_destino_id is None:
            return None
        destino = await self.repo_catalogos.buscar_puesto(puesto_destino_id)
        if not destino or not destino.activo:
            raise _error(status.HTTP_400_BAD_REQUEST,
                         "El puesto de control del cambio de puerto no existe o no está activo.")
        if destino.id == puesto.id:
            raise _error(status.HTTP_400_BAD_REQUEST,
                         "El cambio de puerto tiene que ser a otro puesto de control.")
        return destino

    async def _validar_formulario(
        self, tipo: TipoTramite, datos: _DatosFormularioSolicitud,
    ) -> tuple[PuestoControl, PuestoControl | None, list[_TripulanteResuelto], str | None]:
        """Valida cabecera y tripulantes. Devuelve el puesto, el del cambio de
        puerto (o None), los tripulantes resueltos y el IMO normalizado."""
        faltan = self.tramites.validar_campos_cabecera(tipo, datos.model_dump())
        if faltan:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Faltan datos obligatorios del formulario: {', '.join(faltan)}.")
        # Cada trámite ofrece sus operaciones: «Subir y bajar», solo el de Técnico (2026-11-26).
        if tipo.pide_operacion and datos.operacion and tipo.operaciones and datos.operacion not in tipo.operaciones:
            nombres = [ETIQUETA_OPERACION[o] for o in tipo.operaciones]
            opciones = ", ".join(nombres[:-1]) + f" o {nombres[-1]}" if len(nombres) > 1 else nombres[0]
            raise _error(status.HTTP_400_BAD_REQUEST,
                         f"La operación «{ETIQUETA_OPERACION[datos.operacion]}» no es de este trámite: elige {opciones}.")
        # Y sus días del sellado: Urgencia médica, solo 5 (2026-11-27).
        ofrecidos = tipo.dias_sellado_opciones
        if tipo.pide_dias_sellado and datos.dias_sellado and ofrecidos and datos.dias_sellado not in ofrecidos:
            nombres = [texto_dias(d) for d in ofrecidos]
            opciones = ", ".join(nombres[:-1]) + f" o {nombres[-1]}" if len(nombres) > 1 else nombres[0]
            raise _error(status.HTTP_400_BAD_REQUEST,
                         f"El sellado de {texto_dias(datos.dias_sellado)} no es de este trámite: elige {opciones}.")

        hoy = hoy_panama()
        assert datos.fecha_operacion is not None and datos.puesto_control_id is not None
        if datos.fecha_operacion < hoy:
            raise _error(status.HTTP_400_BAD_REQUEST, "La fecha de la operación no puede ser anterior a hoy.")
        if datos.fecha_operacion > hoy + timedelta(days=configuracion.DIAS_MAXIMOS_ANTICIPACION):
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"La fecha de la operación no puede estar a más de {configuracion.DIAS_MAXIMOS_ANTICIPACION} días.",
            )

        puesto = await self.repo_catalogos.buscar_puesto(datos.puesto_control_id)
        if not puesto or not puesto.activo:
            raise _error(status.HTTP_400_BAD_REQUEST, "El puesto de control seleccionado no existe o no está activo.")
        # Solo los trámites que lo admiten (Embarque y Desembarque): en los demás, un
        # nuevo puesto que llegue (resto de otro trámite elegido antes) se descarta,
        # como los campos que el trámite no usa.
        destino = await self._validar_cambio_de_puerto(
            puesto, datos.puesto_destino_id if tipo.permite_cambio_puerto else None,
        )

        imo = None
        if datos.imo:
            imo = normalizar_imo(datos.imo)
            if not imo:
                raise _error(
                    status.HTTP_400_BAD_REQUEST,
                    "El número IMO no es válido: son 7 dígitos y el último es el dígito verificador (ej. IMO 9074729).",
                )

        if not datos.tripulantes:
            raise _error(status.HTTP_400_BAD_REQUEST, "Debes registrar al menos un tripulante en la solicitud.")
        if len(datos.tripulantes) > MAX_TRIPULANTES:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"Una solicitud admite hasta {MAX_TRIPULANTES} tripulantes. Si son más, presenta otra solicitud.",
            )

        codigos = {t.nacionalidad for t in datos.tripulantes} | {t.pais_nacimiento for t in datos.tripulantes}
        bandera = datos.bandera.upper() if datos.bandera else None
        if bandera:
            codigos.add(bandera)
        paises = await self.repo_catalogos.paises_por_codigo(codigos)
        if bandera and bandera not in paises:
            raise _error(status.HTTP_400_BAD_REQUEST, "La bandera del buque no es un país válido.")

        errores = self.tramites.validar_tripulantes(
            tipo, datos.tripulantes,
            fecha_referencia=max(hoy, datos.fecha_operacion), hoy=hoy,
            codigos_pais_validos=set(paises),
        )
        if errores:
            extra = len(errores) - MAX_ERRORES_MOSTRADOS
            detalle = " ".join(errores[:MAX_ERRORES_MOSTRADOS]) + (f" (y {extra} más)" if extra > 0 else "")
            raise _error(status.HTTP_400_BAD_REQUEST, f"Revisa los datos de los tripulantes: {detalle}")

        resueltos = [
            _TripulanteResuelto(entrada=t, restringido=paises[t.nacionalidad].nacionalidad_restringida)
            for t in datos.tripulantes
        ]
        return puesto, destino, resueltos, imo

    @staticmethod
    def _resolver_asignaciones(
        tipo: TipoTramite, asignaciones: list[AsignacionArchivo], total_tripulantes: int,
        ya_cargados: dict[tuple[str, int | None], int] | None = None,
    ) -> list[Asignacion]:
        """Traduce cada asignación a (casilla del checklist, índice del
        tripulante). Sin código de documento es un documento adicional.
        Cada casilla recibe un solo archivo, salvo las que admiten más (la Form. 7 de
        Renovación, Urgencias y Técnico, hasta 10: 2026-11-27): sin este control, un envío
        podía colgar varios en la misma. `ya_cargados`, al corregir: los que se conservan."""
        por_codigo = {td.documento.codigo: td for td in tipo.documentos}
        resueltas: list[Asignacion] = []
        ocupadas: Counter[tuple[str, int | None]] = Counter(ya_cargados or {})
        for asignacion in asignaciones:
            if asignacion.documento_codigo is None:
                resueltas.append((None, None))
                continue
            td = por_codigo.get(asignacion.documento_codigo)
            if not td:
                raise _error(
                    status.HTTP_400_BAD_REQUEST,
                    f"El documento '{asignacion.documento_codigo}' no pertenece a este trámite.",
                )
            if td.alcance == AlcanceDocumento.SOLICITUD.value:
                indice = None
            else:
                indice = asignacion.indice_tripulante
                if indice is None or not 0 <= indice < total_tripulantes:
                    raise _error(
                        status.HTTP_400_BAD_REQUEST,
                        f"Tripulante inválido para el documento '{td.documento.nombre}'.",
                    )
            casilla = (td.documento.codigo, indice)
            maximo = td.maximo_archivos or 1
            if ocupadas[casilla] >= maximo:
                de_quien = f" del tripulante {indice + 1}" if indice is not None else ""
                if maximo == 1:
                    raise _error(
                        status.HTTP_400_BAD_REQUEST,
                        f"Llegó más de un archivo para «{td.documento.nombre}»{de_quien}: adjunta uno solo por documento.",
                    )
                raise _error(
                    status.HTTP_400_BAD_REQUEST,
                    f"«{td.documento.nombre}»{de_quien} admite hasta {maximo} archivos: quita alguno.",
                )
            ocupadas[casilla] += 1
            resueltas.append((td, indice))
        return resueltas

    @staticmethod
    def _limitar_adicionales(cantidad: int) -> None:
        if cantidad > MAX_DOCUMENTOS_ADICIONALES:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"Se admiten hasta {MAX_DOCUMENTOS_ADICIONALES} documentos adicionales por solicitud.",
            )

    @staticmethod
    def _subir_y_bajar(tipo: TipoTramite, datos: _DatosFormularioSolicitud) -> bool:
        """La respuesta a «¿Subir y bajar?» (2026-11-16), solo si el trámite hace la
        pregunta: en los demás se descarta, como el cambio de puerto. Desde el 2026-11-18
        ningún trámite la hace: «Subir y bajar» es una operación del de Técnico."""
        return tipo.permite_subir_y_bajar and datos.subir_y_bajar

    @classmethod
    def con_carta_subir_y_bajar(cls, tipo: TipoTramite, datos: _DatosFormularioSolicitud) -> bool:
        """Si se piden los documentos de la condición SUBIR_Y_BAJAR (hoy, la carta de garantía de
        la agencia contratante; hasta el 2026-11-27, también la Carta Form. 7 de Técnico, que desde
        entonces va con toda operación): con la operación «Subir y bajar» del trámite de Técnico
        (2026-11-18) o con «¿Subir y bajar? Sí» donde se pregunte. Espejo:
        conCartaSubirYBajar (checklist.ts)."""
        operacion = tipo.pide_operacion and datos.operacion == OperacionTecnico.SUBIR_Y_BAJAR.value
        return operacion or cls._subir_y_bajar(tipo, datos)

    def _exigir_checklist(
        self, tipo: TipoTramite, tripulantes: list[_TripulanteResuelto], cubiertas: set[tuple[int, int | None]],
        datos: _DatosFormularioSolicitud,
    ) -> list[CasillaChecklist]:
        """400 si falta un documento exigible; si no, las casillas exigidas (la foto que se guarda).
        Las condiciones del formulario: la Carta de «Subir y bajar» y la operación de Técnico."""
        resultado = self.tramites.evaluar(
            tipo, [t.para_checklist() for t in tripulantes], cubiertas,
            self.con_carta_subir_y_bajar(tipo, datos), datos.operacion if tipo.pide_operacion else None,
        )
        if not resultado.completo:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"Faltan documentos obligatorios: {resultado.describir_faltantes()}.",
            )
        return resultado.requeridas

    def _registrar_casillas(
        self, s: Solicitud, requeridas: list[CasillaChecklist], tripulantes_orm: list[TripulanteSolicitud],
    ) -> None:
        """Foto del checklist con el que se envía (o corrige) la solicitud: el
        expediente se evalúa contra ella, no contra el catálogo de hoy. Va
        después del flush (los tripulantes ya tienen id), por `solicitud_id`."""
        for orden, c in enumerate(requeridas):
            tripulante_id = tripulantes_orm[c.indice_tripulante].id if c.indice_tripulante is not None else None
            self.repo.agregar_registro(CasillaSolicitud(
                solicitud_id=s.id, documento_id=c.documento_id, tripulante_id=tripulante_id, orden=orden,
                obligatoria=c.obligatoria,
            ))

    # ── Armado de la solicitud ───────────────────────────────────────────────

    @staticmethod
    def _titulo(tipo: TipoTramite, nombre_buque: str | None, cantidad: int) -> str:
        """Título legible autogenerado (la agencia no lo escribe a mano)."""
        partes = [tipo.nombre]
        if nombre_buque:
            partes.append(nombre_buque)
        partes.append(f"{cantidad} tripulante{'' if cantidad == 1 else 's'}")
        return " — ".join(partes)[:255]

    def _aplicar_cabecera(
        self, s: Solicitud, tipo: TipoTramite, datos: _DatosFormularioSolicitud,
        puesto: PuestoControl, destino: PuestoControl | None, imo: str | None, cantidad_tripulantes: int,
    ) -> None:
        """Copia la cabecera del formulario. Los campos que el trámite no usa
        se guardan vacíos aunque lleguen con valor (restos de otro trámite
        que la agencia eligió antes en el formulario)."""
        s.puesto_control_id    = puesto.id
        s.puesto_nombre        = puesto.nombre
        s.puesto_destino_id     = destino.id if destino else None
        s.puesto_destino_nombre = destino.nombre if destino else None
        s.subir_y_bajar        = self._subir_y_bajar(tipo, datos)
        # La del trámite de Técnico (2026-11-18); los demás trámites la descartan.
        s.operacion            = datos.operacion if tipo.pide_operacion else None
        # Shore Pass y, desde el 2026-11-27, Urgencia médica (solo 5, que vale aunque no llegue).
        s.dias_sellado         = self.tramites.dias_sellado_de(tipo, datos.dias_sellado)
        assert datos.fecha_operacion is not None   # la exige _validar_formulario
        s.fecha_operacion      = datos.fecha_operacion
        s.cantidad_tripulantes = cantidad_tripulantes
        s.nombre_buque         = datos.nombre_buque if tipo.requiere_buque else None
        s.imo                  = imo if tipo.requiere_buque else None
        s.bandera              = datos.bandera.upper() if tipo.requiere_buque and datos.bandera else None
        s.nombre_puerto        = datos.nombre_puerto if tipo.requiere_puerto else None
        s.puerto_desembarque   = datos.puerto_desembarque if tipo.requiere_puerto_desembarque else None
        s.motivo               = datos.motivo if tipo.requiere_motivo else None
        s.clinica_hospital     = datos.clinica_hospital if tipo.requiere_clinica else None
        s.observaciones        = datos.observaciones
        s.titulo               = self._titulo(tipo, s.nombre_buque, cantidad_tripulantes)

    @staticmethod
    def _llenar_tripulante(orm: TripulanteSolicitud, t: _TripulanteResuelto, orden: int) -> None:
        e = t.entrada
        orm.nombre           = e.nombre
        orm.apellido         = e.apellido
        orm.fecha_nacimiento = e.fecha_nacimiento
        orm.pais_nacimiento  = e.pais_nacimiento
        orm.nacionalidad     = e.nacionalidad
        orm.sexo             = e.sexo
        orm.pasaporte        = e.pasaporte
        orm.pasaporte_expira = e.pasaporte_expira
        orm.libreta_marino   = e.libreta_marino if t.porta_libreta else None
        orm.libreta_expira   = e.libreta_expira if t.porta_libreta else None
        orm.rango            = e.rango
        # La ocupación salió del formulario (2026-11-16). Al corregir una solicitud vieja
        # también se borra: si no, podría quedar pegada a otra persona cuando la agencia
        # cambia a alguien en la misma ficha.
        orm.ocupacion        = None
        orm.es_panameno      = e.nacionalidad == CODIGO_PANAMA
        orm.nacionalidad_restringida = t.restringido
        orm.orden            = orden

    @staticmethod
    def _documento(
        s: Solicitud, archivo: ArchivoGuardado, carpeta: Path,
        td: TramiteDocumento | None, tripulante_id: int | None, usuario: Usuario,
    ) -> DocumentoSolicitud:
        return DocumentoSolicitud(
            solicitud_id=s.id,
            tripulante_id=tripulante_id,
            documento_id=td.documento_id if td else None,
            nombre_original=archivo.nombre_original,
            nombre_almacenado=archivo.nombre_almacenado,
            ruta=almacenamiento.ruta_relativa(carpeta / archivo.nombre_almacenado),
            tipo_mime=archivo.tipo_mime,
            tamano=archivo.tamano,
            sha256=archivo.sha256,
            subido_por_id=usuario.id,
        )

    def _registrar_evento(
        self, s: Solicitud, usuario: Usuario | None, tipo: TipoEventoSolicitud,
        estado_anterior: str | None, estado_nuevo: str | None, comentario: str | None = None,
    ) -> None:
        self.repo.agregar_registro(EventoSolicitud(
            solicitud_id=s.id,
            tipo=tipo.value,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            comentario=comentario,
            usuario_id=usuario.id if usuario else None,
            usuario_nombre=usuario.full_name if usuario else "Sistema",
        ))

    # ── Agencia: crear y corregir ────────────────────────────────────────────

    async def crear(
        self, ctx: ContextoAcceso, datos: DatosCrearSolicitud, archivos: list[UploadFile],
    ) -> Solicitud:
        """Crea la solicitud a nombre de la agencia del usuario y la deja en la
        cola de UCVMM. El expediente entra completo o no entra: se rechaza con
        400 si falta un dato o un documento exigible."""
        agencia = ctx.usuario.agencia
        if agencia is None:
            raise _error(
                status.HTTP_409_CONFLICT,
                "Tu usuario no tiene una agencia naviera asignada. Pide al administrador que te asigne a la tuya.",
            )
        if not agencia.activo:
            raise _error(status.HTTP_409_CONFLICT, "Tu agencia naviera está inactiva: no puede enviar solicitudes.")

        tipo = await self.repo_tramites.buscar_tipo_por_codigo(datos.codigo_tramite)
        if not tipo or not tipo.activo:
            raise _error(status.HTTP_404_NOT_FOUND, f"Tipo de trámite no encontrado o inactivo: {datos.codigo_tramite}.")

        puesto, destino, tripulantes, imo = await self._validar_formulario(tipo, datos)

        if len(datos.asignaciones) != len(archivos):
            raise _error(status.HTTP_400_BAD_REQUEST, "Cada archivo debe indicar a qué documento corresponde.")
        asignadas = self._resolver_asignaciones(tipo, datos.asignaciones, len(tripulantes))
        self._limitar_adicionales(sum(1 for td, _ in asignadas if td is None))
        requeridas = self._exigir_checklist(
            tipo, tripulantes, {(td.documento_id, indice) for td, indice in asignadas if td is not None}, datos,
        )

        # Los archivos se validan y escriben antes de registrar la solicitud:
        # si alguno se rechaza, no se consume un número de solicitud.
        temporal = almacenamiento.carpeta_temporal()
        carpeta: Path | None = None
        try:
            guardados = await almacenamiento.guardar_archivos(temporal, archivos)
            s = Solicitud(
                agencia_id=agencia.id,
                agencia_nombre=agencia.nombre,
                creada_por_id=ctx.usuario.id,
                tipo_tramite_id=tipo.id,
                estado=Estado.EN_REVISION.value,
                enviada_en=ahora_utc(),
            )
            self._aplicar_cabecera(s, tipo, datos, puesto, destino, imo, len(tripulantes))
            tripulantes_orm: list[TripulanteSolicitud] = []
            for orden, t in enumerate(tripulantes):
                orm = TripulanteSolicitud()
                self._llenar_tripulante(orm, t, orden)
                s.tripulantes.append(orm)
                tripulantes_orm.append(orm)
            await self.repo.agregar(s)   # flush: la solicitud y sus tripulantes ya tienen id
            s.numero = f"AM-{hoy_panama().year}-{s.id:06d}"

            carpeta = almacenamiento.carpeta_solicitud(s.id)
            almacenamiento.mover_carpeta(temporal, carpeta)
            for archivo, (td, indice) in zip(guardados, asignadas, strict=True):
                tripulante_id = tripulantes_orm[indice].id if indice is not None else None
                self.repo.agregar_registro(self._documento(s, archivo, carpeta, td, tripulante_id, ctx.usuario))
            self._registrar_casillas(s, requeridas, tripulantes_orm)
            self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.CREADA, None, s.estado, datos.observaciones)
            await self.repo.guardar()
        except Exception:
            almacenamiento.borrar_carpeta(temporal)
            if carpeta is not None:
                almacenamiento.borrar_carpeta(carpeta)
            raise
        return await self._recargar(s.id)

    async def corregir(
        self, ctx: ContextoAcceso, solicitud_id: int, datos: DatosCorregirSolicitud, archivos: list[UploadFile],
    ) -> Solicitud:
        """Reenvío de la agencia tras una devolución: puede editar la cabecera,
        quitar/agregar/editar tripulantes y reemplazar documentos. Vuelve a
        la cola de UCVMM y la verificación de impedimentos se reinicia."""
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
        if not ctx.es_de_su_agencia(s):
            raise _error(status.HTTP_403_FORBIDDEN, "Solo la agencia que envió la solicitud puede corregirla.")
        if s.estado != Estado.EN_CORRECCION.value:
            raise _error(status.HTTP_409_CONFLICT, "La solicitud no está en corrección.")
        if s.plazo_correccion and s.plazo_correccion < ahora_utc():
            raise _error(status.HTTP_409_CONFLICT, "El plazo para corregir la solicitud ya venció.")

        tipo = await self.repo_tramites.buscar_tipo_por_id(s.tipo_tramite_id)
        assert tipo is not None
        puesto, destino, tripulantes, imo = await self._validar_formulario(tipo, datos)

        # ── Tripulantes que se conservan / quitan ──
        existentes = {t.id: t for t in s.tripulantes}
        ids = [t.entrada.id for t in tripulantes if t.entrada.id is not None]
        if len(ids) != len(set(ids)) or any(i not in existentes for i in ids):
            raise _error(status.HTTP_400_BAD_REQUEST, "La lista de tripulantes no coincide con la solicitud.")
        quitados = set(existentes) - set(ids)
        # Quien tiene impedimento no sigue en la solicitud (2026-11-26): se quita, y si va otra
        # persona, se agrega como tripulante nuevo (y se verifica de nuevo).
        con_impedimento = [existentes[i] for i in ids if existentes[i].con_impedimento]
        if con_impedimento:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"{con_impedimento[0].nombre_completo} tiene impedimento y la solicitud no puede avanzar con esa "
                "persona: quítala. Si va otra persona, agrégala como tripulante nuevo.",
            )

        # ── Documentos que se conservan (los de un tripulante quitado se van con él) ──
        documentos_por_id = {d.id: d for d in s.documentos}
        pedidos = set(datos.documentos_conservados)
        if pedidos - set(documentos_por_id):
            raise _error(status.HTTP_400_BAD_REQUEST, "Alguno de los documentos a conservar no pertenece a la solicitud.")
        conservados = {did for did in pedidos if documentos_por_id[did].tripulante_id not in quitados}

        if len(datos.asignaciones) != len(archivos):
            raise _error(status.HTTP_400_BAD_REQUEST, "Cada archivo debe indicar a qué documento corresponde.")
        # Los que se conservan cuentan en su casilla (la Form. 7 admite hasta 10, 2026-11-27).
        indice_de = {t.entrada.id: i for i, t in enumerate(tripulantes) if t.entrada.id is not None}
        ya_cargados: Counter[tuple[str, int | None]] = Counter(
            (d.documento.codigo, None if d.tripulante_id is None else indice_de.get(d.tripulante_id))
            for d in (documentos_por_id[did] for did in conservados) if d.documento is not None
        )
        asignadas = self._resolver_asignaciones(tipo, datos.asignaciones, len(tripulantes), ya_cargados)
        self._limitar_adicionales(
            sum(1 for td, _ in asignadas if td is None)
            + sum(1 for did in conservados if documentos_por_id[did].documento_id is None)
        )

        indice_por_id = {t.entrada.id: i for i, t in enumerate(tripulantes) if t.entrada.id is not None}
        cubiertas = {(td.documento_id, indice) for td, indice in asignadas if td is not None}
        for did in conservados:
            documento = documentos_por_id[did]
            if documento.documento_id is None:
                continue
            indice = None if documento.tripulante_id is None else indice_por_id.get(documento.tripulante_id)
            cubiertas.add((documento.documento_id, indice))
        requeridas = self._exigir_checklist(tipo, tripulantes, cubiertas, datos)

        carpeta = almacenamiento.carpeta_solicitud(s.id)
        nuevos = await almacenamiento.guardar_archivos(carpeta, archivos)
        retirados = [d for d in s.documentos if d.id not in conservados]
        try:
            # Lo que se había enviado se conserva (2026-11-22): la foto y los documentos que
            # salen, con el nombre de su tripulante. Antes se borraban para siempre.
            ahora = ahora_utc()
            await self._guardar_version(s, ctx.usuario, ahora)
            for documento in retirados:
                dueno = existentes.get(documento.tripulante_id) if documento.tripulante_id else None
                documento.retirado_en = ahora
                documento.tripulante_nombre = dueno.nombre_completo if dueno else None
            # La corrección se validó con las reglas de hoy: la foto se vuelve a tomar.
            s.casillas.clear()

            tripulantes_orm: list[TripulanteSolicitud] = []
            for orden, t in enumerate(tripulantes):
                if t.entrada.id is not None:
                    orm = existentes[t.entrada.id]
                else:
                    orm = TripulanteSolicitud()
                    s.tripulantes.append(orm)
                self._llenar_tripulante(orm, t, orden)
                tripulantes_orm.append(orm)
            for tripulante_id in quitados:
                s.tripulantes.remove(existentes[tripulante_id])
            await self.repo.guardar()   # flush: los tripulantes nuevos ya tienen id

            for archivo, (td, indice) in zip(nuevos, asignadas, strict=True):
                del_tripulante = tripulantes_orm[indice].id if indice is not None else None
                self.repo.agregar_registro(self._documento(s, archivo, carpeta, td, del_tripulante, ctx.usuario))
            self._registrar_casillas(s, requeridas, tripulantes_orm)

            anterior = s.estado
            self._aplicar_cabecera(s, tipo, datos, puesto, destino, imo, len(tripulantes))
            s.estado           = Estado.EN_REVISION.value
            s.enviada_en       = ahora
            s.plazo_correccion = None
            s.sector_revision_id = None   # la revisa el sector que tenga el puesto
            s.impedimentos_verificados        = False
            s.comentario_impedimentos         = None
            s.impedimentos_verificados_en     = None
            s.impedimentos_verificados_por_id = None
            for tripulante in s.tripulantes:   # la tripulación pudo cambiar: se verifica de nuevo
                tripulante.con_impedimento = None

            resumen = (
                f"Documentos nuevos: {len(nuevos)}. Documentos retirados: {len(retirados)}. "
                f"Tripulantes: {len(tripulantes)}."
            )
            if datos.observaciones:
                resumen += f" Observaciones: {datos.observaciones}"
            self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.CORREGIDA, anterior, s.estado, resumen)
            await self.repo.guardar()
        except Exception:
            for archivo in nuevos:
                almacenamiento.borrar_archivo(archivo.ruta)
            raise
        return await self._recargar(s.id)

    async def _guardar_version(self, s: Solicitud, usuario: Usuario, ahora: datetime) -> None:
        """La foto de lo que se había enviado, antes de que la corrección lo cambie."""
        def ultimo(*tipos: TipoEventoSolicitud) -> EventoSolicitud | None:
            valores = {t.value for t in tipos}
            return next((ev for ev in reversed(s.eventos) if ev.tipo in valores), None)

        envio, devolucion = ultimo(TipoEventoSolicitud.CREADA, TipoEventoSolicitud.CORREGIDA), ultimo(TipoEventoSolicitud.DEVUELTA)
        self.repo.agregar_registro(VersionSolicitud(
            solicitud_id=s.id, numero=len(await self.repo.versiones(s.id)) + 1,
            enviada_en=s.enviada_en, enviada_por=envio.usuario_nombre if envio else None,
            devuelta_en=devolucion.creado_en if devolucion else None,
            devuelta_por=devolucion.usuario_nombre if devolucion else None, motivo=s.motivo_devolucion,
            corregida_en=ahora, corregida_por=usuario.full_name,
            datos=foto(s, await self._nombre_pais(s.bandera)),
        ))

    # ── Historial completo (2026-11-22) ──────────────────────────────────────

    async def _para_registro(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        s = await self.obtener(ctx, solicitud_id)
        if not ctx.ve_registro(s):
            raise _error(status.HTTP_403_FORBIDDEN, "El historial completo lo ve el personal de UCVMM que la revisa.")
        return s

    async def registro(self, ctx: ContextoAcceso, solicitud_id: int) -> tuple[Solicitud, SalidaRegistro]:
        """Lo que se envió en cada versión y qué cambió, y todos los archivos con su
        huella: los vigentes, los retirados y las autorizaciones emitidas."""
        s = await self._para_registro(ctx, solicitud_id)
        versiones = await self.repo.versiones(s.id)
        fotos = [v.datos for v in versiones]
        if versiones:
            fotos.append(foto(s, await self._nombre_pais(s.bandera)))
        archivos = [
            SalidaArchivo(
                clase="documento", id=d.id, documento=d.documento.nombre if d.documento else DOCUMENTO_ADICIONAL,
                tripulante=d.tripulante_nombre or (d.tripulante.nombre_completo if d.tripulante else None),
                nombre=d.nombre_original, tamano=d.tamano, tipo_mime=almacenamiento.mime_del_formato(d.nombre_almacenado),
                sha256=d.sha256, fecha=d.created_at, por=por, retirado_en=d.retirado_en,
            )
            for d, por in await self.repo.archivos(s.id)
        ] + [
            SalidaArchivo(
                clase="emitido", id=x.id, documento=_ETIQUETA_EMITIDO[x.tipo], nombre=self.nombre_emitido(s, x),
                tamano=x.tamano, tipo_mime="application/pdf", sha256=x.sha256, fecha=x.emitido_en,
            )
            for x in await self.repo.emitidos(s.id)
        ]
        # Una devuelta sin corregir todavía no guarda su versión.
        corregidas = (s.veces_devuelta or 0) - (1 if s.estado == Estado.EN_CORRECCION.value else 0)
        return s, SalidaRegistro(
            versiones=[
                SalidaVersion(
                    numero=v.numero, enviada_en=v.enviada_en, enviada_por=v.enviada_por, devuelta_en=v.devuelta_en,
                    devuelta_por=v.devuelta_por, motivo=v.motivo, corregida_en=v.corregida_en, corregida_por=v.corregida_por,
                    datos=v.datos["datos"], tripulantes=v.datos["tripulantes"], documentos=v.datos["documentos"],
                    cambios=comparar(antes, despues),
                )
                for v, antes, despues in zip(versiones, fotos, fotos[1:], strict=False)
            ],
            sin_version=max(corregidas - len(versiones), 0),
            archivos=archivos,
        )

    @staticmethod
    def nombre_emitido(s: Solicitud, x: DocumentoEmitido) -> str:
        return f"Autorizacion-{s.numero or s.id}-{x.tipo}.pdf"

    async def obtener_emitido(
        self, ctx: ContextoAcceso, solicitud_id: int, emitido_id: int,
    ) -> tuple[Solicitud, DocumentoEmitido, Path]:
        """Una autorización tal como se emitió, si sigue intacta."""
        s = await self._para_registro(ctx, solicitud_id)
        emitido = next((x for x in await self.repo.emitidos(s.id) if x.id == emitido_id), None)
        if emitido is None:
            raise _error(status.HTTP_404_NOT_FOUND, "Autorización no encontrada en esta solicitud.")
        return s, emitido, await self._archivo_intacto(emitido.ruta, emitido.sha256, f"La autorización emitida {emitido.id}")

    # ── UCVMM: revisión ──────────────────────────────────────────────────────

    async def _para_revision(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        if not ctx.puede_revisar:
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_REVISAR}.")
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
        if not ctx.puede_revisar_esta(s):
            raise _error(status.HTTP_403_FORBIDDEN, "La solicitud es de un puesto de otro sector.")
        if self._tiene_conflicto(ctx, s):
            raise _error(
                status.HTTP_403_FORBIDDEN,
                "No puedes revisar una solicitud que creaste o que es de tu agencia.",
            )
        if s.estado != Estado.EN_REVISION.value:
            raise _error(status.HTTP_409_CONFLICT, "La solicitud no está pendiente de revisión.")
        return s

    async def registrar_impedimentos(
        self, ctx: ContextoAcceso, solicitud_id: int, datos: DatosImpedimentos,
    ) -> Solicitud:
        """Verificación de impedimentos (SIMPLUS) por tripulante: cada uno
        queda "sin impedimento" o "con impedimento". Con impedimentos igual
        se puede aprobar (el proceso indica informar a Operaciones). El
        comentario es opcional.

        Si ya estaba registrada en esta revisión (corregir() la reinicia),
        cambiarla es una corrección: exige motivo y el historial dice qué
        cambió. Sin cambios no se registra nada."""
        s = await self._para_revision(ctx, solicitud_id)
        return await self._verificar_impedimentos(ctx, s, datos, _VERIFICACION_UCVMM)

    async def _verificar_impedimentos(
        self, ctx: ContextoAcceso, s: Solicitud, datos: DatosImpedimentos, etapa: _EtapaVerificacion,
    ) -> Solicitud:
        """Registra o corrige la verificación de una etapa (UCVMM o puesto de control)."""
        por_id = {t.id: t for t in s.tripulantes}
        recibidos = {d.tripulante_id: d.con_impedimento for d in datos.tripulantes}
        if len(recibidos) != len(datos.tripulantes) or set(recibidos) != set(por_id):
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "Indica el resultado de la verificación de cada tripulante de la solicitud (una vez cada uno).",
            )

        correccion = getattr(s, etapa.verificados)
        cambios = [
            f"{por_id[i].nombre_completo} pasa de {_resultado(getattr(por_id[i], etapa.tripulante))} a {_resultado(c)}"
            for i, c in recibidos.items() if getattr(por_id[i], etapa.tripulante) != c
        ]
        cambia_comentario = datos.comentario != getattr(s, etapa.comentario)
        if correccion:
            if not cambios and not cambia_comentario:
                raise _error(status.HTTP_409_CONFLICT, "La verificación de impedimentos no tiene cambios.")
            if len(datos.motivo_correccion or "") < 5:
                raise _error(status.HTTP_400_BAD_REQUEST, "Indica el motivo de la corrección (al menos 5 caracteres).")

        for tripulante_id, con_impedimento in recibidos.items():
            setattr(por_id[tripulante_id], etapa.tripulante, con_impedimento)
        con = [por_id[i].nombre_completo for i, c in recibidos.items() if c]

        setattr(s, etapa.verificados, True)
        setattr(s, etapa.comentario, datos.comentario)
        setattr(s, etapa.en, ahora_utc())
        setattr(s, etapa.por_id, ctx.usuario.id)
        if correccion:
            partes = ["; ".join(cambios) + "." if cambios else "Se actualiza el comentario."]
            if cambia_comentario and datos.comentario:
                partes.append(f"Comentario: {_con_punto(datos.comentario)}")
            partes.append(f"Motivo: {_con_punto(datos.motivo_correccion or '')}")
            texto = " ".join(partes)
            tipo = etapa.evento_corregido
        else:
            # El título del evento ya dice "Verificación de impedimentos": aquí solo el resultado.
            total = len(recibidos)
            if not con:
                texto = "Sin impedimento." if total == 1 else f"Sin impedimentos ({total} tripulantes)."
            else:
                texto = f"Con impedimento: {', '.join(con)}"
                texto += f" ({len(con)} de {total} tripulantes)." if total > 1 else "."
            if datos.comentario:
                texto += f" {datos.comentario}"
            tipo = etapa.evento
        self._registrar_evento(s, ctx.usuario, tipo, None, None, texto)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def aprobar(self, ctx: ContextoAcceso, solicitud_id: int, observacion: str | None) -> Solicitud:
        s = await self._para_revision(ctx, solicitud_id)
        if not s.impedimentos_verificados or any(t.con_impedimento is None for t in s.tripulantes):
            raise _error(status.HTTP_409_CONFLICT, "Antes de aprobar registra la verificación de impedimentos de cada tripulante.")
        limite = s.fecha_operacion + timedelta(days=configuracion.DIAS_GRACIA_FINALIZACION)
        if limite < hoy_panama():
            raise _error(
                status.HTTP_409_CONFLICT,
                "La fecha de la operación ya pasó: devuelve la solicitud a corrección para que la agencia la actualice.",
            )

        anterior = s.estado
        s.estado                 = Estado.APROBADA.value
        s.sector_revision_id     = s.puesto.sector_id
        s.aprobada_en            = ahora_utc()
        s.aprobada_por_id        = ctx.usuario.id
        s.observacion_aprobacion = observacion
        # Fuera del horario laboral lleva el recargo de hoy (2026-11-11).
        costo = configuracion.COSTO_FUERA_DE_HORARIO
        s.costo_fuera_de_horario = costo if costo > 0 and fuera_de_horario(s.aprobada_en) else None
        # Vale las horas del trámite desde la aprobación (Urgencia médica, 120: 2026-11-26) o, si
        # no las tiene, hasta el final del día, DIAS_GRACIA_FINALIZACION días después de la operación.
        horas = s.tipo_tramite.horas_vigencia
        s.vigente_hasta          = s.aprobada_en + timedelta(hours=horas) if horas else fin_del_dia(limite)
        s.codigo_verificacion    = secrets.token_urlsafe(24)
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.APROBADA, anterior, s.estado, observacion)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def devolver(self, ctx: ContextoAcceso, solicitud_id: int, motivo: str) -> Solicitud:
        s = await self._para_revision(ctx, solicitud_id)
        anterior = s.estado
        s.estado             = Estado.EN_CORRECCION.value
        s.sector_revision_id = s.puesto.sector_id
        s.motivo_devolucion  = motivo
        s.plazo_correccion   = ahora_utc() + timedelta(days=configuracion.PLAZO_CORRECCION_DIAS)
        s.veces_devuelta     = (s.veces_devuelta or 0) + 1
        # Quiénes tienen impedimento, en el historial que ve la agencia (2026-11-26).
        aviso = aviso_impedimentos(self.con_impedimento_al_devolver(s))
        texto = f"{motivo}\n\n{aviso}" if aviso else motivo
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.DEVUELTA, anterior, s.estado, texto)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def negar(self, ctx: ContextoAcceso, solicitud_id: int, motivo: str) -> Solicitud:
        s = await self._para_revision(ctx, solicitud_id)
        anterior = s.estado
        s.estado             = Estado.NEGADA.value
        s.sector_revision_id = s.puesto.sector_id
        s.negada_en          = ahora_utc()
        s.negada_por_id      = ctx.usuario.id
        s.motivo_negacion    = motivo
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.NEGADA, anterior, s.estado, motivo)
        await self.repo.guardar()
        return await self._recargar(s.id)

    # ── Puesto de control: finalizar ─────────────────────────────────────────

    async def _para_puerto(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
        if not self._es_del_puerto(ctx, s):
            if s.puesto_destino_id is not None:
                # La ve por otro permiso (UCVMM de su sector, también en el primer puesto).
                raise _error(status.HTTP_403_FORBIDDEN,
                             f"La autorización tiene cambio de puerto: la finaliza {s.puesto_destino_nombre}.")
            raise _error(status.HTTP_403_FORBIDDEN, "La solicitud no corresponde a tus puestos de control.")
        if s.estado != Estado.APROBADA.value:
            raise _error(status.HTTP_409_CONFLICT, "La autorización no está aprobada pendiente de finalizar.")
        if s.vigente_hasta and s.vigente_hasta < ahora_utc():
            raise _error(status.HTTP_409_CONFLICT, "La autorización venció sin finalizarse.")
        return s

    async def registrar_impedimentos_puesto(
        self, ctx: ContextoAcceso, solicitud_id: int, datos: DatosImpedimentos,
    ) -> Solicitud:
        """El puesto de control verifica los impedimentos en SIMPLUS antes de
        finalizar (2026-11-06): al momento de la operación pudo aparecer uno
        que no estaba cuando UCVMM aprobó. Funciona como la de UCVMM (por
        tripulante, comentario opcional, corrección con motivo) y se guarda
        aparte. Con impedimento igual se puede finalizar: lo ocurrido con esa
        persona va en el comentario de la operación."""
        s = await self._para_puerto(ctx, solicitud_id)
        return await self._verificar_impedimentos(ctx, s, datos, _VERIFICACION_PUESTO)

    async def finalizar(
        self, ctx: ContextoAcceso, solicitud_id: int, comentario: str, puesto_finalizacion_id: int | None = None,
    ) -> Solicitud:
        """Cierra la autorización en el puesto autorizado (con cambio de puerto,
        el nuevo), con la verificación de impedimentos del puesto ya registrada
        (desde el 2026-11-06). Desde el 2026-10-30 no se finaliza en otro puesto:
        si la operación se hace en otro, la agencia presenta una nueva solicitud y
        esta vence sola. `puesto_finalizacion_id` solo llega de una página abierta
        antes del cambio: si es otro puesto, se rechaza con el motivo en vez de
        cerrarla donde no fue."""
        s = await self._para_puerto(ctx, solicitud_id)
        if puesto_finalizacion_id is not None and puesto_finalizacion_id != s.puesto_autorizado_id:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"La autorización es solo para {s.puesto_autorizado_nombre}: no se finaliza en otro puesto. Si la "
                "operación se realizó en otro, la agencia debe presentar una nueva solicitud.",
            )
        if not s.impedimentos_puesto_verificados or any(t.con_impedimento_puesto is None for t in s.tripulantes):
            raise _error(
                status.HTTP_409_CONFLICT,
                "Antes de finalizar registra la verificación de impedimentos de cada tripulante en SIMPLUS.",
            )
        anterior = s.estado
        s.estado                     = Estado.FINALIZADA.value
        s.finalizada_en              = ahora_utc()
        s.finalizada_por_id          = ctx.usuario.id
        s.comentario_finalizacion    = comentario
        # Se sigue registrando (es el autorizado) para las estadísticas por puesto y las finalizadas de antes.
        s.puesto_finalizacion_id     = s.puesto_autorizado_id
        s.puesto_finalizacion_nombre = s.puesto_autorizado_nombre
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.FINALIZADA, anterior, s.estado,
                               f"Finalizada en {s.puesto_autorizado_nombre}. {comentario}")
        await self.repo.guardar()
        return await self._recargar(s.id)

    # ── Vencimientos (proceso automático) ────────────────────────────────────

    async def expirar_vencidas(self) -> list[Vencimiento]:
        """Expira las aprobadas que no se finalizaron a tiempo y las devueltas
        que la agencia no corrigió dentro del plazo."""
        ahora = ahora_utc()
        vencimientos: list[Vencimiento] = []
        for s in await self.repo.listar_vencidas(ahora):
            anterior = s.estado
            if anterior == Estado.APROBADA.value:
                motivo = "La autorización no se finalizó en el puesto de control dentro del plazo."
            else:
                motivo = (
                    "La agencia no corrigió la solicitud dentro del plazo de "
                    f"{configuracion.PLAZO_CORRECCION_DIAS * 24} horas."
                )
            s.estado      = Estado.EXPIRADA.value
            s.expirada_en = ahora
            self._registrar_evento(s, None, TipoEventoSolicitud.EXPIRADA, anterior, s.estado, motivo)
            vencimientos.append(Vencimiento(solicitud=s, estado_anterior=anterior, motivo=motivo))
        if vencimientos:
            await self.repo.guardar()
        return vencimientos

    # ── Salidas ──────────────────────────────────────────────────────────────

    @staticmethod
    def _vencimientos_tripulante(t: TripulanteSolicitud, referencia: date) -> tuple[bool, bool, bool]:
        """(pasaporte vencido, pasaporte con menos de 3 meses de vigencia, seamanbook
        vencido) a la fecha de la operación. Lo mismo cuenta la bandeja en SQL
        (RepositorioSolicitud.alertas_de): si cambias uno, cambia el otro."""
        pasaporte = t.pasaporte_expira < referencia
        corta     = not pasaporte and t.pasaporte_expira < vigencia_minima_pasaporte(referencia)
        libreta   = bool(t.porta_libreta and t.libreta_expira and t.libreta_expira < referencia)
        return pasaporte, corta, libreta

    def construir_resumen(
        self, s: Solicitud, *, interno: bool, alertas: tuple[int, bool] | None = None,
        encontrados: list[tuple[str, str]] | None = None,
    ) -> SalidaSolicitudResumen:
        return SalidaSolicitudResumen(
            **self._campos_resumen(s, interno=interno, alertas=alertas),
            tripulantes_encontrados=None if encontrados is None else [
                SalidaTripulanteEncontrado(nombre=nombre, pasaporte=pasaporte) for nombre, pasaporte in encontrados
            ],
        )

    def _campos_resumen(self, s: Solicitud, *, interno: bool, alertas: tuple[int, bool] | None = None) -> dict:
        """`interno`: quien consulta es del SNM. Lo interno no le llega a la agencia.
        `alertas` = (tripulantes con documento vencido o pasaporte con menos de 3 meses
        de vigencia, ¿alguno restringido?), ya
        contados por la BD (bandejas, RepositorioSolicitud.alertas_de); sin ellas
        se cuentan aquí, con los tripulantes cargados (el expediente)."""
        if alertas is None:
            alertas = (
                sum(1 for t in s.tripulantes if any(self._vencimientos_tripulante(t, s.fecha_operacion))),
                any(t.nacionalidad_restringida for t in s.tripulantes),
            )
        con_alerta, alguno_restringido = alertas
        return dict(
            id=s.id, numero=s.numero, titulo=s.titulo, estado=s.estado,
            tipo_tramite_codigo=s.tipo_tramite.codigo, tipo_tramite_nombre=s.tipo_tramite.nombre,
            agencia_id=s.agencia_id, agencia_nombre=s.agencia_nombre, puesto_nombre=s.puesto_nombre,
            puesto_destino_nombre=s.puesto_destino_nombre, operacion=s.operacion, dias_sellado=s.dias_sellado,
            # El sector que la revisó (o el del puesto, sin revisar), para el SNM: la agencia
            # no trabaja con sectores. Si el puesto ya es de otro, también el de hoy (2026-11-22).
            sector_nombre=s.sector.nombre if interno else None,
            sector_actual_nombre=s.puesto.sector.nombre if interno and s.puesto.sector_id != s.sector_id else None,
            nombre_buque=s.nombre_buque, imo=s.imo, fecha_operacion=s.fecha_operacion,
            cantidad_tripulantes=s.cantidad_tripulantes,
            creada_por=s.creada_por.full_name if s.creada_por else None,
            created_at=s.created_at, enviada_en=s.enviada_en,
            plazo_correccion=s.plazo_correccion, vigente_hasta=s.vigente_hasta, horas_vigencia=self.horas_vigencia(s),
            aprobada_en=s.aprobada_en, negada_en=s.negada_en,
            finalizada_en=s.finalizada_en, expirada_en=s.expirada_en,
            veces_devuelta=s.veces_devuelta or 0,
            tripulantes_con_alerta=con_alerta,
            tiene_nacionalidad_restringida=alguno_restringido,
            # Aprobada fuera del horario laboral (2026-11-06; antes, por la finalización).
            # Desde el 2026-11-11 lo ve también la agencia, con el recargo.
            fuera_de_horario=fuera_de_horario(s.aprobada_en) if s.aprobada_en else None,
            costo_fuera_de_horario=texto_costo(s.costo_fuera_de_horario) if s.costo_fuera_de_horario else None,
        )

    @staticmethod
    def _autor_ultimo(s: Solicitud, *tipos: TipoEventoSolicitud) -> str | None:
        valores = {t.value for t in tipos}
        return next((e.usuario_nombre for e in reversed(s.eventos) if e.tipo in valores), None)

    @staticmethod
    def evento_para(e, interno: bool) -> SalidaEvento | None:
        """Un evento del historial tal como lo ve quien consulta. La agencia no ve
        lo interno del SNM (impedimentos, comentarios del puesto, la observación
        de aprobación ni el texto de cierre) ni el nombre del funcionario: ve los
        estados y los motivos que le corresponden (devolución y negación). Lo usan
        el expediente y las novedades de las notificaciones internas."""
        salida = SalidaEvento.model_validate(e)
        if interno:
            return salida
        if e.tipo in _EVENTOS_INTERNOS:
            return None
        cambios: dict = {}
        if e.tipo in _AUTOR_PARA_AGENCIA:
            cambios["usuario_nombre"] = _AUTOR_PARA_AGENCIA[e.tipo]
        if e.tipo in _SIN_TEXTO_PARA_AGENCIA:
            cambios["comentario"] = None
        return salida.model_copy(update=cambios)

    async def _nombre_pais(self, codigo: str | None) -> str | None:
        if not codigo:
            return None
        pais = await self.repo_catalogos.buscar_pais(codigo)
        return pais.nombre if pais else codigo

    async def construir_detalle(self, ctx: ContextoAcceso, s: Solicitud) -> SalidaSolicitud:
        # El tipo con su checklist (la relación de la solicitud no lo trae cargado)
        tipo = await self.repo_tramites.buscar_tipo_por_id(s.tipo_tramite_id)
        assert tipo is not None

        # Devuelta, la agencia ve quiénes tienen impedimento (2026-11-26).
        devuelta = s.estado == Estado.EN_CORRECCION.value
        tripulantes = []
        for t in s.tripulantes:
            pasaporte_vencido, pasaporte_corta, libreta_vencida = self._vencimientos_tripulante(t, s.fecha_operacion)
            tripulantes.append(SalidaTripulante(
                id=t.id, nombre=t.nombre, apellido=t.apellido, nombre_completo=t.nombre_completo,
                fecha_nacimiento=t.fecha_nacimiento,
                pais_nacimiento=t.pais_nacimiento,
                pais_nacimiento_nombre=t.pais_nacimiento_ref.nombre if t.pais_nacimiento_ref else None,
                nacionalidad=t.nacionalidad,
                nacionalidad_nombre=t.nacionalidad_ref.nombre if t.nacionalidad_ref else None,
                sexo=t.sexo, pasaporte=t.pasaporte, pasaporte_expira=t.pasaporte_expira,
                libreta_marino=t.libreta_marino, libreta_expira=t.libreta_expira,
                rango=t.rango, ocupacion=t.ocupacion, es_panameno=t.es_panameno,
                nacionalidad_restringida=t.nacionalidad_restringida,
                con_impedimento=(t.con_impedimento if ctx.es_personal_snm
                                 else (True if devuelta and t.con_impedimento else None)),
                con_impedimento_puesto=t.con_impedimento_puesto if ctx.es_personal_snm else None,
                porta_libreta=t.porta_libreta, orden=t.orden,
                pasaporte_vencido=pasaporte_vencido, pasaporte_vigencia_corta=pasaporte_corta,
                libreta_vencida=libreta_vencida,
            ))

        documentos = [
            SalidaDocumentoSolicitud(
                # El tipo del formato verificado, el mismo con que se sirve el archivo.
                id=d.id, nombre_original=d.nombre_original, tamano=d.tamano,
                tipo_mime=almacenamiento.mime_del_formato(d.nombre_almacenado),
                documento_id=d.documento_id,
                documento_codigo=d.documento.codigo if d.documento else None,
                documento_nombre=d.documento.nombre if d.documento else None,
                tripulante_id=d.tripulante_id, created_at=d.created_at,
            )
            for d in s.documentos
        ]

        # Contra la foto del checklist con el que se envió (o corrigió): un
        # cambio posterior del catálogo no deja incompleta una solicitud que cumplía.
        nombres = {t.id: t.nombre_completo for t in s.tripulantes}
        checklist = []
        for c in s.casillas:
            ids = [d.id for d in s.documentos if d.documento_id == c.documento_id and d.tripulante_id == c.tripulante_id]
            checklist.append(SalidaCasilla(
                documento_id=c.documento_id, documento_codigo=c.documento.codigo,
                documento_nombre=c.documento.nombre,
                alcance=AlcanceDocumento.SOLICITUD.value if c.tripulante_id is None else AlcanceDocumento.MARINO.value,
                tripulante_id=c.tripulante_id,
                tripulante_nombre=nombres.get(c.tripulante_id) if c.tripulante_id is not None else None,
                documento_ids=ids, cubierta=bool(ids), obligatoria=c.obligatoria,
            ))

        interno = ctx.es_personal_snm
        ve_boletas = self.ve_boletas(ctx, s)
        eventos = [ev for ev in (self.evento_para(e, interno) for e in s.eventos)
                   if ev is not None and (ve_boletas or ev.tipo not in _EVENTOS_BOLETA)]

        return SalidaSolicitud(
            **self._campos_resumen(s, interno=interno),
            tipo_tramite_nota=tipo.nota,
            tipo_tramite_aviso_custodia=tipo.aviso_custodia,
            requiere_buque=tipo.requiere_buque, requiere_puerto=tipo.requiere_puerto,
            requiere_puerto_desembarque=tipo.requiere_puerto_desembarque,
            requiere_motivo=tipo.requiere_motivo, requiere_clinica=tipo.requiere_clinica,
            valida_vigencia=tipo.valida_vigencia,
            puesto_control_id=s.puesto_control_id, puesto_destino_id=s.puesto_destino_id,
            subir_y_bajar=s.subir_y_bajar, permite_subir_y_bajar=tipo.permite_subir_y_bajar,
            pide_operacion=tipo.pide_operacion, pide_dias_sellado=tipo.pide_dias_sellado,
            bandera=s.bandera, bandera_nombre=await self._nombre_pais(s.bandera),
            nombre_puerto=s.nombre_puerto, puerto_desembarque=s.puerto_desembarque,
            motivo=s.motivo, clinica_hospital=s.clinica_hospital, observaciones=s.observaciones,
            impedimentos_verificados=s.impedimentos_verificados if interno else False,
            comentario_impedimentos=s.comentario_impedimentos if interno else None,
            tripulantes_con_impedimento=self.con_impedimento_al_devolver(s),
            impedimentos_verificados_en=s.impedimentos_verificados_en if interno else None,
            impedimentos_verificados_por=self._autor_ultimo(
                s, TipoEventoSolicitud.IMPEDIMENTOS, TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS,
            ) if interno else None,
            impedimentos_puesto_verificados=s.impedimentos_puesto_verificados if interno else False,
            comentario_impedimentos_puesto=s.comentario_impedimentos_puesto if interno else None,
            impedimentos_puesto_en=s.impedimentos_puesto_en if interno else None,
            impedimentos_puesto_por=self._autor_ultimo(
                s, TipoEventoSolicitud.IMPEDIMENTOS_PUESTO, TipoEventoSolicitud.IMPEDIMENTOS_PUESTO_CORREGIDOS,
            ) if interno else None,
            motivo_devolucion=s.motivo_devolucion,
            observacion_aprobacion=s.observacion_aprobacion if interno else None,
            aprobada_por=self._autor_ultimo(s, TipoEventoSolicitud.APROBADA) if interno else None,
            motivo_negacion=s.motivo_negacion,
            comentario_finalizacion=s.comentario_finalizacion if interno else None,
            finalizada_por=self._autor_ultimo(s, TipoEventoSolicitud.FINALIZADA) if interno else None,
            puesto_finalizacion_id=s.puesto_finalizacion_id,
            puesto_finalizacion_nombre=s.puesto_finalizacion_nombre,
            tripulantes=tripulantes, documentos=documentos, checklist=checklist,
            eventos=eventos,
            acciones=self.acciones(ctx, s),
            boletas=[self.salida_boleta(b) for b in s.boletas] if ve_boletas else None,
        )

    # ── Boleta de recargo (2026-11-16) ───────────────────────────────────────

    @staticmethod
    def salida_boleta(b: BoletaRecargo) -> SalidaBoleta:
        return SalidaBoleta(
            id=b.id, numero_oficio=b.numero_oficio, monto=texto_costo(b.monto), generada_en=b.generada_en,
            generada_por=b.generada_por.full_name if b.generada_por else None,
            anulada_en=b.anulada_en, anulada_por=b.anulada_por.full_name if b.anulada_por else None,
            motivo_anulacion=b.motivo_anulacion, vigente=b.vigente,
        )

    async def _para_boleta(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        """La solicitud bloqueada (FOR UPDATE), si quien pide es de UCVMM de su sector: dos
        funcionarios que generan a la vez no dejan dos vigentes. Quién anula cuál, en
        `puede_anular_boleta`."""
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
        if not self._es_ucvmm_de(ctx, s):
            raise _error(status.HTTP_403_FORBIDDEN,
                         "La boleta la pone UCVMM: el analista que aprobó la solicitud o, si no está, otro de su sector.")
        if s.costo_fuera_de_horario is None or s.aprobada_en is None:
            raise _error(status.HTTP_409_CONFLICT,
                         "La solicitud no lleva recargo: no se aprobó fuera del horario laboral.")
        return s

    async def generar_boleta(
        self, ctx: ContextoAcceso, solicitud_id: int, numero_oficio: str,
    ) -> tuple[Solicitud, BoletaRecargo]:
        """Una boleta nueva con el número de oficio (ya normalizado por DatosBoleta): una
        sola vigente por solicitud y un número que ninguna otra boleta tenga, anulada o no."""
        s = await self._para_boleta(ctx, solicitud_id)
        if any(b.vigente for b in s.boletas):
            raise _error(status.HTTP_409_CONFLICT,
                         "La solicitud ya tiene una boleta vigente. Para generar otra, anula la vigente.")
        otra = await self.repo.boleta_con_numero(numero_oficio)
        if otra is not None:
            duena = await self.repo.buscar_por_id(otra.solicitud_id)
            raise _error(status.HTTP_409_CONFLICT,
                         f"El número de oficio {otra.numero_oficio} ya está en la boleta de la solicitud "
                         f"{duena.numero if duena and duena.numero else otra.solicitud_id}"
                         f"{' (anulada)' if not otra.vigente else ''}.")
        boleta = BoletaRecargo(
            solicitud_id=s.id, numero_oficio=numero_oficio, monto=s.costo_fuera_de_horario,
            generada_en=ahora_utc(), generada_por_id=ctx.usuario.id,
        )
        self.repo.agregar_registro(boleta)
        # Si no la pone quien aprobó, queda dicho en lugar de quién (2026-11-27).
        en_lugar_de = await self.en_lugar_de(ctx, s)
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.BOLETA_GENERADA, None, None,
                               f"Oficio N.º {numero_oficio}"
                               f"{f', en lugar de {en_lugar_de}, que la aprobó' if en_lugar_de else ''}.")
        try:
            await self.repo.guardar()
        except IntegrityError as exc:
            # La carrera que el bloqueo no cubre: el mismo número en otra solicitud a la vez.
            raise _error(status.HTTP_409_CONFLICT,
                         f"El número de oficio {numero_oficio} ya está en otra boleta.") from exc
        s = await self._recargar(s.id)
        return s, next(b for b in s.boletas if b.id == boleta.id)

    async def anular_boleta(
        self, ctx: ContextoAcceso, solicitud_id: int, boleta_id: int, motivo: str,
    ) -> tuple[Solicitud, BoletaRecargo]:
        """Como en un talonario: la boleta queda anulada, con su número, y se puede
        generar otra con otro número."""
        s = await self._para_boleta(ctx, solicitud_id)
        boleta = next((b for b in s.boletas if b.id == boleta_id), None)
        if boleta is None:
            raise _error(status.HTTP_404_NOT_FOUND, "Boleta no encontrada.")
        if not boleta.vigente:
            raise _error(status.HTTP_409_CONFLICT, "La boleta ya está anulada.")
        if not self.puede_anular_boleta(ctx, s, boleta):
            raise _error(status.HTTP_403_FORBIDDEN,
                         "La anula quien aprobó la solicitud o quien generó esta boleta.")
        boleta.anulada_en = ahora_utc()
        boleta.anulada_por_id = ctx.usuario.id
        boleta.motivo_anulacion = motivo
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.BOLETA_ANULADA, None, None,
                               f"Oficio N.º {boleta.numero_oficio}. Motivo: {_con_punto(motivo)}")
        await self.repo.guardar()
        s = await self._recargar(s.id)
        return s, next(b for b in s.boletas if b.id == boleta_id)

    async def datos_pdf_boleta(
        self, ctx: ContextoAcceso, solicitud_id: int, boleta_id: int,
    ) -> tuple[Solicitud, BoletaRecargo, DatosPdfBoleta]:
        """La boleta para el PDF: la descargan quienes la ven (`ve_boletas`): UCVMM y el supervisor
        de sector de sus sectores y el Administrador (2026-11-27)."""
        s = await self.obtener(ctx, solicitud_id)
        if not self.ve_boletas(ctx, s):
            raise _error(status.HTTP_403_FORBIDDEN,
                         "La boleta de recargo la ven UCVMM, el supervisor de sector y el Administrador.")
        boleta = next((b for b in s.boletas if b.id == boleta_id), None)
        if boleta is None or s.aprobada_en is None:
            raise _error(status.HTTP_404_NOT_FOUND, "Boleta no encontrada.")
        # El tipo de operación en casillas (2026-11-16): los trámites activos, en su orden.
        tipos = await self.repo_tramites.listar_tipos(solo_activos=True)
        return s, boleta, DatosPdfBoleta(
            numero_oficio=boleta.numero_oficio, monto=boleta.monto, numero_solicitud=s.numero or str(s.id),
            tipo_tramite=s.tipo_tramite.nombre, agencia=s.agencia_nombre, buque=s.nombre_buque,
            puesto=s.puesto_nombre, puesto_destino=s.puesto_destino_nombre,
            aprobada_en=s.aprobada_en.astimezone(ZONA_PANAMA),
            generada_en=boleta.generada_en.astimezone(ZONA_PANAMA),
            # Firma el jefe encargado del sector de UCVMM de la solicitud (2026-11-26).
            sector=s.sector.nombre,
            anulada_en=boleta.anulada_en.astimezone(ZONA_PANAMA) if boleta.anulada_en else None,
            motivo_anulacion=boleta.motivo_anulacion,
            tipos_operacion=[t.nombre for t in tipos],
            detalles=self._detalles_boleta(s),
        )

    @staticmethod
    def _respuesta_subir_y_bajar(s: Solicitud) -> bool | None:
        """La respuesta a «¿Subir y bajar?» para el PDF y la boleta: None si el trámite no
        pregunta, salvo en las de antes que respondieron «Sí» (Embarque y Desembarque, del
        2026-11-16 al 18), que lo siguen diciendo."""
        return s.subir_y_bajar if s.tipo_tramite.permite_subir_y_bajar or s.subir_y_bajar else None

    @classmethod
    def _detalles_boleta(cls, s: Solicitud) -> list[str]:
        """Lo que eligió la agencia, una línea cada cosa bajo la casilla marcada de la boleta
        (2026-11-27; del 2026-11-26 al 27, entre paréntesis en la misma línea): la operación
        (Técnico y, del 2026-11-26 al 27, Urgencia médica), los días del sellado (Shore Pass y
        Urgencia médica) y, en las de antes que respondieron «Sí», «Subir y bajar». El cambio de
        puerto lo suma `casillas_operacion`, con los dos puestos."""
        lineas = []
        if s.operacion:
            lineas.append(f"Operación: {ETIQUETA_OPERACION[s.operacion]}")
        if s.dias_sellado:
            lineas.append(f"Sellado: {texto_dias(s.dias_sellado)}")
        if cls._respuesta_subir_y_bajar(s):
            lineas.append("Subir y bajar: Sí")
        return lineas

    # ── Autorización (PDF) y verificación pública ────────────────────────────

    @staticmethod
    def url_verificacion(codigo: str) -> str:
        """Adonde apunta el QR: la dirección pública de la verificación, si la DTI la
        publicó (URL_VERIFICACION_PUBLICA); si no, la del sistema."""
        return f"{configuracion.url_base_verificacion}/verificar/{codigo}"

    async def preparar_pdf(self, ctx: ContextoAcceso, s: Solicitud) -> DatosPdfAutorizacion:
        if not self.acciones(ctx, s).descargar_autorizacion or not s.codigo_verificacion:
            raise _error(status.HTTP_409_CONFLICT, "La autorización solo se descarga cuando la solicitud está aprobada o finalizada.")
        return await self._datos_pdf(s, interno=ctx.es_personal_snm)

    @staticmethod
    def _vigente(s: Solicitud, ahora: datetime) -> bool:
        """Si la autorización vale: finalizada, o aprobada y dentro de su plazo."""
        return s.estado == Estado.FINALIZADA.value or (
            s.estado == Estado.APROBADA.value and (s.vigente_hasta is None or s.vigente_hasta >= ahora)
        )

    def pdf_publico_disponible(self, s: Solicitud) -> bool:
        """Si el PDF se puede ver por el QR, sin sesión (2026-11-14): mientras la
        autorización valga y hasta DIAS_PDF_PUBLICO días después de la operación.
        Después, la agencia lo descarga con su cuenta."""
        if s.aprobada_en is None or not s.codigo_verificacion or not self._vigente(s, ahora_utc()):
            return False
        return hoy_panama() <= s.fecha_operacion + timedelta(days=configuracion.DIAS_PDF_PUBLICO)

    async def pdf_publico(self, codigo: str) -> tuple[Solicitud | None, DatosPdfAutorizacion | None]:
        """La copia de la agencia, para quien escanea el QR. (None, None) si el código no
        existe o si ya no se puede ver así (la ruta lleva a la verificación, que
        explica por qué)."""
        s = await self.repo.buscar_por_codigo_verificacion(codigo)
        if not s or not self.pdf_publico_disponible(s):
            return None, None
        return s, await self._datos_pdf(s, interno=False)

    async def datos_para_emitir(self, s: Solicitud) -> DatosPdfAutorizacion:
        """La copia de la agencia, para guardarla tal como se emite (infrastructure/emision.py)."""
        return await self._datos_pdf(s, interno=False)

    async def _datos_pdf(self, s: Solicitud, *, interno: bool) -> DatosPdfAutorizacion:
        assert s.aprobada_en is not None and s.codigo_verificacion
        # La agencia recibe la institución, sin nombres de funcionarios, como en su
        # vista del expediente (decisión del usuario, 2026-10-15). El personal del SNM,
        # una copia interna con el nombre de quien aprobó (reunión del 2026-10-30) y,
        # ya finalizada, el de quien finalizó (2026-11-14), tomados del historial.
        aprobador   = self._autor_ultimo(s, TipoEventoSolicitud.APROBADA) if interno else None
        finalizador = self._autor_ultimo(s, TipoEventoSolicitud.FINALIZADA) if interno else None
        return DatosPdfAutorizacion(
            numero=s.numero or str(s.id),
            estado=s.estado,
            tipo_tramite=s.tipo_tramite.nombre,
            nota_tramite=s.tipo_tramite.nota,
            aviso_custodia=s.tipo_tramite.aviso_custodia,
            agencia_naviera=s.agencia_nombre,
            nombre_buque=s.nombre_buque, imo=s.imo, bandera=await self._nombre_pais(s.bandera),
            puesto_control=s.puesto_nombre, puesto_destino=s.puesto_destino_nombre,
            # Solo en los trámites que hacen la pregunta (Embarque y Desembarque, 2026-11-16).
            subir_y_bajar=self._respuesta_subir_y_bajar(s),
            # La operación de Técnico y los días del sellado de Shore Pass (2026-11-18); None en
            # los demás trámites y en las de antes.
            operacion=ETIQUETA_OPERACION.get(s.operacion or ""),
            dias_sellado=texto_dias(s.dias_sellado) if s.dias_sellado else None,
            fecha_operacion=s.fecha_operacion,
            nombre_puerto=s.nombre_puerto, puerto_desembarque=s.puerto_desembarque,
            clinica_hospital=s.clinica_hospital, motivo=s.motivo,
            fecha_solicitud=s.enviada_en.astimezone(ZONA_PANAMA),
            aprobada_en=s.aprobada_en.astimezone(ZONA_PANAMA),
            aprobada_por=f"{aprobador} (UCVMM)" if aprobador else INSTITUCION,
            copia_interna=interno,
            fuera_de_horario=fuera_de_horario(s.aprobada_en),
            costo_fuera_de_horario=s.costo_fuera_de_horario,
            vigente_hasta=s.vigente_hasta.astimezone(ZONA_PANAMA) if s.vigente_hasta else None,
            horas_vigencia=self.horas_vigencia(s),
            finalizada_en=s.finalizada_en.astimezone(ZONA_PANAMA) if s.finalizada_en else None,
            expirada_en=s.expirada_en.astimezone(ZONA_PANAMA) if s.expirada_en else None,
            puesto_finalizacion=s.puesto_finalizacion_nombre,
            finalizada_por=f"{finalizador} (Puesto de control)" if finalizador else None,
            url_verificacion=self.url_verificacion(s.codigo_verificacion),
            codigo_verificacion=s.codigo_verificacion,
            tripulantes=[
                TripulantePdf(
                    nombre=t.nombre, apellido=t.apellido,
                    nacionalidad=t.nacionalidad_ref.nombre if t.nacionalidad_ref else t.nacionalidad,
                    pasaporte=t.pasaporte, libreta=t.libreta_marino or "",
                    rango=t.rango, ocupacion=t.ocupacion,
                    restringida=t.nacionalidad_restringida, porta_libreta=t.porta_libreta,
                )
                for t in s.tripulantes
            ],
        )

    async def verificar(self, codigo: str) -> SalidaVerificacion:
        s = await self.repo.buscar_por_codigo_verificacion(codigo)
        if not s:
            raise _error(status.HTTP_404_NOT_FOUND, "El código no corresponde a ninguna autorización emitida.")
        vigente = self._vigente(s, ahora_utc())

        def enmascarar(pasaporte: str) -> str:
            return "•" * max(len(pasaporte) - 4, 0) + pasaporte[-4:]

        return SalidaVerificacion(
            valida=vigente, estado=s.estado, numero=s.numero,
            pdf_disponible=self.pdf_publico_disponible(s),
            tipo_tramite=s.tipo_tramite.nombre,
            agencia_nombre=s.agencia_nombre,
            nombre_buque=s.nombre_buque, imo=s.imo, bandera=await self._nombre_pais(s.bandera),
            puesto_nombre=s.puesto_nombre, puesto_destino_nombre=s.puesto_destino_nombre,
            fecha_operacion=s.fecha_operacion,
            aprobada_en=s.aprobada_en, vigente_hasta=s.vigente_hasta, finalizada_en=s.finalizada_en,
            puesto_finalizacion_nombre=s.puesto_finalizacion_nombre,
            tripulantes=[
                SalidaTripulanteVerificacion(
                    nombre_completo=t.nombre_completo,
                    nacionalidad=t.nacionalidad_ref.nombre if t.nacionalidad_ref else t.nacionalidad,
                    pasaporte=enmascarar(t.pasaporte),
                    rango=t.rango,
                )
                for t in s.tripulantes
            ],
        )

    # ── Estadísticas ─────────────────────────────────────────────────────────

    async def alcance_estadisticas(self, ctx: ContextoAcceso, sector_id: int | None) -> AlcanceEstadisticas:
        """UCVMM y el supervisor de sector ven las de sus sectores; el Administrador,
        las de todos (el supervisor general no tiene estadísticas desde el
        2026-11-16). Los que ven más de un sector pueden elegir uno."""
        self._exigir_sector(ctx)
        sectores = await self.repo_catalogos.listar_sectores()
        elegibles = [x for x in sectores if ctx.ve_todos_los_sectores or x.id in ctx.sectores_ids]
        opciones = [(x.id, x.nombre) for x in elegibles]
        if sector_id is not None:
            elegido = next((x for x in elegibles if x.id == sector_id), None)
            if elegido is None:
                raise _error(status.HTTP_403_FORBIDDEN, "No puedes ver las estadísticas de ese sector.")
            alcance = AlcanceSectores(frozenset({elegido.id}), frozenset(pu.id for pu in elegido.puestos))
            return AlcanceEstadisticas(alcance, elegido.nombre, elegido.id, opciones, ctx.ve_todos_los_sectores)
        if ctx.ve_todos_los_sectores:
            return AlcanceEstadisticas(None, "Todos los sectores", None, opciones, True)
        return AlcanceEstadisticas(ctx.alcance_sectores, " y ".join(n for _, n in opciones), None, opciones, False)

    async def estadisticas(
        self, desde: date | None, hasta: date | None, alcance: AlcanceEstadisticas | None = None,
    ) -> SalidaEstadisticasSolicitudes:
        """Lo que pasó con las solicitudes recibidas en el periodo: por día, por
        mes y por año, más las aprobadas fuera del horario laboral (las 50 más
        recientes) y las aprobadas por día de la semana y hora (el mapa de horas).
        Solo las de los sectores del alcance (sin alcance, todas)."""
        sectores = alcance.filtro if alcance else None
        hitos = await self.repo.contar_hitos(desde, hasta, sectores)

        # La serie se cuenta por día y se agrupa aquí: los últimos días, meses y
        # años del periodo (con «Todo», hasta hoy).
        hoy = hoy_panama()
        fin = min(hasta, hoy) if hasta else hoy
        diaria = await self.repo.serie_diaria(desde, hasta, sectores)
        inicio_dias = max(desde or date.min, fin - timedelta(days=DIAS_EN_SERIE - 1))
        inicio_meses = max(desde or date.min, meses_antes(fin, MESES_EN_SERIE - 1))
        inicio_anios = max(desde or min(diaria, default=fin), date(fin.year - ANIOS_EN_SERIE + 1, 1, 1))

        return SalidaEstadisticasSolicitudes(
            recibidas=int(hitos["recibidas"] or 0),
            por_estado=await self.repo.contar_por_estado(desde, hasta, sectores),
            aprobadas=int(hitos["aprobadas"] or 0),
            negadas=int(hitos["negadas"] or 0),
            expiradas=int(hitos["expiradas"] or 0),
            finalizadas=int(hitos["finalizadas"] or 0),
            horas_promedio_resolucion=(
                round(float(hitos["horas"]), 1) if hitos["horas"] is not None else None
            ),
            aprobadas_fuera_horario=int(hitos["fuera_horario"] or 0),
            horario_laboral=TEXTO_HORARIO,
            operaciones_fuera_horario=[
                FilaFueraHorario(id=f.id, numero=f.numero, tipo_tramite=f.tipo_tramite, puesto=f.puesto,
                                 aprobada_en=f.aprobada_en, aprobada_por=f.aprobada_por)
                for f in await self.repo.listar_fuera_horario(desde, hasta, MAX_FUERA_HORARIO_LISTADAS, sectores)
            ],
            aprobadas_por_hora=[
                FilaPorHora(dia=int(f.dia), hora=int(f.hora), total=f.total)
                for f in await self.repo.aprobadas_por_hora(desde, hasta, sectores)
            ],
            por_tipo=[
                FilaEstadisticaTipo(
                    codigo=f.codigo, nombre=f.nombre,
                    recibidas=f.recibidas, aprobadas=f.aprobadas, negadas=f.negadas, expiradas=f.expiradas,
                )
                for f in await self.repo.contar_por_tipo(desde, hasta, sectores)
            ],
            por_dia=serie(diaria, periodos_dia(inicio_dias, fin), lambda d: d.isoformat()),
            por_mes=serie(diaria, periodos_mes(inicio_meses, fin), lambda d: f"{d.year:04d}-{d.month:02d}"),
            por_anio=serie(diaria, periodos_anio(inicio_anios, fin), lambda d: f"{d.year:04d}"),
            por_puesto=[
                FilaEstadisticaPuesto(puesto=f.nombre, aprobadas=f.aprobadas, finalizadas=f.finalizadas,
                                      expiradas=f.expiradas)
                for f in await self.repo.contar_por_puesto(desde, hasta, sectores)
            ],
            alcance=alcance.texto if alcance else "Todos los sectores",
            sector_id=alcance.sector_id if alcance else None,
            sectores=[FilaSector(id=i, nombre=n) for i, n in alcance.sectores] if alcance else [],
            uso_del_sistema=alcance.uso_del_sistema if alcance else True,
        )
