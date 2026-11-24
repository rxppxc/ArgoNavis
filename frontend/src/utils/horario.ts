/**
 * Horario laboral, espejo de core/horario.py: de lunes a viernes, de 07:00 a 15:00, hora de
 * Panamá, al minuto y con las dos puntas dentro (las 15:00 en punto todavía son laborales;
 * desde las 15:01, fuera). Fuera del horario, lo que UCVMM aprueba lleva recargo.
 * - Las horas las compara test_constantes_iguales_en_el_frontend, y los casos de
 *   `fueraDeHorario` son los de backend/tests/espejo/horario.json.
 * - Lo usan el mapa de horas de las estadísticas, la frase del chip y del expediente y, desde
 *   el 2026-11-24, el reloj del inicio (RelojHorario).
 */
import { dosCifras } from "./fechas";

export const HORA_INICIO_LABORAL = 7;
export const HORA_FIN_LABORAL = 15;

/** Como lo dicen el correo y el PDF (TEXTO_HORARIO, core/horario.py). */
export const TEXTO_HORARIO_LABORAL =
  `lunes a viernes, de ${dosCifras(HORA_INICIO_LABORAL)}:00 a ${dosCifras(HORA_FIN_LABORAL)}:00`;

/** Panamá está en UTC−5 todo el año: no cambia la hora. */
const DESFASE_PANAMA_MS = 5 * 3_600_000;

export interface HoraPanama {
  /** El día en Panamá, AAAA-MM-DD. */
  iso:       string;
  /** 1 = lunes … 7 = domingo, como el mapa de horas de las estadísticas. */
  diaSemana: number;
  hora:      number;
  minuto:    number;
}

/** El momento en Panamá, sin importar la zona horaria del equipo. */
export function enPanama(momento: Date): HoraPanama {
  const d = new Date(momento.getTime() - DESFASE_PANAMA_MS);
  return {
    iso: `${d.getUTCFullYear()}-${dosCifras(d.getUTCMonth() + 1)}-${dosCifras(d.getUTCDate())}`,
    diaSemana: d.getUTCDay() || 7,
    hora: d.getUTCHours(),
    minuto: d.getUTCMinutes(),
  };
}

/** Si el momento cae fuera del horario laboral (`fuera_de_horario`, core/horario.py). */
export function fueraDeHorario(momento: Date): boolean {
  const { diaSemana, hora, minuto } = enPanama(momento);
  const minutos = hora * 60 + minuto;
  return diaSemana >= 6 || minutos < HORA_INICIO_LABORAL * 60 || minutos > HORA_FIN_LABORAL * 60;
}

export interface EstadoHorario {
  laboral: boolean;
  /** Hasta cuándo sigue así: «las 15:00», «las 07:00», «mañana a las 07:00», «el lunes a las 07:00». */
  hasta:   string;
}

export function estadoHorario(momento: Date): EstadoHorario {
  const inicio = `las ${dosCifras(HORA_INICIO_LABORAL)}:00`;
  if (!fueraDeHorario(momento)) return { laboral: true, hasta: `las ${dosCifras(HORA_FIN_LABORAL)}:00` };
  const { diaSemana, hora } = enPanama(momento);
  // Un día de semana antes de abrir, abre hoy.
  if (diaSemana <= 5 && hora < HORA_INICIO_LABORAL) return { laboral: false, hasta: inicio };
  // Del lunes al jueves por la tarde, y el domingo, abre mañana; el viernes y el sábado, el lunes.
  const abreManana = diaSemana <= 4 || diaSemana === 7;
  return { laboral: false, hasta: `${abreManana ? "mañana" : "el lunes"} a ${inicio}` };
}
