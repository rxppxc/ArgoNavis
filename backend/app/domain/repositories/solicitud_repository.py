"""Acceso a BD del expediente de las solicitudes: bandejas paginadas por
alcance (agencia, revisión, puesto), bloqueo de fila para las transiciones,
vencimientos, estadísticas y las novedades de las notificaciones internas."""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, Time, and_, case, cast, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.horario import FIN_LABORAL, INICIO_LABORAL, entre_fechas_panama
from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.models.solicitud import (
    RANGOS_CON_LIBRETA, CasillaSolicitud, DocumentoSolicitud, EstadoSolicitud, EventoSolicitud, Solicitud,
    TipoEventoSolicitud, TripulanteSolicitud,
)
from app.domain.models.tramite import TipoTramite

_ZONA = "America/Panama"


@dataclass
class FiltrosBandeja:
    """Alcance (quién ve qué) + filtros de la bandeja."""
    agencia_id:  int | None = None        # bandeja de la agencia
    puestos_ids: set[int] | None = None   # bandeja del puesto (None = todos)
    solo_aprobadas_alguna_vez: bool = False
    estado:      str | None = None
    texto:       str | None = None
    desde:       date | None = None
    hasta:       date | None = None


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
    def _condiciones(filtros: FiltrosBandeja, *, con_estado: bool) -> list:
        condiciones = []
        if filtros.agencia_id is not None:
            condiciones.append(Solicitud.agencia_id == filtros.agencia_id)
        if filtros.puestos_ids is not None:
            # Sin puestos asignados no ve nada (IN de una lista vacía no es válido en SQL).
            condiciones.append(Solicitud.puesto_control_id.in_(sorted(filtros.puestos_ids) or [-1]))
        if filtros.solo_aprobadas_alguna_vez:
            condiciones.append(Solicitud.aprobada_en.isnot(None))
        if filtros.texto:
            # autoescape: un «_» o un «%» de lo que se escribe se busca tal cual, no como comodín.
            texto = filtros.texto.strip()
            condiciones.append(or_(*(
                columna.icontains(texto, autoescape=True)
                for columna in (Solicitud.numero, Solicitud.titulo, Solicitud.nombre_buque, Solicitud.imo,
                                Solicitud.agencia_nombre, Solicitud.puesto_nombre)
            )))
        condiciones += entre_fechas_panama(Solicitud.enviada_en, filtros.desde, filtros.hasta)
        if con_estado and filtros.estado:
            condiciones.append(Solicitud.estado == filtros.estado)
        return condiciones

    async def contar_por_estado_en(self, filtros: FiltrosBandeja) -> dict[str, int]:
        """Cuántas hay en cada estado dentro del alcance (sin filtrar por estado):
        las pestañas de una bandeja y los pendientes de la campana."""
        return {
            estado: total for estado, total in (await self.sesion.execute(
                select(Solicitud.estado, func.count())
                .where(*self._condiciones(filtros, con_estado=False))
                .group_by(Solicitud.estado)
            )).all()
        }

    async def pendiente_en(self, filtros: FiltrosBandeja, estado: str) -> tuple[int, datetime | None]:
        """Cuántas hay en ese estado dentro del alcance y el plazo más próximo de
        ellas (el de corrección, las devueltas; el de finalización, las aprobadas).
        Una sola consulta: la campana la hace cada minuto por pestaña abierta, y
        antes eran dos (un conteo de todos los estados y el mínimo aparte)."""
        columna = Solicitud.plazo_correccion if estado == EstadoSolicitud.EN_CORRECCION.value else Solicitud.vigente_hasta
        cantidad, vence = (await self.sesion.execute(
            select(func.count(), func.min(columna))
            .where(*self._condiciones(filtros, con_estado=False), Solicitud.estado == estado)
        )).one()
        return int(cantidad or 0), vence

    async def listar(
        self, filtros: FiltrosBandeja, *, pagina: int, por_pagina: int, orden: str = "recientes",
    ) -> tuple[int, dict[str, int], list[Solicitud]]:
        """(total con filtros, conteo por estado sin filtrar estado, página). Sin
        los tripulantes: lo que la bandeja muestra de ellos sale de `alertas_de`."""
        conteos = await self.contar_por_estado_en(filtros)
        condiciones = self._condiciones(filtros, con_estado=True)
        total = (await self.sesion.execute(
            select(func.count()).select_from(Solicitud).where(*condiciones)
        )).scalar() or 0

        if orden == "cola":           # revisión: la más antigua primero (FIFO)
            orden_por = (Solicitud.enviada_en.asc(), Solicitud.id.asc())
        elif orden == "operacion":    # puerto: la operación más próxima primero
            orden_por = (Solicitud.fecha_operacion.asc(), Solicitud.id.asc())
        else:
            orden_por = (Solicitud.enviada_en.desc(), Solicitud.id.desc())

        consulta: Select = (
            select(Solicitud)
            .where(*condiciones)
            .order_by(*orden_por)
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        return total, conteos, list((await self.sesion.execute(consulta)).scalars().all())

    async def alertas_de(self, ids: list[int]) -> dict[int, tuple[int, bool]]:
        """Por solicitud: cuántos tripulantes tienen el pasaporte o el seamanbook
        vencido a la fecha de la operación y si alguno es de nacionalidad
        restringida. Lo calcula la BD en una consulta: antes cada página de una
        bandeja traía a todos sus tripulantes (hasta 100 × 30) solo para contarlos.
        La regla es la de ServicioSolicitud._vencimientos_tripulante."""
        if not ids:
            return {}
        t = TripulanteSolicitud
        vencido = or_(
            t.pasaporte_expira < Solicitud.fecha_operacion,
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
            or_(*[and_(*self._condiciones(f, con_estado=False), EventoSolicitud.tipo.in_(sorted(t))) for f, t in fuentes]),
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

    def agregar_registro(self, registro: EventoSolicitud | DocumentoSolicitud | CasillaSolicitud) -> None:
        """Agrega un evento, un documento o una casilla por su `solicitud_id`,
        sin pasar por las colecciones de la solicitud (que se recargan después)."""
        self.sesion.add(registro)

    async def guardar(self) -> None:
        await self.sesion.flush()

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
    def _filtro_fechas(desde: date | None, hasta: date | None) -> list:
        """Filtra por fecha de creación (inclusive, en hora de Panamá), con el índice de created_at."""
        return entre_fechas_panama(Solicitud.created_at, desde, hasta)

    async def contar_por_estado(self, desde: date | None, hasta: date | None) -> dict[str, int]:
        consulta = (
            select(Solicitud.estado, func.count())
            .where(*self._filtro_fechas(desde, hasta))
            .group_by(Solicitud.estado)
        )
        return {estado: total for estado, total in (await self.sesion.execute(consulta)).all()}

    async def contar_hitos(self, desde: date | None, hasta: date | None) -> dict[str, float | int | None]:
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
        ).where(*self._filtro_fechas(desde, hasta))
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

    async def contar_por_tipo(self, desde: date | None, hasta: date | None) -> list:
        consulta = (
            select(
                TipoTramite.codigo, TipoTramite.nombre,
                func.count(Solicitud.id).label("recibidas"),
                func.count(Solicitud.aprobada_en).label("aprobadas"),
                func.count(Solicitud.negada_en).label("negadas"),
                func.count(Solicitud.expirada_en).label("expiradas"),
            )
            .join(TipoTramite, TipoTramite.id == Solicitud.tipo_tramite_id)
            .where(*self._filtro_fechas(desde, hasta))
            .group_by(TipoTramite.codigo, TipoTramite.nombre, TipoTramite.orden)
            .order_by(TipoTramite.orden)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def contar_por_puesto(self, desde: date | None, hasta: date | None) -> list:
        consulta = (
            select(
                PuestoControl.nombre,
                func.count(Solicitud.aprobada_en).label("aprobadas"),
                func.count(Solicitud.finalizada_en).label("finalizadas"),
                func.count(case((Solicitud.aprobada_en.isnot(None), Solicitud.expirada_en))).label("expiradas"),
            )
            .join(PuestoControl, PuestoControl.id == Solicitud.puesto_control_id)
            .where(*self._filtro_fechas(desde, hasta))
            .group_by(PuestoControl.nombre)
            .order_by(func.count(Solicitud.aprobada_en).desc(), PuestoControl.nombre)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def serie_diaria(self, desde: date | None = None, hasta: date | None = None) -> dict[date, dict[str, int]]:
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
                    *self._filtro_fechas(desde, hasta),
                    columna.isnot(None),
                    *([condicion] if condicion is not None else []),
                )
                .group_by(dia)
            )
            for valor_dia, total in (await self.sesion.execute(consulta)).all():
                series.setdefault(valor_dia, {})[clave] = total
        return series

    async def aprobadas_por_hora(self, desde: date | None, hasta: date | None) -> list:
        """Aprobadas por día de la semana (1 = lunes … 7 = domingo) y hora de la
        aprobación, en hora de Panamá: (dia, hora, total), solo las que tienen alguna."""
        local = func.timezone(_ZONA, Solicitud.aprobada_en)
        dia = extract("isodow", local)
        hora = extract("hour", local)
        consulta = (
            select(dia.label("dia"), hora.label("hora"), func.count().label("total"))
            .where(*self._filtro_fechas(desde, hasta), Solicitud.aprobada_en.isnot(None))
            .group_by(dia, hora)
        )
        return list((await self.sesion.execute(consulta)).all())

    async def listar_fuera_horario(self, desde: date | None, hasta: date | None, limite: int) -> list:
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
                Solicitud.puesto_nombre.label("puesto"), Solicitud.aprobada_en,
                aprobada_por.label("aprobada_por"),
            )
            .join(TipoTramite, TipoTramite.id == Solicitud.tipo_tramite_id)
            .where(
                *self._filtro_fechas(desde, hasta),
                Solicitud.aprobada_en.isnot(None),
                _fuera_de_horario(Solicitud.aprobada_en),
            )
            .order_by(Solicitud.aprobada_en.desc(), Solicitud.id.desc())
            .limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())
