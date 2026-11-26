/** Textos y formatos compartidos por las pantallas de solicitudes. */
import type {
  EstadoSolicitud, EventoSolicitud, Operacion, RangoMarino, Sexo, TripulanteSolicitud,
} from "../../api/solicitudes";
import { dosCifras } from "../../utils/fechas";

export const ETIQUETA_ESTADO: Record<EstadoSolicitud, string> = {
  review:    "En revisión",
  returned:  "En corrección",
  approved:  "Aprobada",
  denied:    "Denegada",
  finalized: "Finalizada",
  expired:   "Expirada",
};

export const ETIQUETA_RANGO: Record<RangoMarino, string> = {
  marino:          "Marino",
  pasajero:        "Pasajero",   // un Marino sin libreta (2026-11-13)
  militar:         "Militar",
  tecnico:         "Técnico",
  supernumerario:  "Supernumerario",
  superintendente: "Superintendente",
};

export const TODOS_LOS_RANGOS = Object.keys(ETIQUETA_RANGO) as RangoMarino[];

/** La operación del trámite de Técnico (2026-11-18), en el orden del formulario. Espejo de
 *  ETIQUETA_OPERACION (models/solicitud.py), que la escribe en el PDF y en la boleta. */
export const ETIQUETA_OPERACION: Record<Operacion, string> = {
  embarque:      "Embarque",
  desembarque:   "Desembarque",
  subir_y_bajar: "Subir y bajar",
};

/** Los días del sellado de Shore Pass (2026-11-18): «15 días», como texto_dias (models/solicitud.py). */
export function textoDias(dias: number): string {
  return `${dias} días`;
}

/** Lo que lee la agencia al devolverse una solicitud con tripulantes con impedimento (2026-11-26):
 *  quiénes son y que la solicitud no puede avanzar con ellos. Espejo de aviso_impedimentos
 *  (models/solicitud.py), con los casos de backend/tests/espejo/impedimentos.json. */
export function avisoImpedimentos(nombres: string[]): string | null {
  if (!nombres.length) return null;
  const final = "si va otra persona, agrégala como tripulante nuevo.";
  if (nombres.length === 1) {
    return `Tripulante con impedimento: ${nombres[0]}. La solicitud no puede avanzar con esa persona: quítala al corregir; ${final}`;
  }
  const lista = `${nombres.slice(0, -1).join(", ")} y ${nombres[nombres.length - 1]}`;
  return `Tripulantes con impedimento: ${lista}. La solicitud no puede avanzar con esas personas: quítalas al corregir; ${final}`;
}

/** Cuánto vale la autorización de un trámite con `horas_vigencia` (Urgencia médica, 120:
 *  2026-11-26): «120 horas (5 días) desde la aprobación». Espejo de texto_vigencia
 *  (core/horario.py), con los casos de backend/tests/espejo/vigencia.json. */
export function textoVigencia(horas: number): string {
  const dias = horas % 24 === 0 ? ` (${horas / 24} ${horas === 24 ? "día" : "días"})` : "";
  return `${horas} horas${dias} desde la aprobación`;
}

export const ETIQUETA_SEXO: Record<Sexo, string> = {
  M: "Masculino",
  F: "Femenino",
  X: "No especificado",
};

/** Títulos del historial, por el estado al que lleva cada hito. */
export const ETIQUETA_EVENTO: Record<EventoSolicitud["tipo"], string> = {
  creada:       "Enviada · En revisión",
  corregida:    "Corregida · En revisión",
  impedimentos: "Verificación de impedimentos",
  impedimentos_corregidos: "Corrección de impedimentos",
  impedimentos_puesto: "Verificación de impedimentos en el puesto",
  impedimentos_puesto_corregidos: "Corrección de impedimentos en el puesto",
  devuelta:     "Devuelta a corrección",
  aprobada:     "Aprobada",
  negada:       "Denegada",
  comentario:   "Comentario del puesto de control",
  finalizada:   "Finalizada",
  expirada:     "Expirada",
  boleta_generada: "Boleta de recargo generada",
  boleta_anulada:  "Boleta de recargo anulada",
};

/** Rangos que portan seamanbook (al resto no se le pide libreta). */
export const RANGOS_CON_LIBRETA: RangoMarino[] = ["marino"];

/** El título de la columna del rango en el expediente: «Rango / ocupación» solo si
 *  algún tripulante la tiene (una solicitud de antes del 2026-11-16, cuando la ocupación
 *  salió del formulario). Lo mismo hace el PDF (titulo_columna_rango). */
export function tituloColumnaRango(tripulantes: Pick<TripulanteSolicitud, "ocupacion">[]): "Rango / ocupación" | "Rango" {
  return tripulantes.some((t) => t.ocupacion) ? "Rango / ocupación" : "Rango";
}

interface ConPuestos {
  puesto_nombre: string | null;
  puesto_destino_nombre: string | null;
}

/** Donde vale la autorización y se finaliza: con cambio de puerto (2026-11-13), el
 *  nuevo puesto. Espejo de Solicitud.puesto_autorizado_nombre. */
export function puestoAutorizado(s: ConPuestos): string {
  return s.puesto_destino_nombre ?? s.puesto_nombre ?? "";
}

/** El puesto; con cambio de puerto, los dos: «Balboa → Rodman». */
export function textoPuestos(s: ConPuestos): string {
  return s.puesto_destino_nombre ? `${s.puesto_nombre ?? ""} → ${s.puesto_destino_nombre}` : s.puesto_nombre ?? "";
}

interface ConSectores {
  sector_nombre: string | null;
  sector_actual_nombre: string | null;
}

/** El sector de UCVMM que la revisó y, si el puesto es hoy de otro, los dos (2026-11-22). */
export function textoSector(s: ConSectores): string | null {
  return s.sector_actual_nombre && s.sector_nombre
    ? `${s.sector_nombre}, que la revisó. Hoy el puesto es del ${s.sector_actual_nombre}`
    : s.sector_nombre;
}

/** Lo mismo, corto, para las bandejas y la consulta histórica. */
export function textoSectorCorto(s: ConSectores): string | null {
  return s.sector_actual_nombre && s.sector_nombre ? `${s.sector_nombre} (hoy, ${s.sector_actual_nombre})` : s.sector_nombre;
}

/** El horario laboral, como lo dicen el correo y el PDF (TEXTO_HORARIO, core/horario.py). */
export { TEXTO_HORARIO_LABORAL } from "../../utils/horario";

/** Aclaraciones del instructivo del Formulario No. 3 (pág. 3) para el buque y
 *  el puerto, según el trámite. Se muestran como placeholder del campo. */
export const AYUDA_CAMPOS_TRAMITE: Partial<Record<string, { buque?: string; puerto?: string }>> = {
  "F3-CAMBIO-NAVE":   { buque: "Nueva nave a embarcar" },
  "F3-SHORE-PASS":    { buque: "Nave de desembarque" },
  "F3-CAMBIO-PUERTO": { puerto: "Nuevo puerto a embarcar" },
};

/** "2026-10-07" → "07/10/2026" sin pasar por Date (evita el corrimiento de zona horaria). */
export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [anio, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

/** Fecha y hora local como "06/10/2026, 03:10 p. m.". El orden día/mes se arma
 *  a mano: el locale es-PA formatea mes/día, y el PDF y los correos usan día/mes. */
export function formatearFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const hora = d.toLocaleTimeString("es-PA", { hour: "2-digit", minute: "2-digit" });
  return `${dosCifras(d.getDate())}/${dosCifras(d.getMonth() + 1)}/${d.getFullYear()}, ${hora}`;
}

/** Tiempo que falta hasta `iso`: `texto` corto ("1 día 4 h", "2 días", "35 min")
 *  y `frase` lista para mostrar ("queda 1 día", "quedan 2 días 4 h"). */
export function tiempoRestante(iso: string | null | undefined): { texto: string; frase: string; vencido: boolean } {
  if (!iso) return { texto: "—", frase: "—", vencido: false };
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { texto: "venció", frase: "venció", vencido: true };
  const horas = Math.floor(ms / 3_600_000);
  const dias = Math.floor(horas / 24);
  const minutos = Math.max(1, Math.floor(ms / 60_000));
  const [cifra, texto]: [number, string] =
    dias > 0 ? [dias, `${dias} día${dias === 1 ? "" : "s"}${horas % 24 ? ` ${horas % 24} h` : ""}`]
    : horas > 0 ? [horas, `${horas} h`]
    : [minutos, `${minutos} min`];
  // El verbo concuerda con la primera cifra: "queda 1 día 4 h", "quedan 2 días".
  return { texto, frase: `${cifra === 1 ? "queda" : "quedan"} ${texto}`, vencido: false };
}

/** IMO válido (7 dígitos, el último es el verificador). Devuelve los dígitos o null. */
export function normalizarImo(valor: string): string | null {
  const coincidencia = valor.trim().match(/^(?:IMO)?\s*(\d{7})$/i);
  if (!coincidencia) return null;
  const digitos = coincidencia[1];
  const suma = [7, 6, 5, 4, 3, 2].reduce((acc, peso, i) => acc + Number(digitos[i]) * peso, 0);
  return suma % 10 === Number(digitos[6]) ? digitos : null;
}
