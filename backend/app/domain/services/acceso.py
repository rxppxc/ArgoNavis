"""Quién es el usuario dentro del flujo de solicitudes y qué alcance tiene (hasta el
2026-11-14, en solicitud_service.py). Lo arma `ServicioSolicitud.contexto` una vez por
pedido; lo usan el servicio, las rutas y la campana."""
from dataclasses import dataclass, field

from app.domain.models.solicitud import Solicitud
from app.domain.models.user import Usuario


@dataclass
class ContextoAcceso:
    """Quién es el usuario dentro del flujo (se calcula una vez por request).

    Sectores (2026-11-10): UCVMM y los supervisores de sector ven solo las
    solicitudes de los puestos de sus sectores (`puestos_de_sectores`); el
    Administrador y el supervisor general, las de todos."""
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
        return self.es_admin or self.es_supervisor_general

    @property
    def alcance_ucvmm(self) -> set[int] | None:
        """Los puestos cuyas solicitudes ve como UCVMM o supervisión (None = todos)."""
        return None if self.ve_todos_los_sectores else self.puestos_de_sectores

    def en_sus_sectores(self, s: Solicitud) -> bool:
        return self.ve_todos_los_sectores or s.puesto_control_id in self.puestos_de_sectores

    def puede_revisar_esta(self, s: Solicitud) -> bool:
        """Revisa las de los puestos de sus sectores (el Administrador, todas)."""
        return self.es_admin or (self.es_revisor and s.puesto_control_id in self.puestos_de_sectores)

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
    puestos_ids: set[int] | None          # None = todas
    texto:       str                      # "Todos los sectores", "Sector Pacífico"…
    sector_id:   int | None               # el sector elegido, si eligió uno
    sectores:    list[tuple[int, str]]    # los que puede elegir
    uso_del_sistema: bool                 # ve los totales de todo el sistema
