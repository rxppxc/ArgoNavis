"""Reglas del formulario y del checklist de una solicitud de trámite.

El catálogo (`tramite_documentos`) dice QUÉ documentos exige cada trámite;
este servicio decide CUÁLES son exigibles en una solicitud concreta, porque
varias condiciones dependen de los datos de esa solicitud:

  - SOLO_PANAMENOS           → solo a tripulantes panameños (hoy sin uso: la
                               Libreta de Embarque se pide a todo Marino).
  - NACIONALIDAD_RESTRINGIDA → solo a tripulantes de nacionalidad restringida
                               (Formulario No. 6 de custodia, hoy solo en
                               Desembarque, como en el Form. 3).
  - Documentos con `requiere_libreta` → solo a quien porta seamanbook (rango
    Marino); militares, técnicos, supernumerarios y superintendentes no.

`construir_casillas` está espejado en el frontend
(`modulos/solicitudes/checklist.ts`): si cambias uno, cambia el otro.

También valida la cabecera del formulario y la ficha de cada tripulante
(vigencia de pasaporte y seamanbook: hoy la exigen los 8 trámites).
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.domain.models.solicitud import RANGOS_CON_LIBRETA, RangoMarino
from app.domain.models.tramite import AlcanceDocumento, CondicionDocumento, TipoTramite
from app.domain.schemas.solicitud import DatosTripulanteEntrada

_IMO_RE = re.compile(r"^(?:IMO)?\s*(\d{7})$", re.IGNORECASE)

EDAD_MINIMA = 18                     # años cumplidos a la fecha de la solicitud
NACIMIENTO_MINIMO = date(1900, 1, 1)


def edad_cumplida(nacimiento: date, hoy: date) -> int:
    """Años cumplidos a `hoy`."""
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))

ETIQUETA_RANGO = {
    RangoMarino.MARINO.value:          "Marino",
    RangoMarino.MILITAR.value:         "Militar",
    RangoMarino.TECNICO.value:         "Técnico",
    RangoMarino.SUPERNUMERARIO.value:  "Supernumerario",
    RangoMarino.SUPERINTENDENTE.value: "Superintendente",
}


@dataclass
class CasillaChecklist:
    """Una casilla concreta del checklist de una solicitud.

    Si `indice_tripulante` es None, el documento es de la solicitud completa;
    si trae índice, corresponde a ese tripulante de la lista.
    """
    documento_id:      int
    codigo_documento:  str
    nombre_documento:  str
    alcance:           str
    indice_tripulante: int | None = None
    nombre_tripulante: str | None = None


@dataclass
class TripulanteChecklist:
    """Datos de un tripulante que intervienen en el checklist."""
    nombre:                   str
    es_panameno:              bool = False
    porta_libreta:            bool = True
    nacionalidad_restringida: bool = False


@dataclass
class ResultadoChecklist:
    requeridas: list[CasillaChecklist] = field(default_factory=list)
    faltantes:  list[CasillaChecklist] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return not self.faltantes

    def describir_faltantes(self) -> str:
        """Mensaje legible para el error 400 que ve la agencia."""
        partes = []
        for casilla in self.faltantes:
            if casilla.nombre_tripulante:
                partes.append(f"{casilla.nombre_documento} de {casilla.nombre_tripulante}")
            else:
                partes.append(casilla.nombre_documento)
        return "; ".join(partes)


def normalizar_imo(valor: str) -> str | None:
    """Devuelve los 7 dígitos del número IMO si es válido (incluido su dígito
    verificador), o None si no lo es. Acepta "IMO 9074729" o "9074729"."""
    coincidencia = _IMO_RE.match((valor or "").strip())
    if not coincidencia:
        return None
    digitos = coincidencia.group(1)
    suma = sum(int(d) * peso for d, peso in zip(digitos[:6], range(7, 1, -1)))
    return digitos if suma % 10 == int(digitos[6]) else None


def _fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


class ServicioTramite:
    """Evalúa el checklist y valida el formulario de una solicitud."""

    def construir_casillas(
        self, tipo: TipoTramite, tripulantes: list[TripulanteChecklist],
    ) -> list[CasillaChecklist]:
        """Casillas que esta solicitud debe cubrir, ya resueltas las condiciones."""
        casillas: list[CasillaChecklist] = []

        for td in sorted(tipo.documentos, key=lambda x: x.orden or 0):
            if td.alcance == AlcanceDocumento.SOLICITUD.value:
                if (td.condicion == CondicionDocumento.NACIONALIDAD_RESTRINGIDA.value
                        and not any(t.nacionalidad_restringida for t in tripulantes)):
                    continue
                casillas.append(CasillaChecklist(
                    documento_id=td.documento_id,
                    codigo_documento=td.documento.codigo,
                    nombre_documento=td.documento.nombre,
                    alcance=td.alcance,
                ))
                continue

            # Alcance "marino": una casilla por cada tripulante al que aplique.
            for indice, tripulante in enumerate(tripulantes):
                if td.condicion == CondicionDocumento.SOLO_PANAMENOS.value and not tripulante.es_panameno:
                    continue
                if (td.condicion == CondicionDocumento.NACIONALIDAD_RESTRINGIDA.value
                        and not tripulante.nacionalidad_restringida):
                    continue
                if td.documento.requiere_libreta and not tripulante.porta_libreta:
                    continue
                casillas.append(CasillaChecklist(
                    documento_id=td.documento_id,
                    codigo_documento=td.documento.codigo,
                    nombre_documento=td.documento.nombre,
                    alcance=td.alcance,
                    indice_tripulante=indice,
                    nombre_tripulante=tripulante.nombre,
                ))

        return casillas

    def evaluar(
        self, tipo: TipoTramite, tripulantes: list[TripulanteChecklist],
        cubiertas: set[tuple[int, int | None]],
    ) -> ResultadoChecklist:
        """Compara las casillas exigibles contra las que traen archivo.

        `cubiertas` son tuplas (documento_id, indice_tripulante) —
        indice_tripulante en None para los documentos de alcance solicitud.
        """
        requeridas = self.construir_casillas(tipo, tripulantes)
        faltantes = [
            casilla for casilla in requeridas
            if (casilla.documento_id, casilla.indice_tripulante) not in cubiertas
        ]
        return ResultadoChecklist(requeridas=requeridas, faltantes=faltantes)

    def validar_campos_cabecera(self, tipo: TipoTramite, datos: dict) -> list[str]:
        """Campos obligatorios según el tipo de trámite. Devuelve los que faltan.

        El puesto de control se pide en todos los trámites porque decide qué
        puesto recibe y finaliza la autorización. Del buque (cuando el trámite
        lo pide) se exigen nombre, IMO y bandera, como en el formulario de UCVMM.
        """
        faltantes: list[str] = []
        if not datos.get("puesto_control_id"):
            faltantes.append("Puesto de Control Migratorio")
        if not datos.get("fecha_operacion"):
            faltantes.append("Fecha de la operación")
        if tipo.requiere_buque:
            if not datos.get("nombre_buque"):
                faltantes.append("Nombre del buque")
            if not datos.get("imo"):
                faltantes.append("IMO")
            if not datos.get("bandera"):
                faltantes.append("Bandera")
        if tipo.requiere_puerto and not datos.get("nombre_puerto"):
            faltantes.append("Nombre del puerto")
        if tipo.requiere_puerto_desembarque and not datos.get("puerto_desembarque"):
            faltantes.append("Puerto de desembarque")
        if tipo.requiere_motivo and not datos.get("motivo"):
            faltantes.append("Motivo")
        if tipo.requiere_clinica and not datos.get("clinica_hospital"):
            faltantes.append("Clínica u hospital")
        return faltantes

    def validar_tripulantes(
        self,
        tipo: TipoTramite,
        tripulantes: list[DatosTripulanteEntrada],
        *,
        fecha_referencia: date,
        hoy: date,
        codigos_pais_validos: set[str],
    ) -> list[str]:
        """Errores de la ficha de los tripulantes (lista vacía si todo bien).

        La vigencia se compara contra `fecha_referencia` (el día de la
        operación, o hoy si fuera anterior): el documento tiene que estar
        vigente el día del trámite en puerto.
        """
        errores: list[str] = []
        pasaportes_vistos: dict[tuple[str, str], int] = {}
        rangos = set(tipo.rangos_permitidos or [])
        rangos_texto = ", ".join(ETIQUETA_RANGO.get(r, r) for r in tipo.rangos_permitidos or [])

        for indice, t in enumerate(tripulantes, start=1):
            quien = f"Tripulante {indice} ({t.nombre} {t.apellido})"

            if t.nacionalidad not in codigos_pais_validos:
                errores.append(f"{quien}: la nacionalidad no es válida.")
            if t.pais_nacimiento not in codigos_pais_validos:
                errores.append(f"{quien}: el país de nacimiento no es válido.")
            if t.fecha_nacimiento >= hoy:
                errores.append(f"{quien}: la fecha de nacimiento debe ser anterior a hoy.")
            elif t.fecha_nacimiento < NACIMIENTO_MINIMO:
                errores.append(f"{quien}: la fecha de nacimiento no es válida.")
            elif edad_cumplida(t.fecha_nacimiento, hoy) < EDAD_MINIMA:
                errores.append(f"{quien}: debe ser mayor de edad ({EDAD_MINIMA} años cumplidos).")
            if t.pasaporte_expira <= t.fecha_nacimiento:
                errores.append(f"{quien}: el vencimiento del pasaporte debe ser posterior a la fecha de nacimiento.")
            if t.libreta_expira and t.libreta_expira <= t.fecha_nacimiento:
                errores.append(f"{quien}: el vencimiento del seamanbook debe ser posterior a la fecha de nacimiento.")

            clave = (t.nacionalidad, t.pasaporte)
            if clave in pasaportes_vistos:
                errores.append(f"{quien}: el pasaporte {t.pasaporte} ya está en el tripulante {pasaportes_vistos[clave]}.")
            else:
                pasaportes_vistos[clave] = indice

            if rangos and t.rango not in rangos:
                errores.append(f"{quien}: en este trámite el rango debe ser {rangos_texto}.")

            porta_libreta = t.rango in RANGOS_CON_LIBRETA
            if porta_libreta and (not t.libreta_marino or not t.libreta_expira):
                errores.append(f"{quien}: el rango Marino requiere el número de seamanbook y su fecha de expiración.")

            if tipo.valida_vigencia:
                if t.pasaporte_expira < fecha_referencia:
                    errores.append(
                        f"{quien}: el pasaporte vence el {_fecha(t.pasaporte_expira)}, "
                        f"antes de la operación ({_fecha(fecha_referencia)})."
                    )
                if porta_libreta and t.libreta_expira and t.libreta_expira < fecha_referencia:
                    errores.append(
                        f"{quien}: el seamanbook vence el {_fecha(t.libreta_expira)}, "
                        f"antes de la operación ({_fecha(fecha_referencia)})."
                    )

        return errores
