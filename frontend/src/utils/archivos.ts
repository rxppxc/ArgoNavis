/**
 * Validación de archivos en el cliente — única fuente de verdad del frontend.
 *
 * Mantener alineado con el backend (`EXTENSIONES_PERMITIDAS` y
 * `MAX_FILE_SIZE_MB` en transfer_service.py / config.py). El backend siempre
 * revalida; esto solo evita subir 50 MB para recibir un rechazo.
 */

export const EXTENSIONES_PERMITIDAS = [
  ".pdf", ".doc", ".docx", ".xls", ".xlsx",
  ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic", ".heif", ".avif",
];

/** Valor para el atributo `accept` de un <input type="file">. */
export const TIPOS_ACEPTADOS = EXTENSIONES_PERMITIDAS.join(",");

export const TAMANO_MAX_MB    = 50;
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
    return `Tipo de archivo no permitido: ${detalle}. Se aceptan PDF, Word, Excel e imágenes.`;
  }

  const grandes = archivos.filter(a => a.size > TAMANO_MAX_BYTES);
  if (grandes.length) {
    return `Los siguientes archivos superan el límite de ${TAMANO_MAX_MB} MB: ${grandes.map(a => a.name).join(", ")}`;
  }

  return null;
}
