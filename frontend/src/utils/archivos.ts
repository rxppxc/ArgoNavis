/**
 * Validación de archivos en el cliente — única fuente de verdad del frontend.
 *
 * Mantener alineado con el backend (`EXTENSIONES_PERMITIDAS` y
 * `TAMANO_MAXIMO_MB` en infrastructure/almacenamiento.py). El backend siempre
 * revalida; esto solo evita subir un archivo para recibir un rechazo.
 */
import { formatBytes } from "./format";

/** Formatos del expediente: PDF, Word y Excel. El backend además verifica que
 *  el contenido corresponda al formato y que los de Office no traigan macros. */
export const EXTENSIONES_PERMITIDAS = [".pdf", ".doc", ".docx", ".xls", ".xlsx"];

/** Valor para el atributo `accept` de un <input type="file">. */
export const TIPOS_ACEPTADOS = [
  ...EXTENSIONES_PERMITIDAS,
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
].join(",");

/** Tope por archivo, para cualquier formato (decisión del usuario, 2026-10-16). */
export const TAMANO_MAX_MB    = 2;
export const TAMANO_MAX_BYTES = TAMANO_MAX_MB * 1024 * 1024;

function extensionDe(nombre: string): string {
  const punto = nombre.lastIndexOf(".");
  return punto === -1 ? "" : nombre.slice(punto).toLowerCase();
}

/**
 * Valida una lista de archivos contra las reglas del sistema.
 * Devuelve un mensaje de error listo para mostrar, o `null` si todo está bien.
 */
export function validarArchivos(archivos: File[]): string | null {
  const invalidos = archivos.filter(a => !EXTENSIONES_PERMITIDAS.includes(extensionDe(a.name)));
  if (invalidos.length) {
    const detalle = invalidos.map(a => a.name).join(", ");
    return `Solo se aceptan archivos PDF, Word o Excel: ${detalle}.`;
  }

  const grandes = archivos.filter(a => a.size > TAMANO_MAX_BYTES);
  if (grandes.length) {
    const detalle = grandes.map(a => `${a.name} (${formatBytes(a.size)})`).join(", ");
    return `Cada archivo puede pesar hasta ${TAMANO_MAX_MB} MB. Pesan más: ${detalle}.`;
  }

  return null;
}
