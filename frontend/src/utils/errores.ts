/** Sin respuesta del servidor: sin red, la VPN caída o el backend apagado. */
export const MENSAJE_SIN_CONEXION =
  "No hay conexión con el servidor. Revisa tu conexión (o la VPN) e intenta de nuevo.";
/** Se agotó el tiempo de espera de la petición. */
export const MENSAJE_SIN_RESPUESTA =
  "El servidor tardó demasiado en responder. Intenta de nuevo en unos segundos.";
/** nginx sin backend (502, 504) o un 503 sin motivo. */
export const MENSAJE_NO_DISPONIBLE =
  "El sistema no está disponible en este momento. Intenta de nuevo en unos minutos.";

type ErrorDeApi = {
  response?: { status?: number; data?: { detail?: unknown } };
  request?: unknown;
  code?: string;
};

/** Mensaje legible de un error de la API (campo `detail` de FastAPI).
 *  `detail` puede ser texto o, en errores 422 de validación, una lista.
 *  Sin `detail`, si el servidor no respondió o no está disponible lo dice
 *  (antes cada pantalla mostraba su texto genérico, «No se pudo enviar…», y no
 *  se sabía que era la conexión); en los demás casos, `porDefecto`. */
export function mensajeDeError(error: unknown, porDefecto: string): string {
  const e = error as ErrorDeApi | null;
  const detalle = e?.response?.data?.detail;
  if (typeof detalle === "string" && detalle.trim()) return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) {
    return detalle
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  if (e && !e.response && e.request) {
    return e.code === "ECONNABORTED" || e.code === "ETIMEDOUT" ? MENSAJE_SIN_RESPUESTA : MENSAJE_SIN_CONEXION;
  }
  const estado = e?.response?.status;
  if (estado === 502 || estado === 503 || estado === 504) return MENSAJE_NO_DISPONIBLE;
  return porDefecto;
}
