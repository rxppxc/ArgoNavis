/** Mensaje legible de un error de la API (campo `detail` de FastAPI).
 *  `detail` puede ser texto o, en errores 422 de validación, una lista. */
export function mensajeDeError(error: unknown, porDefecto: string): string {
  const detalle = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detalle === "string" && detalle.trim()) return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) {
    return detalle
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return porDefecto;
}
