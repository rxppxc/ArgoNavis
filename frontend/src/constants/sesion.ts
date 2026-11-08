/**
 * Constantes de gestión de sesión.
 *
 * El backend emite tokens que vencen a los `ACCESS_TOKEN_EXPIRE_MINUTES`
 * (60 en producción). Mientras el usuario trabaja, el token se renueva antes de
 * vencer; tras 15 minutos sin actividad la sesión se cierra, con un aviso de
 * 2 minutos para que el usuario pueda extenderla. La inactividad es la de todas
 * las pestañas (utils/actividad.ts).
 */

export const AVISO_INACTIVIDAD_MS = 13 * 60 * 1000;  // mostrar modal a los 13 min de inactividad
export const LOGOUT_INACTIVIDAD_MS = 15 * 60 * 1000; // cerrar sesión a los 15 min de inactividad

/** Cada cuánto, como mucho, se anota la actividad para las demás pestañas (el
 *  mouse se mueve sin parar: anotarla en cada evento despertaría a todas). */
export const ANOTAR_ACTIVIDAD_MS = 5 * 1000;

/** Si al token le queda menos que esto, se renueva con la siguiente actividad
 *  del usuario. Es mayor que el cierre por inactividad: quien sigue en la
 *  página nunca se queda con un token vencido. */
export const MARGEN_RENOVACION_MS = LOGOUT_INACTIVIDAD_MS + 5 * 60 * 1000;
/** Cada cuánto, como mucho, se revisa si toca renovar (la actividad del mouse es continua). */
export const REVISION_RENOVACION_MS = 30 * 1000;

/** Cada cuánto consulta la campana (notificaciones internas) con la pestaña a
 *  la vista. No cuenta como actividad: no evita el cierre por inactividad. */
export const CONSULTA_PENDIENTES_MS = 60 * 1000;
