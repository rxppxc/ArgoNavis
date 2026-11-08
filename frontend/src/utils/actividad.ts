/**
 * Última actividad del usuario en cualquier pestaña de ARGO NAVIS (ms desde
 * epoch). Vive en localStorage, como el token, y el cierre por inactividad mira
 * esta: antes cada pestaña medía la suya y una olvidada cerraba a los 15 minutos
 * la sesión de la que se estaba usando (borraba el token, que es de todas).
 *
 * No se borra al cerrar la sesión: las demás pestañas lo leerían como 15
 * minutos sin actividad. Cada sesión anota la suya al empezar.
 */
export const CLAVE_ACTIVIDAD = "ultima-actividad";

export function leerActividad(): number {
  return Number(localStorage.getItem(CLAVE_ACTIVIDAD)) || 0;
}

/** Anota actividad ahora. Las demás pestañas se enteran por el evento `storage`. */
export function anotarActividad(): void {
  localStorage.setItem(CLAVE_ACTIVIDAD, String(Date.now()));
}
