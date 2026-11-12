/**
 * El «Volver» del expediente regresa a la página desde la que se abrió (2026-11-11): la
 * consulta histórica con sus filtros, las estadísticas o la pestaña de la bandeja. Antes
 * siempre llevaba al inicio, y la búsqueda de la consulta se perdía.
 *
 * La página de origen viaja en el estado de la navegación (`<Link state={...}>`), que el
 * navegador conserva al recargar y con Atrás/Adelante. Sin ella (un enlace de un correo,
 * la campana, una pestaña nueva), al inicio.
 */
export const INICIO = "/dashboard";

/** El estado que lleva un enlace al expediente: de dónde se abrió. */
export function estadoParaVolver(pathname: string, search = ""): { volverA: string } {
  return { volverA: pathname + search };
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
