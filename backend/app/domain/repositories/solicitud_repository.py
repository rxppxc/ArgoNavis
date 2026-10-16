"""Acceso a BD del expediente de las solicitudes: bandejas paginadas por
alcance (agencia, revisión, puesto), bloqueo de fila para las transiciones,
vencimientos y estadísticas."""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, and_, case, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.catalogo import PuestoControl
from app.domain.models.solicitud import (
    CasillaSolicitud, DocumentoSolicitud, EstadoSolicitud, EventoSolicitud, Solicitud,
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
            patron = f"%{filtros.texto.strip()}%"
            condiciones.append(or_(
                Solicitud.numero.ilike(patron),
                Solicitud.titulo.ilike(patron),
                Solicitud.nombre_buque.ilike(patron),
                Solicitud.imo.ilike(patron),
                Solicitud.agencia_nombre.ilike(patron),
                Solicitud.puesto_nombre.ilike(patron),
            ))
        if filtros.desde:
            condiciones.append(_fecha_panama(Solicitud.enviada_en) >= filtros.desde)
        if filtros.hasta:
            condiciones.append(_fecha_panama(Solicitud.enviada_en) <= filtros.hasta)
        if con_estado and filtros.estado:
            condiciones.append(Solicitud.estado == filtros.estado)
        return condiciones

    async def listar(
        self, filtros: FiltrosBandeja, *, pagina: int, por_pagina: int, orden: str = "recientes",
    ) -> tuple[int, dict[str, int], list[Solicitud]]:
        """(total con filtros, conteo por estado sin filtrar estado, página)."""
        conteos = {
            estado: total for estado, total in (await self.sesion.execute(
                select(Solicitud.estado, func.count())
                .where(*self._condiciones(filtros, con_estado=False))
                .group_by(Solicitud.estado)
            )).all()
        }
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
            .options(selectinload(Solicitud.tripulantes))
            .where(*condiciones)
            .order_by(*orden_por)
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        return total, conteos, list((await self.sesion.execute(consulta)).scalars().all())

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
        consulta = (
            select(Solicitud.agencia_id, Solicitud.agencia_nombre, func.count().label("total"))
            .group_by(Solicitud.agencia_id, Solicitud.agencia_nombre)
            .order_by(func.count().desc())
            .limit(limite)
        )
        return list((await self.sesion.execute(consulta)).all())

    # ── Estadísticas del flujo ───────────────────────────────────────────────

    @staticmethod
    def _filtro_fechas(desde: date | None, hasta: date | None) -> list:
        """Filtra por fecha de creación (inclusive, en hora de Panamá)."""
        filtros = []
        if desde:
            filtros.append(_fecha_panama(Solicitud.created_at) >= desde)
        if hasta:
            filtros.append(_fecha_panama(Solicitud.created_at) <= hasta)
        return filtros

    async def contar_por_estado(self, desde: date | None, hasta: date | None) -> dict[str, int]:
        consulta = (
            select(Solicitud.estado, func.count())
            .where(*self._filtro_fechas(desde, hasta))
            .group_by(Solicitud.estado)
        )
        return {estado: total for estado, total in (await self.sesion.execute(consulta)).all()}

    async def contar_hitos(self, desde: date | None, hasta: date | None) -> dict[str, float | int | None]:
        """Totales por hito alcanzado (no por estado actual): una solicitud
        aprobada y luego finalizada cuenta como aprobada y como finalizada."""
        horas_resolucion = func.avg(
            extract("epoch", func.coalesce(Solicitud.aprobada_en, Solicitud.negada_en) - Solicitud.created_at) / 3600
        )
        consulta = select(
            func.count().label("recibidas"),
            func.count(Solicitud.aprobada_en).label("aprobadas"),
            func.count(Solicitud.negada_en).label("negadas"),
            func.count(Solicitud.expirada_en).label("expiradas"),
            func.count(Solicitud.finalizada_en).label("finalizadas"),
            horas_resolucion.label("horas"),
        ).where(*self._filtro_fechas(desde, hasta))
        fila = (await self.sesion.execute(consulta)).one()
        return {
            "recibidas":   fila.recibidas,
            "aprobadas":   fila.aprobadas,
            "negadas":     fila.negadas,
            "expiradas":   fila.expiradas,
            "finalizadas": fila.finalizadas,
            "horas":       float(fila.horas) if fila.horas is not None else None,
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

    async def serie_mensual(
        self, desde_mes: date, desde: date | None = None, hasta: date | None = None,
    ) -> dict[str, dict[str, int]]:
        """Conteo por mes (hora de Panamá) de cada hito desde `desde_mes`,
        sobre las solicitudes creadas en el rango `desde`/`hasta` (si se da)."""
        series: dict[str, dict[str, int]] = {}
        columnas = {
            "recibidas": Solicitud.created_at,
            "aprobadas": Solicitud.aprobada_en,
            "negadas":   Solicitud.negada_en,
            "expiradas": Solicitud.expirada_en,
        }
        for clave, columna in columnas.items():
            mes = func.to_char(func.timezone(_ZONA, columna), "YYYY-MM")
            consulta = (
                select(mes.label("mes"), func.count())
                .where(
                    *self._filtro_fechas(desde, hasta),
                    columna.isnot(None),
                    _fecha_panama(columna) >= desde_mes,
                )
                .group_by(mes)
            )
            for valor_mes, total in (await self.sesion.execute(consulta)).all():
                series.setdefault(valor_mes, {}).setdefault(clave, total)
        return series
