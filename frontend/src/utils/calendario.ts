/**
 * El calendario propio del sistema (SelectorFecha, 2026-11-23), sin React: armar el mes,
 * leer lo que se escribe, la máscara dd/mm/aaaa y el rango permitido.
 *
 * Las fechas van como AAAA-MM-DD (lo que guarda el formulario y espera la API) y se
 * calculan en UTC: una fecha sin hora no debe correrse de día por la zona horaria.
 * El mes va de 0 a 11, como en Date.
 */

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
] as const;

/** La semana empieza en domingo, como en los calendarios de Panamá. */
export const DIAS_SEMANA = ["do", "lu", "ma", "mi", "ju", "vi", "sá"] as const;

const FECHA_LARGA = new Intl.DateTimeFormat("es-PA", {
  weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
});

const dos = (n: number) => String(n).padStart(2, "0");

export function isoDe(anio: number, mes: number, dia: number): string {
  const d = new Date(Date.UTC(anio, mes, dia));
  return `${d.getUTCFullYear()}-${dos(d.getUTCMonth() + 1)}-${dos(d.getUTCDate())}`;
}

/** Año, mes (0 a 11) y día de una fecha AAAA-MM-DD que existe; null si no. */
export function partesDe(iso: string | null | undefined): { anio: number; mes: number; dia: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  if (!m) return null;
  const [anio, mes, dia] = [Number(m[1]), Number(m[2]) - 1, Number(m[3])];
  const d = new Date(Date.UTC(anio, mes, dia));
  return d.getUTCFullYear() === anio && d.getUTCMonth() === mes && d.getUTCDate() === dia ? { anio, mes, dia } : null;
}

export function sumarDias(iso: string, dias: number): string {
  const p = partesDe(iso);
  return p ? isoDe(p.anio, p.mes, p.dia + dias) : iso;
}

/** El mismo día, n meses después (o antes); si ese día no existe, el último del mes. */
export function sumarMeses(iso: string, meses: number): string {
  const p = partesDe(iso);
  if (!p) return iso;
  const ultimo = new Date(Date.UTC(p.anio, p.mes + meses + 1, 0)).getUTCDate();
  return isoDe(p.anio, p.mes + meses, Math.min(p.dia, ultimo));
}

/** Las 6 semanas que muestra el calendario, de domingo a sábado, con los días de los
 *  meses vecinos para completarlas. */
export function semanasDelMes(anio: number, mes: number): string[][] {
  const primero = new Date(Date.UTC(anio, mes, 1)).getUTCDay();
  return Array.from({ length: 6 }, (_, semana) =>
    Array.from({ length: 7 }, (_, dia) => isoDe(anio, mes, 1 - primero + semana * 7 + dia)));
}

/** Mientras se escribe: las barras se ponen solas (2611 → 26/11) y se respetan las que
 *  escribe la persona (1/5/2026). Una fecha AAAA-MM-DD pegada queda tal cual. */
export function enmascarar(texto: string): string {
  if (/^\d{4}-\d{0,2}(-\d{0,2})?$/.test(texto)) return texto;
  const tramos = ["", "", ""];
  const maximo = [2, 2, 4];
  let i = 0;
  let abiertos = 1;
  for (const c of texto.replace(/[.-]/g, "/")) {
    if (c === "/") {
      if (tramos[i] && i < 2) { i += 1; abiertos = i + 1; }
      continue;
    }
    if (!/\d/.test(c)) continue;
    if (tramos[i].length === maximo[i]) {
      if (i === 2) continue;
      i += 1;
      abiertos = i + 1;
    }
    tramos[i] += c;
  }
  return tramos.slice(0, abiertos).join("/");
}

/** Lo escrito como AAAA-MM-DD: dd/mm/aaaa (con uno o dos dígitos) o AAAA-MM-DD pegada.
 *  null si está incompleto o la fecha no existe. */
export function textoAIso(texto: string): string | null {
  const t = texto.trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
  const dmy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(t);
  const candidato = iso ? t : dmy ? `${dmy[3]}-${dos(Number(dmy[2]))}-${dos(Number(dmy[1]))}` : "";
  return partesDe(candidato) ? candidato : null;
}

export function isoATexto(iso: string | null | undefined): string {
  const p = partesDe(iso);
  return p ? `${dos(p.dia)}/${dos(p.mes + 1)}/${p.anio}` : "";
}

/** De qué lado del rango permitido cae la fecha, o null si está dentro. */
export function fueraDeRango(iso: string, min?: string, max?: string): "antes" | "despues" | null {
  if (min && iso < min) return "antes";
  if (max && iso > max) return "despues";
  return null;
}

/** La fecha llevada al borde más cercano del rango. */
export function acotar(iso: string, min?: string, max?: string): string {
  if (min && iso < min) return min;
  if (max && iso > max) return max;
  return iso;
}

/** El mes que muestra el calendario al abrir: el de la fecha elegida; sin ella, el de hoy
 *  si se puede elegir, o el del borde más cercano. */
export function vistaInicial(valor: string, hoy: string, min?: string, max?: string): { anio: number; mes: number } {
  const p = partesDe(valor) ?? partesDe(acotar(hoy, min, max)) ?? partesDe(hoy);
  return p ? { anio: p.anio, mes: p.mes } : { anio: 2026, mes: 0 };
}

/** Los años del selector: del borde de abajo al de arriba (sin bordes, cien años atrás y
 *  veinte adelante). Un rango largo, como el del nacimiento, del más reciente al más antiguo. */
export function aniosDisponibles(hoy: string, min?: string, max?: string): number[] {
  const actual = partesDe(hoy)?.anio ?? 2026;
  const desde = partesDe(min)?.anio ?? actual - 100;
  const hasta = partesDe(max)?.anio ?? actual + 20;
  const anios = Array.from({ length: hasta - desde + 1 }, (_, i) => desde + i);
  return hasta - desde > 15 ? anios.reverse() : anios;
}

/** «jueves, 26 de noviembre de 2026»; vacío si la fecha no existe. */
export function fechaLarga(iso: string | null | undefined): string {
  const p = partesDe(iso);
  return p ? FECHA_LARGA.format(new Date(Date.UTC(p.anio, p.mes, p.dia))) : "";
}
