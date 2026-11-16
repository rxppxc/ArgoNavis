/**
 * El «Volver» del expediente regresa a la página desde la que se abrió (2026-11-11): la
 * consulta histórica con sus filtros, las estadísticas o la pestaña de la bandeja. Antes
 * siempre llevaba al inicio, y la búsqueda de la consulta se perdía.
 *
 * La página de origen viaja en el estado de la navegación (`<Link state={...}>`), que el
 * navegador conserva al recargar y con Atrás/Adelante. Sin ella (un enlace de un correo,
 * la campana, una pestaña nueva), al inicio.
 *
 * El pasajero buscado en la consulta histórica no va en la URL (2026-11-14: quedaba en el
 * historial del navegador y en los logs del servidor): viaja también en ese estado, y el
 * «Volver» se lo devuelve a la consulta.
 */
export const INICIO = "/dashboard";

/** Lo que vuelve con el «Volver», además de la ruta. */
export interface ExtraVolver {
  pasajero?: string;
}

/** El estado que lleva un enlace al expediente: de dónde se abrió (y el pasajero buscado). */
export function estadoParaVolver(pathname: string, search = "", extra: ExtraVolver = {}): { volverA: string } & ExtraVolver {
  return { volverA: pathname + search, ...(extra.pasajero ? { pasajero: extra.pasajero } : {}) };
}

/** El pasajero que trae el estado de la navegación (al volver del expediente o al recargar
 *  la consulta). Como cualquiera puede armar el estado, solo un texto, con el tope del campo. */
export function pasajeroDelEstado(estado: unknown): string {
  const pasajero = typeof estado === "object" && estado !== null ? (estado as { pasajero?: unknown }).pasajero : undefined;
  return typeof pasajero === "string" ? pasajero.slice(0, 100) : "";
}

/** Lo que el «Volver» del expediente le devuelve a la página de origen. */
export function estadoDeVolver(estado: unknown): ExtraVolver | undefined {
  const pasajero = pasajeroDelEstado(estado);
  return pasajero ? { pasajero } : undefined;
}

/** A dónde vuelve el expediente. Solo una ruta de esta aplicación: el estado lo puede
 *  armar cualquiera (`history.pushState`), y «//otro.sitio» o «/\otro.sitio» el navegador
 *  los lee como otro servidor. */
export function destinoDeVolver(estado: unknown): string {
  const volverA = typeof estado === "object" && estado !== null ? (estado as { volverA?: unknown }).volverA : undefined;
  if (typeof volverA !== "string" || !volverA.startsWith("/")) return INICIO;
  if (volverA.startsWith("//") || volverA.startsWith("/\\")) return INICIO;
  return volverA;
}
