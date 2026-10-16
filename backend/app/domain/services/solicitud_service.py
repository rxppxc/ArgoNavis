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
    `usuarios_puestos`) ve las aprobadas de sus puestos, comenta y finaliza.
  - Cada transición bloquea la fila (SELECT ... FOR UPDATE): dos usuarios no
    pueden, por ejemplo, aprobar y negar la misma solicitud a la vez.
  - Cada paso queda en `solicitud_eventos` (historial con usuario y hora).
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obtener_configuracion
from app.core.pdf_autorizacion import DatosPdfAutorizacion, TripulantePdf
from app.core.permisos import (
    PERMISO_PUERTO, PERMISO_REVISAR, PERMISO_SOLICITAR, codigos_permiso, es_admin_efectivo,
)
from app.domain.models.catalogo import PuestoControl
from app.domain.models.solicitud import (
    RANGOS_CON_LIBRETA, CasillaSolicitud, DocumentoSolicitud, EstadoSolicitud, EventoSolicitud, Solicitud,
    TipoEventoSolicitud, TripulanteSolicitud,
)
from app.domain.models.tramite import AlcanceDocumento, TipoTramite, TramiteDocumento
from app.domain.models.user import Usuario
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.solicitud_repository import FiltrosBandeja, RepositorioSolicitud
from app.domain.repositories.tramite_repository import RepositorioTramite
from app.domain.schemas.solicitud import (
    AccionesSolicitud, AsignacionArchivo, ConsultaBandeja, DatosCorregirSolicitud,
    DatosCrearSolicitud, DatosImpedimentos, DatosTripulanteEntrada, FilaEstadisticaMes,
    FilaEstadisticaPuesto, FilaEstadisticaTipo, PaginaSolicitudes, SalidaCasilla,
    SalidaDocumentoSolicitud, SalidaEstadisticasSolicitudes, SalidaEvento, SalidaSolicitud,
    SalidaSolicitudResumen, SalidaTripulante, SalidaTripulanteVerificacion, SalidaVerificacion,
    _DatosFormularioSolicitud,
)
from app.domain.services.tramite_service import (
    CasillaChecklist, ServicioTramite, TripulanteChecklist, normalizar_imo,
)
from app.infrastructure import almacenamiento
from app.infrastructure.almacenamiento import ArchivoGuardado
from app.infrastructure.database import al_confirmar

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

TZ_PANAMA     = ZoneInfo("America/Panama")
CODIGO_PANAMA = "PAN"
Estado        = EstadoSolicitud
MAX_ERRORES_MOSTRADOS      = 8
MAX_DOCUMENTOS_ADICIONALES = 20

# (casilla del checklist o None si es un documento adicional, índice del tripulante)
Asignacion = tuple[TramiteDocumento | None, int | None]

# Historial que ve la agencia (ver ServicioSolicitud._evento_para).
_EVENTOS_INTERNOS = {
    TipoEventoSolicitud.IMPEDIMENTOS.value,
    TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS.value,
    TipoEventoSolicitud.COMENTARIO.value,
}
_SIN_TEXTO_PARA_AGENCIA = {TipoEventoSolicitud.APROBADA.value, TipoEventoSolicitud.FINALIZADA.value}
_AUTOR_PARA_AGENCIA = {
    TipoEventoSolicitud.DEVUELTA.value:   "UCVMM",
    TipoEventoSolicitud.APROBADA.value:   "UCVMM",
    TipoEventoSolicitud.NEGADA.value:     "UCVMM",
    TipoEventoSolicitud.FINALIZADA.value: "Puesto de control",
}


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def hoy_panama() -> date:
    return datetime.now(TZ_PANAMA).date()


def fin_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time(23, 59, 59), tzinfo=TZ_PANAMA)


def _resultado(con_impedimento: bool | None) -> str:
    """Resultado de un tripulante en SIMPLUS, para el historial."""
    return "con impedimento" if con_impedimento else "sin impedimento"


def _con_punto(texto: str) -> str:
    """Cierra una frase del historial (sin duplicar la puntuación del usuario)."""
    return texto if texto.endswith((".", "!", "?")) else f"{texto}."


def _error(codigo: int, detalle: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=detalle)


@dataclass
class ContextoAcceso:
    """Quién es el usuario dentro del flujo (se calcula una vez por request)."""
    usuario:     Usuario
    es_admin:    bool
    es_naviera:  bool
    es_revisor:  bool
    es_puerto:   bool
    puestos_ids: set[int]
    agencia_id:  int | None

    @property
    def puede_revisar(self) -> bool:
        return self.es_admin or self.es_revisor

    @property
    def es_personal_snm(self) -> bool:
        """UCVMM, puesto de control o admin. La verificación de impedimentos
        (y la acción tomada, p. ej. avisar a Operaciones) es información
        interna: no se muestra a la agencia."""
        return self.es_admin or self.es_revisor or self.es_puerto

    def es_de_su_agencia(self, s: Solicitud) -> bool:
        return (self.es_naviera or self.es_admin) and self.agencia_id is not None and s.agencia_id == self.agencia_id


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
            porta_libreta=self.porta_libreta,
            nacionalidad_restringida=self.restringido,
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
        return ContextoAcceso(
            usuario=usuario,
            es_admin=es_admin_efectivo(usuario),
            es_naviera=PERMISO_SOLICITAR in codigos,
            es_revisor=PERMISO_REVISAR in codigos,
            es_puerto=PERMISO_PUERTO in codigos,
            puestos_ids=await self.repo_catalogos.puestos_de_usuario(usuario.id),
            agencia_id=usuario.agencia_id,
        )

    @staticmethod
    def _es_del_puerto(ctx: ContextoAcceso, s: Solicitud) -> bool:
        return ctx.es_admin or (ctx.es_puerto and s.puesto_control_id in ctx.puestos_ids)

    @staticmethod
    def _tiene_conflicto(ctx: ContextoAcceso, s: Solicitud) -> bool:
        """Separación de funciones: nadie revisa lo que creó ni lo de su agencia."""
        return s.creada_por_id == ctx.usuario.id or (
            ctx.agencia_id is not None and s.agencia_id == ctx.agencia_id
        )

    def puede_ver(self, ctx: ContextoAcceso, s: Solicitud) -> bool:
        """La ven su agencia, UCVMM y el admin; el puesto de control, solo las
        de sus puestos y desde que se aprueban."""
        if ctx.puede_revisar or ctx.es_de_su_agencia(s):
            return True
        return s.aprobada_en is not None and self._es_del_puerto(ctx, s)

    def acciones(self, ctx: ContextoAcceso, s: Solicitud) -> AccionesSolicitud:
        ahora      = ahora_utc()
        vigente    = s.estado == Estado.APROBADA.value and (s.vigente_hasta is None or s.vigente_hasta >= ahora)
        en_plazo   = s.plazo_correccion is None or s.plazo_correccion >= ahora
        del_puerto = vigente and self._es_del_puerto(ctx, s)
        revisable  = ctx.puede_revisar and s.estado == Estado.EN_REVISION.value
        conflicto  = revisable and self._tiene_conflicto(ctx, s)
        return AccionesSolicitud(
            corregir=ctx.es_de_su_agencia(s) and s.estado == Estado.EN_CORRECCION.value and en_plazo,
            revisar=revisable and not conflicto,
            comentar=del_puerto,
            finalizar=del_puerto,
            descargar_autorizacion=(
                s.estado in (Estado.APROBADA.value, Estado.FINALIZADA.value) and self.puede_ver(ctx, s)
            ),
            conflicto_revision=conflicto,
        )

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
        STORAGE_PATH). Lo ve quien puede ver la solicitud."""
        s = await self.obtener(ctx, solicitud_id)
        documento = next((d for d in s.documentos if d.id == documento_id), None)
        if not documento:
            raise _error(status.HTTP_404_NOT_FOUND, "Documento no encontrado en esta solicitud.")
        ruta = almacenamiento.ruta_segura(documento.ruta)
        if not ruta or not ruta.is_file():
            logger.error("[solicitudes] Falta en disco el documento %s de la solicitud %s.", documento.id, s.id)
            raise _error(status.HTTP_404_NOT_FOUND, "El archivo no está disponible. Avisa al administrador.")
        return s, documento, ruta

    # ── Bandejas ─────────────────────────────────────────────────────────────

    async def _pagina(self, filtros: FiltrosBandeja, consulta: ConsultaBandeja, orden: str) -> PaginaSolicitudes:
        total, conteos, items = await self.repo.listar(
            filtros, pagina=consulta.pagina, por_pagina=consulta.por_pagina, orden=orden,
        )
        return PaginaSolicitudes(
            total=total, pagina=consulta.pagina, por_pagina=consulta.por_pagina, conteos=conteos,
            items=[self.construir_resumen(s) for s in items],
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
        return await self._pagina(self._filtros(consulta, agencia_id=ctx.agencia_id), consulta, "recientes")

    async def bandeja_revision(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Todas las solicitudes, para UCVMM. Las pendientes salen en orden de
        llegada (la más antigua primero)."""
        if not ctx.puede_revisar:
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_REVISAR}.")
        orden = "cola" if consulta.estado == Estado.EN_REVISION.value else "recientes"
        return await self._pagina(self._filtros(consulta), consulta, orden)

    async def bandeja_puerto(self, ctx: ContextoAcceso, consulta: ConsultaBandeja) -> PaginaSolicitudes:
        """Autorizaciones aprobadas de los puestos del usuario (el admin ve
        todos). Las pendientes de finalizar salen por fecha de operación."""
        if not (ctx.es_admin or ctx.es_puerto):
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_PUERTO}.")
        filtros = self._filtros(
            consulta, puestos_ids=None if ctx.es_admin else ctx.puestos_ids, solo_aprobadas_alguna_vez=True,
        )
        orden = "operacion" if consulta.estado == Estado.APROBADA.value else "recientes"
        return await self._pagina(filtros, consulta, orden)

    # ── Validación del formulario ────────────────────────────────────────────

    async def _validar_formulario(
        self, tipo: TipoTramite, datos: _DatosFormularioSolicitud,
    ) -> tuple[PuestoControl, list[_TripulanteResuelto], str | None]:
        """Valida cabecera y tripulantes. Devuelve el puesto, los tripulantes
        resueltos y el IMO normalizado."""
        faltan = self.tramites.validar_campos_cabecera(tipo, datos.model_dump())
        if faltan:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Faltan datos obligatorios del formulario: {', '.join(faltan)}.")

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
        return puesto, resueltos, imo

    @staticmethod
    def _resolver_asignaciones(
        tipo: TipoTramite, asignaciones: list[AsignacionArchivo], total_tripulantes: int,
    ) -> list[Asignacion]:
        """Traduce cada asignación a (casilla del checklist, índice del
        tripulante). Sin código de documento es un documento adicional."""
        por_codigo = {td.documento.codigo: td for td in tipo.documentos}
        resueltas: list[Asignacion] = []
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
                resueltas.append((td, None))
                continue
            indice = asignacion.indice_tripulante
            if indice is None or not 0 <= indice < total_tripulantes:
                raise _error(
                    status.HTTP_400_BAD_REQUEST,
                    f"Tripulante inválido para el documento '{td.documento.nombre}'.",
                )
            resueltas.append((td, indice))
        return resueltas

    @staticmethod
    def _limitar_adicionales(cantidad: int) -> None:
        if cantidad > MAX_DOCUMENTOS_ADICIONALES:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                f"Se admiten hasta {MAX_DOCUMENTOS_ADICIONALES} documentos adicionales por solicitud.",
            )

    def _exigir_checklist(
        self, tipo: TipoTramite, tripulantes: list[_TripulanteResuelto], cubiertas: set[tuple[int, int | None]],
    ) -> list[CasillaChecklist]:
        """400 si falta un documento exigible; si no, las casillas exigidas (la foto que se guarda)."""
        resultado = self.tramites.evaluar(tipo, [t.para_checklist() for t in tripulantes], cubiertas)
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
        puesto: PuestoControl, imo: str | None, cantidad_tripulantes: int,
    ) -> None:
        """Copia la cabecera del formulario. Los campos que el trámite no usa
        se guardan vacíos aunque lleguen con valor (restos de otro trámite
        que la agencia eligió antes en el formulario)."""
        s.puesto_control_id    = puesto.id
        s.puesto_nombre        = puesto.nombre
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
        orm.ocupacion        = e.ocupacion
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

        puesto, tripulantes, imo = await self._validar_formulario(tipo, datos)

        if len(datos.asignaciones) != len(archivos):
            raise _error(status.HTTP_400_BAD_REQUEST, "Cada archivo debe indicar a qué documento corresponde.")
        asignadas = self._resolver_asignaciones(tipo, datos.asignaciones, len(tripulantes))
        self._limitar_adicionales(sum(1 for td, _ in asignadas if td is None))
        requeridas = self._exigir_checklist(
            tipo, tripulantes, {(td.documento_id, indice) for td, indice in asignadas if td is not None},
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
            self._aplicar_cabecera(s, tipo, datos, puesto, imo, len(tripulantes))
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
            for archivo, (td, indice) in zip(guardados, asignadas):
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
        puesto, tripulantes, imo = await self._validar_formulario(tipo, datos)

        # ── Tripulantes que se conservan / quitan ──
        existentes = {t.id: t for t in s.tripulantes}
        ids = [t.entrada.id for t in tripulantes if t.entrada.id is not None]
        if len(ids) != len(set(ids)) or any(i not in existentes for i in ids):
            raise _error(status.HTTP_400_BAD_REQUEST, "La lista de tripulantes no coincide con la solicitud.")
        quitados = set(existentes) - set(ids)

        # ── Documentos que se conservan (los de un tripulante quitado se van con él) ──
        documentos_por_id = {d.id: d for d in s.documentos}
        pedidos = set(datos.documentos_conservados)
        if pedidos - set(documentos_por_id):
            raise _error(status.HTTP_400_BAD_REQUEST, "Alguno de los documentos a conservar no pertenece a la solicitud.")
        conservados = {did for did in pedidos if documentos_por_id[did].tripulante_id not in quitados}

        if len(datos.asignaciones) != len(archivos):
            raise _error(status.HTTP_400_BAD_REQUEST, "Cada archivo debe indicar a qué documento corresponde.")
        asignadas = self._resolver_asignaciones(tipo, datos.asignaciones, len(tripulantes))
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
        requeridas = self._exigir_checklist(tipo, tripulantes, cubiertas)

        carpeta = almacenamiento.carpeta_solicitud(s.id)
        nuevos = await almacenamiento.guardar_archivos(carpeta, archivos)
        retirados = [d for d in s.documentos if d.id not in conservados]
        rutas_retiradas = [d.ruta for d in retirados]
        try:
            for documento in retirados:
                s.documentos.remove(documento)
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

            for archivo, (td, indice) in zip(nuevos, asignadas):
                tripulante_id = tripulantes_orm[indice].id if indice is not None else None
                self.repo.agregar_registro(self._documento(s, archivo, carpeta, td, tripulante_id, ctx.usuario))
            self._registrar_casillas(s, requeridas, tripulantes_orm)

            anterior = s.estado
            self._aplicar_cabecera(s, tipo, datos, puesto, imo, len(tripulantes))
            s.estado           = Estado.EN_REVISION.value
            s.enviada_en       = ahora_utc()
            s.plazo_correccion = None
            s.impedimentos_verificados        = False
            s.comentario_impedimentos         = None
            s.impedimentos_verificados_en     = None
            s.impedimentos_verificados_por_id = None
            for t in s.tripulantes:   # la tripulación pudo cambiar: se verifica de nuevo
                t.con_impedimento = None

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

        # Los documentos retirados se borran del disco cuando la corrección
        # quede confirmada en la BD: si el commit fallara, siguen ahí.
        def borrar_retirados() -> None:
            for ruta in rutas_retiradas:
                almacenamiento.borrar_archivo(ruta)
        al_confirmar(self.sesion, borrar_retirados)
        return await self._recargar(s.id)

    # ── UCVMM: revisión ──────────────────────────────────────────────────────

    async def _para_revision(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        if not ctx.puede_revisar:
            raise _error(status.HTTP_403_FORBIDDEN, f"No tienes el permiso requerido: {PERMISO_REVISAR}.")
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
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
        por_id = {t.id: t for t in s.tripulantes}
        recibidos = {d.tripulante_id: d.con_impedimento for d in datos.tripulantes}
        if len(recibidos) != len(datos.tripulantes) or set(recibidos) != set(por_id):
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "Indica el resultado de la verificación de cada tripulante de la solicitud (una vez cada uno).",
            )

        correccion = s.impedimentos_verificados
        cambios = [
            f"{por_id[i].nombre_completo} pasa de {_resultado(por_id[i].con_impedimento)} a {_resultado(c)}"
            for i, c in recibidos.items() if por_id[i].con_impedimento != c
        ]
        cambia_comentario = datos.comentario != s.comentario_impedimentos
        if correccion:
            if not cambios and not cambia_comentario:
                raise _error(status.HTTP_409_CONFLICT, "La verificación de impedimentos no tiene cambios.")
            if len(datos.motivo_correccion or "") < 5:
                raise _error(status.HTTP_400_BAD_REQUEST, "Indica el motivo de la corrección (al menos 5 caracteres).")

        for tripulante_id, con_impedimento in recibidos.items():
            por_id[tripulante_id].con_impedimento = con_impedimento
        con = [por_id[i].nombre_completo for i, c in recibidos.items() if c]

        s.impedimentos_verificados        = True
        s.comentario_impedimentos         = datos.comentario
        s.impedimentos_verificados_en     = ahora_utc()
        s.impedimentos_verificados_por_id = ctx.usuario.id
        if correccion:
            partes = ["; ".join(cambios) + "." if cambios else "Se actualiza el comentario."]
            if cambia_comentario and datos.comentario:
                partes.append(f"Comentario: {_con_punto(datos.comentario)}")
            partes.append(f"Motivo: {_con_punto(datos.motivo_correccion or '')}")
            texto = " ".join(partes)
            tipo = TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS
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
            tipo = TipoEventoSolicitud.IMPEDIMENTOS
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
        s.aprobada_en            = ahora_utc()
        s.aprobada_por_id        = ctx.usuario.id
        s.observacion_aprobacion = observacion
        s.vigente_hasta          = fin_del_dia(limite)
        s.codigo_verificacion    = secrets.token_urlsafe(24)
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.APROBADA, anterior, s.estado, observacion)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def devolver(self, ctx: ContextoAcceso, solicitud_id: int, motivo: str) -> Solicitud:
        s = await self._para_revision(ctx, solicitud_id)
        anterior = s.estado
        s.estado            = Estado.EN_CORRECCION.value
        s.motivo_devolucion = motivo
        s.plazo_correccion  = ahora_utc() + timedelta(days=configuracion.PLAZO_CORRECCION_DIAS)
        s.veces_devuelta    = (s.veces_devuelta or 0) + 1
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.DEVUELTA, anterior, s.estado, motivo)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def negar(self, ctx: ContextoAcceso, solicitud_id: int, motivo: str) -> Solicitud:
        s = await self._para_revision(ctx, solicitud_id)
        anterior = s.estado
        s.estado          = Estado.NEGADA.value
        s.negada_en       = ahora_utc()
        s.negada_por_id   = ctx.usuario.id
        s.motivo_negacion = motivo
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.NEGADA, anterior, s.estado, motivo)
        await self.repo.guardar()
        return await self._recargar(s.id)

    # ── Puesto de control: comentar y finalizar ──────────────────────────────

    async def _para_puerto(self, ctx: ContextoAcceso, solicitud_id: int) -> Solicitud:
        s = await self.obtener(ctx, solicitud_id, bloquear=True)
        if not self._es_del_puerto(ctx, s):
            raise _error(status.HTTP_403_FORBIDDEN, "La solicitud no corresponde a tus puestos de control.")
        if s.estado != Estado.APROBADA.value:
            raise _error(status.HTTP_409_CONFLICT, "La autorización no está aprobada pendiente de finalizar.")
        if s.vigente_hasta and s.vigente_hasta < ahora_utc():
            raise _error(status.HTTP_409_CONFLICT, "La autorización venció sin finalizarse.")
        return s

    async def comentar(self, ctx: ContextoAcceso, solicitud_id: int, comentario: str) -> Solicitud:
        s = await self._para_puerto(ctx, solicitud_id)
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.COMENTARIO, None, None, comentario)
        await self.repo.guardar()
        return await self._recargar(s.id)

    async def finalizar(
        self, ctx: ContextoAcceso, solicitud_id: int, comentario: str, puesto_finalizacion_id: int | None = None,
    ) -> Solicitud:
        """Cierra la autorización. La operación puede terminar en otro puesto
        que el autorizado: se registra dónde terminó (por defecto, el autorizado)."""
        s = await self._para_puerto(ctx, solicitud_id)
        puesto = await self.repo_catalogos.buscar_puesto(puesto_finalizacion_id or s.puesto_control_id)
        if not puesto or not puesto.activo:
            raise _error(status.HTTP_400_BAD_REQUEST, "El puesto de control donde finalizó la operación no existe o está inactivo.")
        anterior = s.estado
        s.estado                     = Estado.FINALIZADA.value
        s.finalizada_en              = ahora_utc()
        s.finalizada_por_id          = ctx.usuario.id
        s.comentario_finalizacion    = comentario
        s.puesto_finalizacion_id     = puesto.id
        s.puesto_finalizacion_nombre = puesto.nombre
        self._registrar_evento(s, ctx.usuario, TipoEventoSolicitud.FINALIZADA, anterior, s.estado,
                               f"Finalizada en {puesto.nombre}. {comentario}")
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
                    f"{configuracion.PLAZO_CORRECCION_DIAS} día(s)."
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
    def _vencimientos_tripulante(t: TripulanteSolicitud, referencia: date) -> tuple[bool, bool]:
        """(pasaporte vencido, seamanbook vencido) a la fecha de la operación."""
        pasaporte = t.pasaporte_expira < referencia
        libreta   = bool(t.porta_libreta and t.libreta_expira and t.libreta_expira < referencia)
        return pasaporte, libreta

    def construir_resumen(self, s: Solicitud) -> SalidaSolicitudResumen:
        return SalidaSolicitudResumen(**self._campos_resumen(s))

    def _campos_resumen(self, s: Solicitud) -> dict:
        con_alerta = sum(
            1 for t in s.tripulantes if any(self._vencimientos_tripulante(t, s.fecha_operacion))
        )
        return dict(
            id=s.id, numero=s.numero, titulo=s.titulo, estado=s.estado,
            tipo_tramite_codigo=s.tipo_tramite.codigo, tipo_tramite_nombre=s.tipo_tramite.nombre,
            agencia_id=s.agencia_id, agencia_nombre=s.agencia_nombre, puesto_nombre=s.puesto_nombre,
            nombre_buque=s.nombre_buque, imo=s.imo, fecha_operacion=s.fecha_operacion,
            cantidad_tripulantes=s.cantidad_tripulantes,
            creada_por=s.creada_por.full_name if s.creada_por else None,
            created_at=s.created_at, enviada_en=s.enviada_en,
            plazo_correccion=s.plazo_correccion, vigente_hasta=s.vigente_hasta,
            aprobada_en=s.aprobada_en, negada_en=s.negada_en,
            finalizada_en=s.finalizada_en, expirada_en=s.expirada_en,
            veces_devuelta=s.veces_devuelta or 0,
            tripulantes_con_alerta=con_alerta,
            tiene_nacionalidad_restringida=(
                s.tipo_tramite.aviso_custodia and any(t.nacionalidad_restringida for t in s.tripulantes)
            ),
        )

    @staticmethod
    def _autor_ultimo(s: Solicitud, *tipos: TipoEventoSolicitud) -> str | None:
        valores = {t.value for t in tipos}
        return next((e.usuario_nombre for e in reversed(s.eventos) if e.tipo in valores), None)

    @staticmethod
    def _evento_para(e, interno: bool) -> SalidaEvento | None:
        """Un evento del historial tal como lo ve quien consulta. La agencia no ve
        lo interno del SNM (impedimentos, comentarios del puesto, la observación
        de aprobación ni el texto de cierre) ni el nombre del funcionario: ve los
        estados y los motivos que le corresponden (devolución y negación)."""
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

        tripulantes = []
        for t in s.tripulantes:
            pasaporte_vencido, libreta_vencida = self._vencimientos_tripulante(t, s.fecha_operacion)
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
                con_impedimento=t.con_impedimento if ctx.es_personal_snm else None,
                porta_libreta=t.porta_libreta, orden=t.orden,
                pasaporte_vencido=pasaporte_vencido, libreta_vencida=libreta_vencida,
            ))

        documentos = [
            SalidaDocumentoSolicitud(
                id=d.id, nombre_original=d.nombre_original, tamano=d.tamano, tipo_mime=d.tipo_mime,
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
                tripulante_id=c.tripulante_id, tripulante_nombre=nombres.get(c.tripulante_id),
                documento_ids=ids, cubierta=bool(ids),
            ))

        interno = ctx.es_personal_snm
        eventos = [ev for ev in (self._evento_para(e, interno) for e in s.eventos) if ev is not None]

        return SalidaSolicitud(
            **self._campos_resumen(s),
            tipo_tramite_nota=tipo.nota,
            tipo_tramite_aviso_custodia=tipo.aviso_custodia,
            requiere_buque=tipo.requiere_buque, requiere_puerto=tipo.requiere_puerto,
            requiere_puerto_desembarque=tipo.requiere_puerto_desembarque,
            requiere_motivo=tipo.requiere_motivo, requiere_clinica=tipo.requiere_clinica,
            valida_vigencia=tipo.valida_vigencia,
            puesto_control_id=s.puesto_control_id,
            bandera=s.bandera, bandera_nombre=await self._nombre_pais(s.bandera),
            nombre_puerto=s.nombre_puerto, puerto_desembarque=s.puerto_desembarque,
            motivo=s.motivo, clinica_hospital=s.clinica_hospital, observaciones=s.observaciones,
            impedimentos_verificados=s.impedimentos_verificados if interno else False,
            comentario_impedimentos=s.comentario_impedimentos if interno else None,
            impedimentos_verificados_en=s.impedimentos_verificados_en if interno else None,
            impedimentos_verificados_por=self._autor_ultimo(
                s, TipoEventoSolicitud.IMPEDIMENTOS, TipoEventoSolicitud.IMPEDIMENTOS_CORREGIDOS,
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
        )

    # ── Autorización (PDF) y verificación pública ────────────────────────────

    @staticmethod
    def url_verificacion(codigo: str) -> str:
        return f"{configuracion.app_base_url}/verificar/{codigo}"

    async def preparar_pdf(self, ctx: ContextoAcceso, s: Solicitud) -> DatosPdfAutorizacion:
        if not self.acciones(ctx, s).descargar_autorizacion or not s.codigo_verificacion:
            raise _error(status.HTTP_409_CONFLICT, "La autorización solo se descarga cuando la solicitud está aprobada o finalizada.")
        assert s.aprobada_en is not None
        return DatosPdfAutorizacion(
            numero=s.numero or str(s.id),
            estado=s.estado,
            tipo_tramite=s.tipo_tramite.nombre,
            nota_tramite=s.tipo_tramite.nota,
            aviso_custodia=s.tipo_tramite.aviso_custodia,
            agencia_naviera=s.agencia_nombre,
            nombre_buque=s.nombre_buque, imo=s.imo, bandera=await self._nombre_pais(s.bandera),
            puesto_control=s.puesto_nombre, fecha_operacion=s.fecha_operacion,
            nombre_puerto=s.nombre_puerto, puerto_desembarque=s.puerto_desembarque,
            clinica_hospital=s.clinica_hospital, motivo=s.motivo,
            fecha_solicitud=s.enviada_en.astimezone(TZ_PANAMA),
            aprobada_en=s.aprobada_en.astimezone(TZ_PANAMA),
            # El PDF lo recibe la agencia: como en su vista del expediente, no lleva
            # nombres de funcionarios (decisión del usuario, 2026-10-15).
            aprobada_por="UCVMM",
            vigente_hasta=s.vigente_hasta.astimezone(TZ_PANAMA) if s.vigente_hasta else None,
            finalizada_en=s.finalizada_en.astimezone(TZ_PANAMA) if s.finalizada_en else None,
            puesto_finalizacion=s.puesto_finalizacion_nombre,
            url_verificacion=self.url_verificacion(s.codigo_verificacion),
            codigo_verificacion=s.codigo_verificacion,
            tripulantes=[
                TripulantePdf(
                    nombre=t.nombre, apellido=t.apellido,
                    nacionalidad=t.nacionalidad_ref.nombre if t.nacionalidad_ref else t.nacionalidad,
                    pasaporte=t.pasaporte, libreta=t.libreta_marino or "",
                    rango=t.rango, ocupacion=t.ocupacion,
                    restringida=t.nacionalidad_restringida,
                )
                for t in s.tripulantes
            ],
        )

    async def verificar(self, codigo: str) -> SalidaVerificacion:
        s = await self.repo.buscar_por_codigo_verificacion(codigo)
        if not s:
            raise _error(status.HTTP_404_NOT_FOUND, "El código no corresponde a ninguna autorización emitida.")
        ahora = ahora_utc()
        vigente = s.estado == Estado.FINALIZADA.value or (
            s.estado == Estado.APROBADA.value and (s.vigente_hasta is None or s.vigente_hasta >= ahora)
        )

        def enmascarar(pasaporte: str) -> str:
            return "•" * max(len(pasaporte) - 4, 0) + pasaporte[-4:]

        return SalidaVerificacion(
            valida=vigente, estado=s.estado, numero=s.numero,
            tipo_tramite=s.tipo_tramite.nombre,
            agencia_nombre=s.agencia_nombre,
            nombre_buque=s.nombre_buque, imo=s.imo, bandera=await self._nombre_pais(s.bandera),
            puesto_nombre=s.puesto_nombre, fecha_operacion=s.fecha_operacion,
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

    async def estadisticas(self, desde: date | None, hasta: date | None) -> SalidaEstadisticasSolicitudes:
        hitos = await self.repo.contar_hitos(desde, hasta)

        # Últimos 6 meses, incluido el actual
        hoy = hoy_panama()
        anio, mes = hoy.year, hoy.month
        meses: list[str] = []
        for _ in range(6):
            meses.append(f"{anio:04d}-{mes:02d}")
            mes -= 1
            if mes == 0:
                anio, mes = anio - 1, 12
        meses.reverse()
        serie = await self.repo.serie_mensual(date(int(meses[0][:4]), int(meses[0][5:]), 1), desde, hasta)

        return SalidaEstadisticasSolicitudes(
            recibidas=int(hitos["recibidas"] or 0),
            por_estado=await self.repo.contar_por_estado(desde, hasta),
            aprobadas=int(hitos["aprobadas"] or 0),
            negadas=int(hitos["negadas"] or 0),
            expiradas=int(hitos["expiradas"] or 0),
            finalizadas=int(hitos["finalizadas"] or 0),
            horas_promedio_resolucion=(
                round(float(hitos["horas"]), 1) if hitos["horas"] is not None else None
            ),
            por_tipo=[
                FilaEstadisticaTipo(
                    codigo=f.codigo, nombre=f.nombre,
                    recibidas=f.recibidas, aprobadas=f.aprobadas, negadas=f.negadas, expiradas=f.expiradas,
                )
                for f in await self.repo.contar_por_tipo(desde, hasta)
            ],
            por_mes=[
                FilaEstadisticaMes(
                    mes=m,
                    recibidas=serie.get(m, {}).get("recibidas", 0),
                    aprobadas=serie.get(m, {}).get("aprobadas", 0),
                    negadas=serie.get(m, {}).get("negadas", 0),
                    expiradas=serie.get(m, {}).get("expiradas", 0),
                )
                for m in meses
            ],
            por_puesto=[
                FilaEstadisticaPuesto(puesto=f.nombre, aprobadas=f.aprobadas, finalizadas=f.finalizadas, expiradas=f.expiradas)
                for f in await self.repo.contar_por_puesto(desde, hasta)
            ],
        )
