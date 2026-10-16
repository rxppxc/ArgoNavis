/** Textos y formatos compartidos por las pantallas de solicitudes. */
import type { EstadoSolicitud, EventoSolicitud, RangoMarino, Sexo } from "../../api/solicitudes";

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
  militar:         "Militar",
  tecnico:         "Técnico",
  supernumerario:  "Supernumerario",
  superintendente: "Superintendente",
};

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
  devuelta:     "Devuelta a corrección",
  aprobada:     "Aprobada",
  negada:       "Denegada",
  comentario:   "Comentario del puesto de control",
  finalizada:   "Finalizada",
  expirada:     "Expirada",
};

/** Rangos que portan seamanbook (al resto no se le pide libreta). */
export const RANGOS_CON_LIBRETA: RangoMarino[] = ["marino"];

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
  const dosDigitos = (n: number) => String(n).padStart(2, "0");
  const hora = d.toLocaleTimeString("es-PA", { hour: "2-digit", minute: "2-digit" });
  return `${dosDigitos(d.getDate())}/${dosDigitos(d.getMonth() + 1)}/${d.getFullYear()}, ${hora}`;
}

/** Tiempo que falta hasta `iso`, en lenguaje corto ("1 día 4 h", "35 min"). */
export function tiempoRestante(iso: string | null | undefined): { texto: string; vencido: boolean } {
  if (!iso) return { texto: "—", vencido: false };
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { texto: "venció", vencido: true };
  const horas = Math.floor(ms / 3_600_000);
  const dias = Math.floor(horas / 24);
  if (dias > 0) return { texto: `${dias} día${dias === 1 ? "" : "s"} ${horas % 24} h`, vencido: false };
  if (horas > 0) return { texto: `${horas} h`, vencido: false };
  return { texto: `${Math.max(1, Math.floor(ms / 60_000))} min`, vencido: false };
}

/** Fecha de hoy en hora local, como "YYYY-MM-DD". */
export function hoyISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** IMO válido (7 dígitos, el último es el verificador). Devuelve los dígitos o null. */
export function normalizarImo(valor: string): string | null {
  const coincidencia = valor.trim().match(/^(?:IMO)?\s*(\d{7})$/i);
  if (!coincidencia) return null;
  const digitos = coincidencia[1];
  const suma = [7, 6, 5, 4, 3, 2].reduce((acc, peso, i) => acc + Number(digitos[i]) * peso, 0);
  return suma % 10 === Number(digitos[6]) ? digitos : null;
}
