/**
 * Lo que dice cada aviso emergente, sin React (diseño «sello centrado», elegido por el
 * usuario el 2026-11-11): su sello, cuánto dura, si se anuncia enseguida, el texto con el
 * número de solicitud aparte y la cola. Lo usa Notificaciones.tsx; las pruebas, avisos.test.ts.
 */
export type TipoNotificacion = "exito" | "error" | "info" | "aviso";

/** El estado al que pasó la solicitud: el aviso lleva su sello, en el color de su insignia. */
export type SelloSolicitud = "enviada" | "reenviada" | "devuelta" | "aprobada" | "denegada" | "finalizada";

/** El sello de un aviso: el estado de la solicitud o, sin solicitud de por medio, una versión
 *  nueva desplegada con la página abierta (VigilanteVersion). */
export type SelloAviso = SelloSolicitud | "version";

const SELLO_DEL_TIPO: Record<TipoNotificacion, string> = {
  exito: "Listo", aviso: "Revisa", error: "No se pudo", info: "Aviso",
};

const TEXTO_DEL_SELLO: Record<SelloAviso, string> = {
  enviada: "Enviada", reenviada: "Reenviada", devuelta: "Devuelta",
  aprobada: "Aprobada", denegada: "Denegada", finalizada: "Finalizada",
  version: "Versión nueva",
};

/** El texto del sello: el estado al que pasó la solicitud o, si no, el tipo de aviso. */
export function textoDelSello(tipo: TipoNotificacion, sello?: SelloAviso): string {
  return sello ? TEXTO_DEL_SELLO[sello] : SELLO_DEL_TIPO[tipo];
}

/** Errores y validaciones: el lector de pantalla los anuncia enseguida (los éxitos, sin interrumpir). */
export function esUrgente(tipo: TipoNotificacion): boolean {
  return tipo === "error" || tipo === "aviso";
}

/** Errores y validaciones quedan más: hay que alcanzar a leerlos (y a oírlos). */
const DURACION_MS: Record<TipoNotificacion, number> = { exito: 4000, info: 4000, error: 10000, aviso: 10000 };
/** El resultado de una decisión trae más que leer (el número y, al devolver, el plazo). */
const DURACION_CON_SELLO_MS = 6000;

export function duracionDe(tipo: TipoNotificacion, sello?: SelloAviso): number {
  return sello ? DURACION_CON_SELLO_MS : DURACION_MS[tipo];
}

const NUMERO_DE_SOLICITUD = /(AM-\d{4}-\d+)/;

const ESPACIO_FIJO = " ";

/** El texto en pedazos, con el número de solicitud aparte: va en letra de máquina y sin
 *  partirse. La hora tampoco se parte: «10:30 a. m.» va con espacios que no cortan línea. */
export function partesDelTexto(texto: string): { texto: string; numero: boolean }[] {
  const sinCortes = texto.replace(/(\d) ([ap])\. m\./g, `$1${ESPACIO_FIJO}$2.${ESPACIO_FIJO}m.`);
  return sinCortes.split(NUMERO_DE_SOLICITUD).filter(Boolean)
    .map((parte) => ({ texto: parte, numero: NUMERO_DE_SOLICITUD.test(parte) }));
}

/** Como mucho tres a la vez, el más nuevo arriba. Uno repetido (mismo texto y tipo) no se
 *  apila: el nuevo reemplaza al anterior y su tiempo empieza de nuevo. */
export const MAX_AVISOS = 3;

export function agregarAviso<T extends { texto: string; tipo: TipoNotificacion }>(lista: T[], nuevo: T): T[] {
  return [nuevo, ...lista.filter((m) => !(m.texto === nuevo.texto && m.tipo === nuevo.tipo))].slice(0, MAX_AVISOS);
}
