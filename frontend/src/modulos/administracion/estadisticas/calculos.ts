/**
 * Cálculos y textos de la página de Estadísticas, sin React (sus pruebas, en
 * calculos.test.ts): cifras y porcentajes, la escala de los ejes, los niveles
 * del mapa de horas, los periodos del filtro y la unidad de la serie.
 */
import type { EstadoSolicitud } from "../../../api/solicitudes";
import type { RangoFechas } from "../../../components/FiltroFechas";

const ESPACIO = " ";   // entre la cifra y el %, para que no se separen al cortar la línea

export function cifra(n: number): string {
  return n.toLocaleString("es-PA");
}

/** "80 %"; "<1 %" si hay alguna pero no llega al 1 %; nunca "100 %" si falta
 *  alguna (99,6 % es "99 %"); "—" si no hay total. */
export function porcentaje(parte: number, total: number): string {
  if (total <= 0) return "—";
  const p = (parte / total) * 100;
  if (parte > 0 && p < 1) return `<1${ESPACIO}%`;
  return `${Math.min(Math.round(p), parte < total ? 99 : 100)}${ESPACIO}%`;
}

/** Proporción entre 0 y 1, para el ancho o el alto de una barra. */
export function proporcion(parte: number, total: number): number {
  return total > 0 ? Math.min(1, Math.max(0, parte / total)) : 0;
}

/** El singular o el plural según la cantidad. */
export function segun(n: number, uno: string, varios: string): string {
  return n === 1 ? uno : varios;
}

/** Tiempo legible: "45 min", "6 h 24 min", "2 días y 3 h". */
export function duracion(horas: number | null): string {
  if (horas === null) return "—";
  const minutos = Math.round(horas * 60);
  if (minutos < 60) return `${minutos} min`;
  if (minutos < 48 * 60) {
    const h = Math.floor(minutos / 60), m = minutos % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
  }
  const dias = Math.floor(minutos / 1440), h = Math.floor((minutos % 1440) / 60);
  return h ? `${dias} días y ${h} h` : `${dias} días`;
}

/** Escala de un eje de cantidades: un tope redondo (pasos de 1, 2 o 5 × 10ⁿ,
 *  nunca menores que 1) y sus marcas, de 0 al tope. */
export function escalaEje(maximo: number, marcasDeseadas = 4): { tope: number; marcas: number[] } {
  if (maximo <= 0) return { tope: 1, marcas: [0, 1] };
  const pasoCrudo = maximo / marcasDeseadas;
  const potencia = 10 ** Math.floor(Math.log10(pasoCrudo));
  const paso = Math.max(1, [1, 2, 5, 10].map((m) => m * potencia).find((p) => p >= pasoCrudo) ?? 10 * potencia);
  const tope = Math.ceil(maximo / paso) * paso;
  return { tope, marcas: Array.from({ length: Math.round(tope / paso) + 1 }, (_, i) => i * paso) };
}

/** Nivel de una casilla del mapa de horas: 0 = ninguna; 1 a 5, según el máximo. */
export const NIVELES_CALOR = 5;
export function nivelCalor(total: number, maximo: number): number {
  if (total <= 0 || maximo <= 0) return 0;
  return Math.min(NIVELES_CALOR, Math.max(1, Math.ceil((total / maximo) * NIVELES_CALOR)));
}

// ─── Días y horas (el mapa de horas) ───────────────────────────────────────

/** Lunes a domingo, como los cuenta el backend (1 = lunes, ISO). */
export const DIAS_SEMANA = [
  { dia: 1, corto: "Lun", largo: "Lunes" },
  { dia: 2, corto: "Mar", largo: "Martes" },
  { dia: 3, corto: "Mié", largo: "Miércoles" },
  { dia: 4, corto: "Jue", largo: "Jueves" },
  { dia: 5, corto: "Vie", largo: "Viernes" },
  { dia: 6, corto: "Sáb", largo: "Sábado" },
  { dia: 7, corto: "Dom", largo: "Domingo" },
] as const;

/** Horario laboral, espejo de core/horario.py (lo compara test_constantes_iguales_en_el_frontend):
 *  de lunes a viernes, de 07:00 a 15:00, al minuto y con las dos puntas dentro (las 15:00
 *  en punto todavía son laborales; desde las 15:01, fuera). Cuenta la aprobación de UCVMM. */
export const HORA_INICIO_LABORAL = 7;
export const HORA_FIN_LABORAL = 15;

/** El mapa va por horas enteras: laboral de 07 a 14. La de las 15 es fuera salvo su primer minuto. */
export function enHorarioLaboral(dia: number, hora: number): boolean {
  return dia <= 5 && hora >= HORA_INICIO_LABORAL && hora < HORA_FIN_LABORAL;
}

/** Cómo cae una casilla del mapa: dentro, fuera o en el borde (las 15, de lunes a viernes). */
export function horarioDeCasilla(dia: number, hora: number): "laboral" | "fuera" | "borde" {
  if (enHorarioLaboral(dia, hora)) return "laboral";
  return dia <= 5 && hora === HORA_FIN_LABORAL ? "borde" : "fuera";
}

export function dosDigitos(n: number): string {
  return String(n).padStart(2, "0");
}

/** "de 10:00 a 10:59". */
export function textoHora(hora: number): string {
  return `de ${dosDigitos(hora)}:00 a ${dosDigitos(hora)}:59`;
}

// ─── Meses ─────────────────────────────────────────────────────────────────

/** Con la primera letra en mayúscula (la de cada palabra con CSS daría «Mayo De 2026»). */
export function mayuscula(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** "2026-10" → "oct" y "2026"; `largo` → "octubre de 2026". */
export function partesMes(mes: string): { corto: string; anio: string; largo: string } {
  const [anio, numero] = mes.split("-").map(Number);
  const fecha = new Date(anio, numero - 1, 1);
  return {
    corto: fecha.toLocaleDateString("es-PA", { month: "short" }).replace(".", ""),
    anio: String(anio),
    largo: fecha.toLocaleDateString("es-PA", { month: "long", year: "numeric" }),
  };
}

// ─── La serie por día, mes o año ─────────────────────────────────────────────

export type Unidad = "dia" | "mes" | "anio";

export const UNIDADES: { id: Unidad; etiqueta: string; cada: string }[] = [
  { id: "dia",  etiqueta: "Día", cada: "día" },
  { id: "mes",  etiqueta: "Mes", cada: "mes" },
  { id: "anio", etiqueta: "Año", cada: "año" },
];

/** Los rótulos de un periodo de la serie, para el eje (`arriba` y `abajo`) y el globo (`largo`):
 *  "2026-10-05" → "5" y "oct" ("lunes 5 de octubre de 2026"); "2026-10" → "oct" y "2026"
 *  ("octubre de 2026"); "2026" → "2026" ("año 2026"). */
export function partesPeriodo(periodo: string): { arriba: string; abajo: string; largo: string } {
  const [anio, mes, dia] = periodo.split("-").map(Number);
  if (dia) {
    const fecha = new Date(anio, mes - 1, dia);
    const nombreMes = fecha.toLocaleDateString("es-PA", { month: "long" });
    return {
      arriba: String(dia),
      abajo: partesMes(periodo.slice(0, 7)).corto,
      largo: `${fecha.toLocaleDateString("es-PA", { weekday: "long" })} ${dia} de ${nombreMes} de ${anio}`,
    };
  }
  if (mes) {
    const p = partesMes(periodo);
    return { arriba: p.corto, abajo: p.anio, largo: p.largo };
  }
  return { arriba: String(anio), abajo: "", largo: `año ${anio}` };
}

// ─── Periodos del filtro ─────────────────────────────────────────────────────

export type Preset = "todo" | "30d" | "mes" | "mesPasado" | "anio";

export const PRESETS: { id: Preset; etiqueta: string }[] = [
  { id: "todo",      etiqueta: "Todo" },
  { id: "30d",       etiqueta: "Últimos 30 días" },
  { id: "mes",       etiqueta: "Este mes" },
  { id: "mesPasado", etiqueta: "Mes pasado" },
  { id: "anio",      etiqueta: "Este año" },
];

/** Fecha local (no UTC) en formato YYYY-MM-DD. */
export function fechaISO(d: Date): string {
  return `${d.getFullYear()}-${dosDigitos(d.getMonth() + 1)}-${dosDigitos(d.getDate())}`;
}

export function rangoDePreset(preset: Preset, hoy: Date): RangoFechas {
  const anio = hoy.getFullYear(), mes = hoy.getMonth();
  switch (preset) {
    case "todo":      return { desde: null, hasta: null };
    case "30d":       return { desde: fechaISO(new Date(anio, mes, hoy.getDate() - 29)), hasta: fechaISO(hoy) };
    case "mes":       return { desde: fechaISO(new Date(anio, mes, 1)), hasta: fechaISO(hoy) };
    case "mesPasado": return { desde: fechaISO(new Date(anio, mes - 1, 1)), hasta: fechaISO(new Date(anio, mes, 0)) };
    case "anio":      return { desde: fechaISO(new Date(anio, 0, 1)), hasta: fechaISO(hoy) };
  }
}

/** El preset que corresponde al rango, o null si es uno personalizado. */
export function presetDeRango(rango: RangoFechas, hoy: Date): Preset | null {
  return PRESETS.find(({ id }) => {
    const r = rangoDePreset(id, hoy);
    return r.desde === rango.desde && r.hasta === rango.hasta;
  })?.id ?? null;
}

function fechaLarga(iso: string, conAnio = true): { dia: number; mes: string; anio: number; texto: string } {
  const [anio, mes, dia] = iso.split("-").map(Number);
  const nombreMes = new Date(anio, mes - 1, 1).toLocaleDateString("es-PA", { month: "long" });
  return { dia, mes: nombreMes, anio, texto: `${dia} de ${nombreMes}${conAnio ? ` de ${anio}` : ""}` };
}

/** El periodo en palabras: "en todo el historial", "el 2 de noviembre de 2026",
 *  "del 1 al 31 de octubre de 2026", "desde el 5 de enero de 2026"… */
export function textoPeriodo(rango: RangoFechas): string {
  const { desde, hasta } = rango;
  if (!desde && !hasta) return "en todo el historial";
  if (desde && !hasta) return `desde el ${fechaLarga(desde).texto}`;
  if (!desde && hasta) return `hasta el ${fechaLarga(hasta).texto}`;
  const a = fechaLarga(desde as string), b = fechaLarga(hasta as string);
  if (desde === hasta) return `el ${a.texto}`;
  if (a.anio !== b.anio) return `del ${a.texto} al ${b.texto}`;
  if (a.mes !== b.mes) return `del ${a.dia} de ${a.mes} al ${b.texto}`;
  return `del ${a.dia} al ${b.texto}`;
}

// ─── Estados (la barra «¿En qué van?») ─────────────────────────────────────

/** Las series de los gráficos, con el color de la insignia de cada estado
 *  (`--graf-*` en globals.css) y el morado de «Fuera del horario». */
export type Serie = "revision" | "correccion" | "aprobada" | "denegada" | "finalizada" | "expirada" | "fuera";

export const SERIE_DE_ESTADO: Record<EstadoSolicitud, Serie> = {
  review: "revision", returned: "correccion", approved: "aprobada",
  denied: "denegada", finalized: "finalizada", expired: "expirada",
};

/** El orden de la barra es el del recorrido (lo terminado bien, lo que sigue en
 *  trámite, lo que no prosperó) y el de la validación de sus colores: cada uno
 *  se distingue de sus vecinos también con daltonismo. */
export const ESTADOS_BARRA: { estado: EstadoSolicitud; etiqueta: string; explicacion: string }[] = [
  { estado: "finalized", etiqueta: "Finalizadas",   explicacion: "El puesto de control cerró la operación." },
  { estado: "approved",  etiqueta: "Por finalizar", explicacion: "Aprobadas por UCVMM; falta que el puesto las finalice." },
  { estado: "review",    etiqueta: "En revisión",   explicacion: "Esperan la decisión de UCVMM." },
  { estado: "returned",  etiqueta: "En corrección", explicacion: "UCVMM las devolvió; la agencia debe corregirlas." },
  { estado: "expired",   etiqueta: "Expiradas",     explicacion: "Venció el plazo sin completarse." },
  { estado: "denied",    etiqueta: "Denegadas",     explicacion: "UCVMM no las autorizó." },
];

// ─── La unidad de la serie según el periodo ─────────────────────────────────

/** Cómo conviene ver la serie de un periodo: por día hasta un mes, por mes hasta
 *  un año y por año más allá; con «Todo» (sin desde), por mes. Cambia sola al
 *  elegir otro periodo (antes «Mes pasado» mostraba una sola columna) y se puede
 *  cambiar a mano; el PDF y la hoja «Resumen» del Excel usan la que se ve. */
export function unidadSugerida(rango: RangoFechas, hoy: Date): Unidad {
  if (!rango.desde) return "mes";
  const dia = (iso: string) => {
    const [a, m, d] = iso.split("-").map(Number);
    return Date.UTC(a, m - 1, d);
  };
  const hasta = rango.hasta ? dia(rango.hasta) : Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
  const dias = Math.round((hasta - dia(rango.desde)) / 86_400_000) + 1;
  return dias <= 31 ? "dia" : dias <= 366 ? "mes" : "anio";
}
