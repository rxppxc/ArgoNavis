"""Acceso a BD del expediente de las solicitudes: bandejas paginadas por
alcance (agencia, revisión, puesto), bloqueo de fila para las transiciones,
vencimientos, estadísticas y las novedades de las notificaciones internas."""
import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import (
    ARRAY, Integer, Interval, Select, Time, and_, any_, case, cast, extract, false, func, literal, literal_column, or_,
    select, update,
)
from sqlalchemy.dialects.postgresql import insert as insertar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.horario import FIN_LABORAL, INICIO_LABORAL, ZONA_PANAMA, entre_fechas_panama
from app.domain.models.boleta import BoletaRecargo
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.models.solicitud import (
    MESES_VIGENCIA_PASAPORTE, RANGOS_CON_LIBRETA, CasillaSolicitud, DocumentoEmitido, DocumentoSolicitud,
    EstadoSolicitud, EventoSolicitud, Solicitud, TipoEmitido, TipoEventoSolicitud, TripulanteSolicitud, VersionSolicitud,
)
from app.domain.models.tramite import TipoTramite
from app.domain.models.user import Usuario

_ZONA = ZONA_PANAMA.key   # el nombre, para timezone() de PostgreSQL

# Qué autorización se emite en cada estado (2026-11-22): en los demás, ninguna.
EMITIDO_POR_ESTADO = {
    EstadoSolicitud.APROBADA.value: TipoEmitido.APROBADA.value,
    EstadoSolicitud.FINALIZADA.value: TipoEmitido.FINALIZADA.value,
}


@dataclass(frozen=True)
class AlcanceSectores:
    """Las solicitudes de unos sectores (UCVMM y la supervisión de sector): las que
    revisó alguno de ellos y, mientras nadie las ha revisado, las de sus puestos de hoy
    (2026-11-22). Es `Solicitud.sector_id` en SQL: si cambias uno, cambia el otro."""
    sectores: frozenset[int] = frozenset()
    puestos:  frozenset[int] = frozenset()   # los de esos sectores, hoy

    def condicion(self):
        # Sin sectores no ve nada (IN de una lista vacía no es válido en SQL).
        return or_(
            Solicitud.sector_revision_id.in_(sorted(self.sectores) or [-1]),
            and_(Solicitud.sector_revision_id.is_(None),
                 Solicitud.puesto_control_id.in_(sorted(self.puestos) or [-1])),
        )


@dataclass(frozen=True)
class AlcanceSnm:
    """Lo que ve el personal del SNM fuera de sus bandejas (la consulta histórica,
    2026-11-11): lo mismo que ServicioSolicitud.puede_ver, sin la vía de la agencia."""
    sectores:          AlcanceSectores | None = None   # UCVMM y supervisión de sector
    # Desde que se aprueban, las que finalizan esos puestos (con cambio de puerto, el nuevo).
    puestos_aprobadas: frozenset[int] = frozenset()
    # Las de los trámites que ve el supervisor general (2026-11-16), de cualquier puesto.
    supervision_general: bool = False

    def condicion(self):
        caminos = []
        if self.sectores is not None:
            caminos.append(self.sectores.condicion())
        if self.puestos_aprobadas:
            caminos.append(and_(puesto_autorizado().in_(sorted(self.puestos_aprobadas)),
                                Solicitud.aprobada_en.isnot(None)))
        if self.supervision_general:
            caminos.append(Solicitud.tipo_tramite_id.in_(
                select(TipoTramite.id).where(TipoTramite.supervision_general.is_(True))))
        return or_(*caminos) if caminos else false()


def puesto_autorizado():
    """Solicitud.puesto_autorizado_id en SQL: el puesto que la finaliza (con cambio
    de puerto, el nuevo)."""
    return func.coalesce(Solicitud.puesto_destino_id, Solicitud.puesto_control_id)


@dataclass
class FiltrosBandeja:
    """Alcance (quién ve qué) + filtros de la bandeja."""
    agencia_id:  int | None = None        # bandeja de la agencia (y filtro de la consulta histórica)
    sectores:    AlcanceSectores | None = None   # las de los sectores de UCVMM (None = todos)
    # Por el puesto que la finaliza (la bandeja y la campana del puesto; None = todos).
    puestos_autorizados: set[int] | None = None
    solo_aprobadas_alguna_vez: bool = False
    estado:      str | None = None
    texto:       str | None = None
    desde:       date | None = None
    hasta:       date | None = None
    # Consulta histórica (2026-11-11)
    alcance_snm:      AlcanceSnm | None = None
    puesto_id:        int | None = None
    tipo_tramite_id:  int | None = None
    pasajero:         str | None = None   # nombre, apellido, pasaporte o seamanbook de un tripulante
    autorizadas:      bool = False        # solo las que se aprobaron alguna vez (una pestaña, 2026-11-22)
    fuera_de_horario: bool = False        # solo las aprobadas fuera del horario
    fecha_por:        str = "envio"       # a qué fecha van desde y hasta: "envio" | "operacion"


@dataclass(frozen=True)
class PaginaBandeja:
    """Una página de una bandeja. `total`, con todos los filtros; las cantidades de las
    pestañas (por estado y las autorizadas), sin el de la pestaña elegida."""
    total:       int
    conteos:     dict[str, int]
    autorizadas: int
    solicitudes: list[Solicitud]


def _fecha_panama(columna):
    return func.date(func.timezone(_ZONA, columna))


def _fuera_de_horario(columna):
    """core.horario.fuera_de_horario en SQL (tienen que coincidir): sábado,
    domingo, antes de las 07:00 o desde las 15:01, en hora de Panamá. Al minuto:
    las 15:00 (hasta las 15:00:59) todavía son laborales."""
    local = func.timezone(_ZONA, columna)
    minuto = cast(func.date_trunc("minute", local), Time)
    return or_(extract("isodow", local) >= 6, minuto < INICIO_LABORAL, minuto > FIN_LABORAL)


def _contar_fuera_de_horario(columna):
    return func.count(case((_fuera_de_horario(columna), columna)))


def _plano(valor):
    """Sin tildes y en minúsculas: el cálculo de las columnas `busqueda` (revisión
    c6e2a9f1d438), aplicado a lo que se busca."""
    sin_tildes = func.regexp_replace(func.normalize(valor, literal_column("NFD")), r"[\u0300-\u036f]", "", "g")
    return func.lower(sin_tildes)


def _contiene(columna, buscado: str) -> list:
    """Todas las palabras de lo escrito, en cualquier orden y en cualquier parte del
    texto, sin distinguir tildes ni mayúsculas (2026-11-22). «%» y «_» van tal cual."""
    condiciones = []
    for palabra in re.split(r"[\s,;]+", buscado):
        if palabra:
            escapada = re.sub(r"([/%_])", r"/\1", palabra)
            condiciones.append(columna.like(literal("%") + _plano(escapada) + literal("%"), escape="/"))
    return condiciones


class RepositorioSolicitud:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    # ── Lectura de un expediente ─────────────────────────────────────────────

    async def buscar_por_id(
        self, solicitud_id: int, *, refrescar: bool = False, bloquear: bool = False,
    ) -> Solicitud | None:
        """Expediente completo.

        - `bloquear`: SELECT ... FOR UPDATE sobre la solicitud, para que dos
          transiciones simultáneas (p. ej. aprobar y negar) no se pisen: la
          segunda espera y vuelve a leer el estado ya cambiado.
        - `refrescar`: relee todo de la BD aunque el objeto ya esté en sesión.
        """
        consulta = (
            select(Solicitud)
            .options(
                selectinload(Solicitud.documentos),
                selectinload(Solicitud.tripulantes),
                selectinload(Solicitud.eventos),
                selectinload(Solicitud.casillas),
                selectinload(Solicitud.boletas),
            )
            .where(Solicitud.id == solicitud_id)
        )
        if bloquear:
            consulta = consulta.with_for_update(of=Solicitud)
        if refrescar or bloquear:
            consulta = consulta.execution_options(populate_existing=True)
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    async def buscar_por_codigo_verificacion(self, codigo: str) -> Solicitud | None:
        consulta = (
            select(Solicitud)
            .options(selectinload(Solicitud.tripulantes))
            .where(Solicitud.codigo_verificacion == codigo)
        )
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    # ── Bandejas ─────────────────────────────────────────────────────────────

    @staticmethod
    def _condiciones(filtros: FiltrosBandeja, *, con_pestana: bool) -> list:
        """`con_pestana`: también la pestaña elegida (un estado o las autorizadas)."""
        condiciones = []
        if filtros.agencia_id is not None:
            condiciones.append(Solicitud.agencia_id == filtros.agencia_id)
        if filtros.sectores is not None:
            condiciones.append(filtros.sectores.condicion())
        if filtros.puestos_autorizados is not None:
            # Sin puestos asignados no ve nada (IN de una lista vacía no es válido en SQL).
            condiciones.append(puesto_autorizado().in_(sorted(filtros.puestos_autorizados) or [-1]))
        if filtros.solo_aprobadas_alguna_vez:
            condiciones.append(Solicitud.aprobada_en.isnot(None))
        if filtros.alcance_snm is not None:
            condiciones.append(filtros.alcance_snm.condicion())
        if filtros.puesto_id is not None:
            # El elegido o el nuevo de un cambio de puerto.
            condiciones.append(or_(Solicitud.puesto_control_id == filtros.puesto_id,
                                   Solicitud.puesto_destino_id == filtros.puesto_id))
        if filtros.tipo_tramite_id is not None:
            condiciones.append(Solicitud.tipo_tramite_id == filtros.tipo_tramite_id)
        if filtros.pasajero:
            # Alguno de sus tripulantes tiene todas las palabras.
            t = TripulanteSolicitud
            condiciones.append(select(t.id).where(
                t.solicitud_id == Solicitud.id, *_contiene(t.busqueda, filtros.pasajero),
            ).exists())
        if filtros.fuera_de_horario:
            condiciones.append(and_(Solicitud.aprobada_en.isnot(None), _fuera_de_horario(Solicitud.aprobada_en)))
        if filtros.texto:
            condiciones += _contiene(Solicitud.busqueda, filtros.texto)
        if filtros.fecha_por == "operacion":   # la fecha de la operación ya es un día de Panamá
            if filtros.desde:
                condiciones.append(Solicitud.fecha_operacion >= filtros.desde)
            if filtros.hasta:
                condiciones.append(Solicitud.fecha_operacion <= filtros.hasta)
        else:
            condiciones += entre_fechas_panama(Solicitud.enviada_en, filtros.desde, filtros.hasta)
        if con_pestana and filtros.estado:
            condiciones.append(Solicitud.estado == filtros.estado)
        if con_pestana and filtros.autorizadas:
            condiciones.append(Solicitud.aprobada_en.isnot(None))
        return condiciones

    async def pendiente_en(self, filtros: FiltrosBandeja, estado: str) -> tuple[int, datetime | None]:
        """Cuántas hay en ese estado dentro del alcance y el plazo más próximo de
        ellas (el de corrección, las devueltas; el de finalización, las aprobadas).
        Una sola consulta: la campana la hace cada minuto por pestaña abierta, y
        antes eran dos (un conteo de todos los estados y el mínimo aparte)."""
        columna = Solicitud.plazo_correccion if estado == EstadoSolicitud.EN_CORRECCION.value else Solicitud.vigente_hasta
        cantidad, vence = (await self.sesion.execute(
            select(func.count(), func.min(columna))
            .where(*self._condiciones(filtros, con_pestana=False), Solicitud.estado == estado)
        )).one()
        return int(cantidad or 0), vence

    async def listar(
        self, filtros: FiltrosBandeja, *, pagina: int, por_pagina: int, orden: str = "recientes",
    ) -> PaginaBandeja:
        """Una página y las cantidades de sus pestañas. Sin los tripulantes: lo que la
        bandeja muestra de ellos sale de `alertas_de`."""
        # Una sola cuenta: de ella sale también el total de la pestaña elegida.
        filas = (await self.sesion.execute(
            select(Solicitud.estado, func.count().label("total"), func.count(Solicitud.aprobada_en).label("autorizadas"))
            .where(*self._condiciones(filtros, con_pestana=False))
            .group_by(Solicitud.estado)
        )).all()
        consulta: Select = (
            select(Solicitud)
            .where(*self._condiciones(filtros, con_pestana=True))
            .order_by(*self._orden(orden))
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        return PaginaBandeja(
            total=sum(f.autorizadas if filtros.autorizadas else f.total
                      for f in filas if filtros.estado in (None, f.estado)),
            conteos={f.estado: f.total for f in filas},
            autorizadas=sum(f.autorizadas for f in filas),
            solicitudes=list((await self.sesion.execute(consulta)).scalars().all()),
        )

    async def tripulantes_encontrados(self, ids: list[int], buscado: str) -> dict[int, list[tuple[str, str]]]:
        """Por solicitud, los tripulantes que coinciden con lo buscado: (nombre, pasaporte)."""
        if not ids:
            return {}
        t = TripulanteSolicitud
        consulta = (
            select(t.solicitud_id, t.nombre, t.apellido, t.pasaporte)
            .where(t.solicitud_id.in_(ids), *_contiene(t.busqueda, buscado))
            .order_by(t.solicitud_id, t.orden, t.id)
        )
        encontrados: dict[int, list[tuple[str, str]]] = {}
        for solicitud_id, nombre, apellido, pasaporte in (await self.sesion.execute(consulta)).all():
            encontrados.setdefault(solicitud_id, []).append((f"{nombre} {apellido}".strip(), pasaporte))
        return encontrados

    async def puestos_revisados_por(self, sectores: frozenset[int]) -> set[int]:
        """Los puestos de las solicitudes que revisaron esos sectores, aunque ya no sean suyos."""
        consulta = select(PuestoControl.id).where(select(Solicitud.id).where(
            Solicitud.puesto_control_id == PuestoControl.id,
            Solicitud.sector_revision_id.in_(sorted(sectores) or [-1]),
        ).exists())
        return set((await self.sesion.execute(consulta)).scalars().all())

    @staticmethod
    def _orden(orden: str) -> tuple:
        if orden == "cola":                  # revisión: la más antigua primero (FIFO)
            return Solicitud.enviada_en.asc(), Solicitud.id.asc()
        if orden == "operacion":             # puerto: la operación más próxima primero
            return Solicitud.fecha_operacion.asc(), Solicitud.id.asc()
        if orden == "operacion_reciente":    # consulta histórica por fecha de la operación
            return Solicitud.fecha_operacion.desc(), Solicitud.id.desc()
        return Solicitud.enviada_en.desc(), Solicitud.id.desc()

    async def para_exportar(
        self, filtros: FiltrosBandeja, *, orden: str, limite: int,
    ) -> tuple[int, list[Solicitud]]:
        """(cuántas cumplen los filtros, las primeras `limite` según el orden): la
        exportación de la consulta histórica. Sin tripulantes ni documentos."""
        condiciones = self._condiciones(filtros, con_pestana=True)
        total = (await self.sesion.execute(
            select(func.count()).select_from(Solicitud).where(*condiciones)
        )).scalar() or 0
        consulta = select(Solicitud).where(*condiciones).order_by(*self._orden(orden)).limit(limite)
        return total, list((await self.sesion.execute(consulta)).scalars().all())

    async def alertas_de(self, ids: list[int]) -> dict[int, tuple[int, bool]]:
        """Por solicitud: cuántos tripulantes tienen el seamanbook vencido a la fecha
        de la operación o el pasaporte con menos de 3 meses de vigencia desde ese
        día (o vencido), y si alguno es de nacionalidad restringida. Lo calcula la
        BD en una consulta: antes cada página de una bandeja traía a todos sus
        tripulantes (hasta 100 × 30) solo para contarlos. La regla es la de
        ServicioSolicitud._vencimientos_tripulante; la fecha + 3 meses de
        PostgreSQL da lo mismo que vigencia_minima_pasaporte (30/11 → 28/02)."""
        if not ids:
            return {}
        t = TripulanteSolicitud
        minimo_pasaporte = Solicitud.fecha_operacion + func.make_interval(0, MESES_VIGENCIA_PASAPORTE, type_=Interval)
        vencido = or_(
            t.pasaporte_expira < minimo_pasaporte,
            and_(t.rango.in_(sorted(RANGOS_CON_LIBRETA)), t.libreta_expira.isnot(None),
                 t.libreta_expira < Solicitud.fecha_operacion),
        )
        consulta = (
            select(t.solicitud_id, func.count().filter(vencido), func.bool_or(t.nacionalidad_restringida))
            .join(Solicitud, Solicitud.id == t.solicitud_id)
            .where(t.solicitud_id.in_(ids))
            .group_by(t.solicitud_id)
        )
        return {sid: (int(n or 0), bool(r)) for sid, n, r in (await self.sesion.execute(consulta)).all()}

    async def listar_vencidas(self, ahora: datetime) -> list[Solicitud]:
        """Aprobadas sin finalizar y devueltas sin corregir cuyo plazo ya pasó.
        Las bloquea (SKIP LOCKED: si una está tomada por otra transacción, se
        deja para la próxima vuelta)."""
        consulta = (
            select(Solicitud)
            .options(selectinload(Solicitud.tripulantes))
            .where(or_(
                and_(Solicitud.estado == EstadoSolicitud.APROBADA.value, Solicitud.vigente_hasta < ahora),
                and_(Solicitud.estado == EstadoSolicitud.EN_CORRECCION.value, Solicitud.plazo_correccion < ahora),
            ))
            .with_for_update(of=Solicitud, skip_locked=True)
        )
        return list((await self.sesion.execute(consulta)).scalars().all())

    # ── Novedades (notificaciones internas) ──────────────────────────────────

    def _de_las_fuentes(self, fuentes: list[tuple[FiltrosBandeja, set[str]]], excluir_usuario_id: int) -> list:
        """Eventos de cualquiera de las fuentes (alcance de una bandeja + tipos de
        evento), sin los que hizo el propio usuario."""
        return [
            or_(*[and_(*self._condiciones(f, con_pestana=False), EventoSolicitud.tipo.in_(sorted(t))) for f, t in fuentes]),
            or_(EventoSolicitud.usuario_id.is_(None), EventoSolicitud.usuario_id != excluir_usuario_id),
        ]

    async def novedades(
        self, fuentes: list[tuple[FiltrosBandeja, set[str]]], *, desde: datetime, excluir_usuario_id: int, limite: int,
    ) -> list:
        """Los eventos más recientes de las fuentes, desde `desde`: (evento, número, título)."""
        if not fuentes:
            return []
        consulta = (
            select(EventoSolicitud, Solicitud.numero, Solicitud.titulo)
            .join(Solicitud, Solicitud.id == EventoSolicitud.solicitud_id)
            .where(*self._de_las_fuentes(fuentes, excluir_usuario_id), EventoSolicitud.creado_en >= desde)
            .order_by(EventoSolicitud.creado_en.desc(), EventoSolicitud.id.desc())
            .limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def contar_novedades(
        self, fuentes: list[tuple[FiltrosBandeja, set[str]]], *, despues_de: datetime, excluir_usuario_id: int,
    ) -> int:
        if not fuentes:
            return 0
        consulta = (
            select(func.count())
            .select_from(EventoSolicitud)
            .join(Solicitud, Solicitud.id == EventoSolicitud.solicitud_id)
            .where(*self._de_las_fuentes(fuentes, excluir_usuario_id), EventoSolicitud.creado_en > despues_de)
        )
        return (await self.sesion.execute(consulta)).scalar() or 0

    # ── Escritura ────────────────────────────────────────────────────────────

    async def agregar(self, solicitud: Solicitud) -> None:
        self.sesion.add(solicitud)
        await self.sesion.flush()

    def agregar_registro(
        self, registro: EventoSolicitud | DocumentoSolicitud | CasillaSolicitud | VersionSolicitud | BoletaRecargo,
    ) -> None:
        """Agrega un evento, un documento, una casilla… por su `solicitud_id`,
        sin pasar por las colecciones de la solicitud (que se recargan después)."""
        self.sesion.add(registro)

    async def guardar(self) -> None:
        await self.sesion.flush()

    async def boleta_con_numero(self, numero_oficio: str) -> BoletaRecargo | None:
        """La boleta con ese número de oficio, sin distinguir mayúsculas (como el
        índice único), anulada o no."""
        consulta = select(BoletaRecargo).where(func.lower(BoletaRecargo.numero_oficio) == numero_oficio.lower())
        return (await self.sesion.execute(consulta)).scalar_one_or_none()

    # ── Historial completo (2026-11-22) ──────────────────────────────────────

    async def versiones(self, solicitud_id: int) -> list[VersionSolicitud]:
        """Lo que se había enviado antes de cada corrección, de la primera a la última."""
        consulta = (select(VersionSolicitud).where(VersionSolicitud.solicitud_id == solicitud_id)
                    .order_by(VersionSolicitud.numero))
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def archivos(self, solicitud_id: int) -> list[tuple[DocumentoSolicitud, str | None]]:
        """Todos sus documentos, vigentes y retirados, con quién los subió."""
        consulta = (
            select(DocumentoSolicitud, Usuario)
            .outerjoin(Usuario, Usuario.id == DocumentoSolicitud.subido_por_id)
            .options(selectinload(DocumentoSolicitud.tripulante))
            .where(DocumentoSolicitud.solicitud_id == solicitud_id)
            .order_by(DocumentoSolicitud.id)
        )
        return [(d, u.full_name if u else None) for d, u in (await self.sesion.execute(consulta)).all()]

    async def documento_retirado(self, solicitud_id: int, documento_id: int) -> DocumentoSolicitud | None:
        return (await self.sesion.execute(select(DocumentoSolicitud).where(
            DocumentoSolicitud.id == documento_id, DocumentoSolicitud.solicitud_id == solicitud_id,
            DocumentoSolicitud.retirado_en.isnot(None),
        ))).scalar_one_or_none()

    async def emitidos(self, solicitud_id: int) -> list[DocumentoEmitido]:
        consulta = (select(DocumentoEmitido).where(DocumentoEmitido.solicitud_id == solicitud_id)
                    .order_by(DocumentoEmitido.emitido_en, DocumentoEmitido.id))
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def emitido(self, solicitud_id: int, tipo: str) -> DocumentoEmitido | None:
        return (await self.sesion.execute(select(DocumentoEmitido).where(
            DocumentoEmitido.solicitud_id == solicitud_id, DocumentoEmitido.tipo == tipo,
        ))).scalar_one_or_none()

    async def agregar_emitido(self, **valores) -> bool:
        """False si ya había una: otro proceso la emitió a la vez."""
        consulta = (insertar(DocumentoEmitido).values(**valores)
                    .on_conflict_do_nothing(constraint="uq_documentos_emitidos_tipo").returning(DocumentoEmitido.id))
        return (await self.sesion.execute(consulta)).scalar_one_or_none() is not None

    async def sin_emitir(self, limite: int) -> list[int]:
        """Las aprobadas y finalizadas a las que les falta la autorización de su estado."""
        faltan = [
            and_(Solicitud.estado == estado, ~select(DocumentoEmitido.id).where(
                DocumentoEmitido.solicitud_id == Solicitud.id, DocumentoEmitido.tipo == tipo).exists())
            for estado, tipo in EMITIDO_POR_ESTADO.items()
        ]
        consulta = (
            select(Solicitud.id)
            .where(Solicitud.codigo_verificacion.isnot(None), Solicitud.aprobada_en.isnot(None), or_(*faltan))
            .order_by(Solicitud.id).limit(limite)
        )
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def documentos_sin_huella(self, ultimo_id: int, limite: int) -> list:
        """(id, ruta) de los que siguen a `ultimo_id` y no tienen huella."""
        consulta = (select(DocumentoSolicitud.id, DocumentoSolicitud.ruta)
                    .where(DocumentoSolicitud.id > ultimo_id, DocumentoSolicitud.sha256.is_(None))
                    .order_by(DocumentoSolicitud.id).limit(limite))
        return list((await self.sesion.execute(consulta)).all())

    async def poner_huella(self, documento_id: int, sha256: str) -> None:
        await self.sesion.execute(update(DocumentoSolicitud).values(sha256=sha256).where(
            DocumentoSolicitud.id == documento_id, DocumentoSolicitud.sha256.is_(None)))

    # ── Los archivos, uno por uno (infrastructure/revisar_documentos.py) ─────
    # `modelo`: DocumentoSolicitud o DocumentoEmitido, que tienen lo mismo que mirar.

    async def archivos_desde(
        self, modelo: type[DocumentoSolicitud] | type[DocumentoEmitido], ultimo_id: int, limite: int,
    ) -> list:
        """(id, ruta, tamano, sha256) de los que siguen a `ultimo_id`, en orden."""
        consulta = (
            select(modelo.id, modelo.ruta, modelo.tamano, modelo.sha256)
            .where(modelo.id > ultimo_id).order_by(modelo.id).limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def archivos_con_su_solicitud(
        self, modelo: type[DocumentoSolicitud] | type[DocumentoEmitido], ids: list[int],
    ) -> list:
        """(id, ruta, tamano, sha256, numero, solicitud_id) de los que sigan registrados."""
        consulta = (
            select(modelo.id, modelo.ruta, modelo.tamano, modelo.sha256, Solicitud.numero, modelo.solicitud_id)
            .join(Solicitud, Solicitud.id == modelo.solicitud_id)
            .where(modelo.id == any_(literal(ids, ARRAY(Integer))))
            .order_by(modelo.id)
        )
        return list((await self.sesion.execute(consulta)).all())

    # ── Uso del sistema ──────────────────────────────────────────────────────

    async def contar_creadas_por(self, usuario_id: int) -> int:
        return (await self.sesion.execute(
            select(func.count()).select_from(Solicitud).where(Solicitud.creada_por_id == usuario_id)
        )).scalar() or 0

    async def totales_documentos(self) -> tuple[int, int]:
        """(cantidad de documentos, bytes almacenados)."""
        fila = (await self.sesion.execute(
            select(func.count(DocumentoSolicitud.id), func.coalesce(func.sum(DocumentoSolicitud.tamano), 0))
        )).one()
        return int(fila[0] or 0), int(fila[1] or 0)

    async def top_agencias(self, limite: int = 5) -> list:
        """Las agencias con más solicitudes, con su nombre de hoy. Agrupar por el
        nombre guardado en cada solicitud (la foto al enviarla) partía en dos filas
        a una agencia renombrada, con la misma agencia_id."""
        total = func.count(Solicitud.id).label("total")
        consulta = (
            select(Solicitud.agencia_id, AgenciaNaviera.nombre.label("agencia_nombre"), total)
            .join(AgenciaNaviera, AgenciaNaviera.id == Solicitud.agencia_id)
            .group_by(Solicitud.agencia_id, AgenciaNaviera.nombre)
            .order_by(total.desc(), AgenciaNaviera.nombre)
            .limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())

    # ── Estadísticas del flujo ───────────────────────────────────────────────

    @staticmethod
    def _filtro_fechas(desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None) -> list:
        """Filtra por fecha de creación (inclusive, en hora de Panamá), con el índice
        de created_at, y por los sectores visibles (None = todos)."""
        filtros = entre_fechas_panama(Solicitud.created_at, desde, hasta)
        if sectores is not None:
            filtros.append(sectores.condicion())
        return filtros

    async def contar_por_estado(
        self, desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None,
    ) -> dict[str, int]:
        consulta = (
            select(Solicitud.estado, func.count())
            .where(*self._filtro_fechas(desde, hasta, sectores))
            .group_by(Solicitud.estado)
        )
        return {estado: total for estado, total in (await self.sesion.execute(consulta)).all()}

    async def contar_hitos(
        self, desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None,
    ) -> dict[str, float | int | None]:
        """Totales por hito alcanzado (no por estado actual): una solicitud
        aprobada y luego finalizada cuenta como aprobada y como finalizada. Las
        fuera del horario, por la hora en que UCVMM aprobó."""
        horas_resolucion = func.avg(
            extract("epoch", func.coalesce(Solicitud.aprobada_en, Solicitud.negada_en) - Solicitud.created_at) / 3600
        )
        consulta = select(
            func.count().label("recibidas"),
            func.count(Solicitud.aprobada_en).label("aprobadas"),
            func.count(Solicitud.negada_en).label("negadas"),
            func.count(Solicitud.expirada_en).label("expiradas"),
            func.count(Solicitud.finalizada_en).label("finalizadas"),
            _contar_fuera_de_horario(Solicitud.aprobada_en).label("fuera_horario"),
            horas_resolucion.label("horas"),
        ).where(*self._filtro_fechas(desde, hasta, sectores))
        fila = (await self.sesion.execute(consulta)).one()
        return {
            "recibidas":     fila.recibidas,
            "aprobadas":     fila.aprobadas,
            "negadas":       fila.negadas,
            "expiradas":     fila.expiradas,
            "finalizadas":   fila.finalizadas,
            "fuera_horario": fila.fuera_horario,
            "horas":         float(fila.horas) if fila.horas is not None else None,
        }

    async def contar_por_tipo(
        self, desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None,
    ) -> list:
        consulta = (
            select(
                TipoTramite.codigo, TipoTramite.nombre,
                func.count(Solicitud.id).label("recibidas"),
                func.count(Solicitud.aprobada_en).label("aprobadas"),
                func.count(Solicitud.negada_en).label("negadas"),
                func.count(Solicitud.expirada_en).label("expiradas"),
            )
            .join(TipoTramite, TipoTramite.id == Solicitud.tipo_tramite_id)
            .where(*self._filtro_fechas(desde, hasta, sectores))
            .group_by(TipoTramite.codigo, TipoTramite.nombre, TipoTramite.orden)
            .order_by(TipoTramite.orden)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def contar_por_puesto(
        self, desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None,
    ) -> list:
        """Por el puesto donde vale la autorización (con cambio de puerto, el nuevo,
        que es el que la finaliza o la deja vencer)."""
        consulta = (
            select(
                PuestoControl.nombre,
                func.count(Solicitud.aprobada_en).label("aprobadas"),
                func.count(Solicitud.finalizada_en).label("finalizadas"),
                func.count(case((Solicitud.aprobada_en.isnot(None), Solicitud.expirada_en))).label("expiradas"),
            )
            .join(PuestoControl, PuestoControl.id == puesto_autorizado())
            .where(*self._filtro_fechas(desde, hasta, sectores))
            .group_by(PuestoControl.nombre)
            .order_by(func.count(Solicitud.aprobada_en).desc(), PuestoControl.nombre)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def serie_diaria(
        self, desde: date | None = None, hasta: date | None = None, sectores: AlcanceSectores | None = None,
    ) -> dict[date, dict[str, int]]:
        """Conteo por día (hora de Panamá) de cada hito, sobre las solicitudes
        creadas en el rango `desde`/`hasta` (si se da): cada cifra cuenta el día
        en que ocurrió (la llegada, la aprobación, la finalización…), y las fuera
        del horario, el día en que se aprobaron. Solo los días con alguna. El
        servicio la agrupa por día, por mes y por año."""
        series: dict[date, dict[str, int]] = {}
        columnas = {
            "recibidas":     (Solicitud.created_at, None),
            "aprobadas":     (Solicitud.aprobada_en, None),
            "negadas":       (Solicitud.negada_en, None),
            "expiradas":     (Solicitud.expirada_en, None),
            "finalizadas":   (Solicitud.finalizada_en, None),
            "fuera_horario": (Solicitud.aprobada_en, _fuera_de_horario(Solicitud.aprobada_en)),
        }
        for clave, (columna, condicion) in columnas.items():
            dia = _fecha_panama(columna)
            consulta = (
                select(dia.label("dia"), func.count())
                .where(
                    *self._filtro_fechas(desde, hasta, sectores),
                    columna.isnot(None),
                    *([condicion] if condicion is not None else []),
                )
                .group_by(dia)
            )
            for valor_dia, total in (await self.sesion.execute(consulta)).all():
                series.setdefault(valor_dia, {})[clave] = total
        return series

    async def aprobadas_por_hora(
        self, desde: date | None, hasta: date | None, sectores: AlcanceSectores | None = None,
    ) -> list:
        """Aprobadas por día de la semana (1 = lunes … 7 = domingo) y hora de la
        aprobación, en hora de Panamá: (dia, hora, total), solo las que tienen alguna."""
        local = func.timezone(_ZONA, Solicitud.aprobada_en)
        dia = extract("isodow", local)
        hora = extract("hour", local)
        consulta = (
            select(dia.label("dia"), hora.label("hora"), func.count().label("total"))
            .where(*self._filtro_fechas(desde, hasta, sectores), Solicitud.aprobada_en.isnot(None))
            .group_by(dia, hora)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def listar_fuera_horario(
        self, desde: date | None, hasta: date | None, limite: int, sectores: AlcanceSectores | None = None,
    ) -> list:
        """Las aprobadas fuera del horario laboral, la más reciente primero:
        (id, número, trámite, puesto autorizado, aprobada_en, quién aprobó). El
        nombre es la foto del historial, como en el expediente."""
        aprobada_por = (
            select(EventoSolicitud.usuario_nombre)
            .where(EventoSolicitud.solicitud_id == Solicitud.id,
                   EventoSolicitud.tipo == TipoEventoSolicitud.APROBADA.value)
            .order_by(EventoSolicitud.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        consulta = (
            select(
                Solicitud.id, Solicitud.numero, TipoTramite.nombre.label("tipo_tramite"),
                func.coalesce(Solicitud.puesto_destino_nombre, Solicitud.puesto_nombre).label("puesto"),
                Solicitud.aprobada_en,
                aprobada_por.label("aprobada_por"),
            )
            .join(TipoTramite, TipoTramite.id == Solicitud.tipo_tramite_id)
            .where(
                *self._filtro_fechas(desde, hasta, sectores),
                Solicitud.aprobada_en.isnot(None),
                _fuera_de_horario(Solicitud.aprobada_en),
            )
            .order_by(Solicitud.aprobada_en.desc(), Solicitud.id.desc())
            .limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())
