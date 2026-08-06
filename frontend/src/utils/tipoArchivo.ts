/**
 * Clasificación de archivos por su tipo, usada en la vista pública de descarga
 * y en el modal de previsualización.
 */
export type CategoriaArchivo =
  | "imagen" | "pdf" | "word" | "excel" | "ppt"
  | "zip" | "video" | "audio" | "texto" | "otro";

export interface InfoTipo {
  etiqueta:   string;
  categoria:  CategoriaArchivo;
}

export function infoTipo(mime: string | null, nombre: string): InfoTipo {
  const m  = mime?.toLowerCase() ?? "";
  const ex = nombre.split(".").pop()?.toLowerCase() ?? "";

  if (m.startsWith("image/") || ["jpg","jpeg","png","gif","webp","bmp","svg","tiff","heic","heif","avif"].includes(ex))
    return { etiqueta: "IMG",   categoria: "imagen" };
  if (m === "application/pdf" || ex === "pdf")
    return { etiqueta: "PDF",   categoria: "pdf" };
  if (m.includes("wordprocessingml") || m === "application/msword" || ["doc","docx"].includes(ex))
    return { etiqueta: "WORD",  categoria: "word" };
  if (m.includes("spreadsheetml") || m.includes("ms-excel") || ["xls","xlsx","csv"].includes(ex))
    return { etiqueta: "XLS",   categoria: "excel" };
  if (m.includes("presentationml") || m.includes("ms-powerpoint") || ["ppt","pptx"].includes(ex))
    return { etiqueta: "PPT",   categoria: "ppt" };
  if (m.includes("zip") || m.includes("rar") || m.includes("7z") || m.includes("tar") || ["zip","rar","7z","tar","gz"].includes(ex))
    return { etiqueta: "ZIP",   categoria: "zip" };
  if (m.startsWith("video/") || ["mp4","mov","avi","mkv","webm"].includes(ex))
    return { etiqueta: "VIDEO", categoria: "video" };
  if (m.startsWith("audio/") || ["mp3","wav","ogg","flac"].includes(ex))
    return { etiqueta: "AUDIO", categoria: "audio" };
  if (m.startsWith("text/") || ["txt","md","xml","json"].includes(ex))
    return { etiqueta: "TXT",   categoria: "texto" };
  return { etiqueta: "FILE",  categoria: "otro" };
}

/** True si el navegador puede renderizar el archivo inline (img / iframe). */
export function esPrevisualizable(mime: string | null, nombre: string): boolean {
  const { categoria } = infoTipo(mime, nombre);
  return categoria === "imagen" || categoria === "pdf";
}
