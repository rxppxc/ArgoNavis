"""Quién es el usuario dentro del flujo de solicitudes y qué alcance tiene (hasta el
2026-11-14, en solicitud_service.py). Lo arma `ServicioSolicitud.contexto` una vez por
pedido; lo usan el servicio, las rutas y la campana."""
from dataclasses import dataclass, field

from app.domain.models.solicitud import Solicitud
from app.domain.models.user import Usuario
from app.domain.repositories.solicitud_repository import AlcanceSectores


@dataclass
class ContextoAcceso:
    """Quién es el usuario dentro del flujo (se calcula una vez por request).

    Sectores (2026-11-10): UCVMM y los supervisores de sector ven solo las
    solicitudes de sus sectores (`Solicitud.sector_id`): las de sus puestos y, ya
    revisadas, las que revisó su sector aunque el puesto haya cambiado (2026-11-22). El
    Administrador, las de todos. El supervisor general (2026-11-16), las de los
    trámites que supervisa (`tipos_tramite.supervision_general`: el de Técnico),
    de los dos sectores."""
    usuario:     Usuario
    es_admin:    bool
    es_naviera:  bool
    es_revisor:  bool
    es_puerto:   bool
    puestos_ids: set[int]          # los puestos asignados (puesto de control)
    agencia_id:  int | None
    es_supervisor_sector:  bool = False
    es_supervisor_general: bool = False
    sectores_ids:          set[int] = field(default_factory=set)
    puestos_de_sectores:   set[int] = field(default_factory=set)

    @property
    def puede_revisar(self) -> bool:
        """Tiene el permiso de revisar (de qué solicitudes, lo dice el sector)."""
        return self.es_admin or self.es_revisor

    @property
    def es_supervisor(self) -> bool:
        return self.es_supervisor_sector or self.es_supervisor_general

    @property
    def ve_todos_los_sectores(self) -> bool:
        """Todas las solicitudes, sin límite de sector ni de trámite: el Administrador.
        Hasta el 2026-11-16, también el supervisor general (ver `supervisa_tramite`)."""
        return self.es_admin

    def supervisa_tramite(self, s: Solicitud) -> bool:
        """El supervisor general ve las de los trámites que supervisa (hoy, el de
        Técnico, Superintendente o Supernumerario), de los dos sectores (2026-11-16)."""
        return self.es_supervisor_general and s.tipo_tramite.supervision_general

    @property
    def ve_historico(self) -> bool:
        """La consulta histórica: UCVMM, el supervisor de sector y el Administrador. El
        supervisor general, no (2026-11-16); el puesto de control tampoco desde el
        2026-11-22: consulta las suyas en su bandeja."""
        return self.es_admin or self.es_revisor or self.es_supervisor_sector

    @property
    def alcance_sectores(self) -> AlcanceSectores:
        """Sus sectores, para filtrar en la BD: lo mismo que `en_sus_sectores`."""
        return AlcanceSectores(frozenset(self.sectores_ids), frozenset(self.puestos_de_sectores))

    def en_sus_sectores(self, s: Solicitud) -> bool:
        return self.ve_todos_los_sectores or s.sector_id in self.sectores_ids

    def puede_revisar_esta(self, s: Solicitud) -> bool:
        """Revisa las de sus sectores (el Administrador, todas)."""
        return self.es_admin or (self.es_revisor and self.en_sus_sectores(s))

    def ve_registro(self, s: Solicitud) -> bool:
        """El historial completo (2026-11-22): lo que se había enviado antes de cada
        corrección, los documentos retirados y las huellas. Lo ve el personal del SNM que
        ve la solicitud antes de aprobarse: UCVMM y el supervisor de su sector, el supervisor
        general (las de su trámite) y el Administrador. El puesto de control no, porque la
        ve desde que se aprueba; la agencia tampoco, porque lleva lo interno del SNM."""
        return (
            self.ve_todos_los_sectores
            or ((self.es_revisor or self.es_supervisor_sector) and self.en_sus_sectores(s))
            or self.supervisa_tramite(s)
        )

    @property
    def es_personal_snm(self) -> bool:
        """UCVMM, supervisión, puesto de control o admin. La verificación de
        impedimentos (y la acción tomada, p. ej. avisar a Operaciones) es
        información interna: no se muestra a la agencia."""
        return self.es_admin or self.es_revisor or self.es_puerto or self.es_supervisor

    def es_de_su_agencia(self, s: Solicitud) -> bool:
        return (self.es_naviera or self.es_admin) and self.agencia_id is not None and s.agencia_id == self.agencia_id


@dataclass(frozen=True)
class AlcanceEstadisticas:
    """De qué solicitudes son las estadísticas de quien consulta (2026-11-10):
    las de sus sectores, o las de todos (Administrador y supervisor general), o
    las del sector que eligió."""
    filtro:      AlcanceSectores | None   # None = todas
    texto:       str                      # "Todos los sectores", "Sector Pacífico"…
    sector_id:   int | None               # el sector elegido, si eligió uno
    sectores:    list[tuple[int, str]]    # los que puede elegir
    uso_del_sistema: bool                 # ve los totales de todo el sistema
