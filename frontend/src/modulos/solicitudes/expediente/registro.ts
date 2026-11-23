/** El historial completo de una solicitud, sin React (2026-11-22). */
import type { ArchivoRegistro, ArchivoVisible, VersionSolicitud } from "../../../api/solicitudes";
import { formatearFecha, formatearFechaHora } from "../presentacion";

export function estadoArchivo(a: ArchivoRegistro): string {
  if (a.clase === "emitido") return "Emitida";
  // La hora del servidor, en la fecha de quien mira, como el resto del expediente.
  return a.retirado_en ? `Retirado el ${formatearFechaHora(a.retirado_en).split(",")[0]}` : "Vigente";
}

/** Lo que pide la vista previa: un documento (también retirado) o una autorización emitida. */
export function archivoVisible(a: Pick<ArchivoRegistro, "clase" | "id" | "nombre" | "tipo_mime">): ArchivoVisible {
  return { id: a.id, nombre_original: a.nombre, tipo_mime: a.tipo_mime, emitido: a.clase === "emitido" };
}

/** Quién la envió, quién la devolvió y quién la corrigió, en orden. */
export function pasosDeLaVersion(v: VersionSolicitud): string[] {
  const paso = (que: string, cuando: string | null, quien: string | null) =>
    cuando ? `${que} el ${formatearFechaHora(cuando)}${quien ? ` por ${quien}` : ""}` : null;
  return [
    paso("Enviada", v.enviada_en, v.enviada_por),
    paso("Devuelta", v.devuelta_en, v.devuelta_por),
    paso("Corregida", v.corregida_en, v.corregida_por),
  ].filter((p): p is string => p !== null);
}

/** Las versiones se guardan desde este día: antes, corregir borraba lo enviado. */
const DESDE = formatearFecha("2026-11-22");

export function textoSinVersion(cuantas: number): string | null {
  if (cuantas === 0) return null;
  return cuantas === 1
    ? `Una corrección de antes del ${DESDE} no guardó lo que se había enviado.`
    : `${cuantas} correcciones de antes del ${DESDE} no guardaron lo que se había enviado.`;
}
