/** Texto de una celda de Excel para la vista previa (ModalPreview).
 *
 *  Las celdas de exceljs pueden traer string, número, fecha, fórmula
 *  ({result}) o texto enriquecido ({richText}) — nunca HTML, así que se
 *  vuelca como texto plano y React lo escapa solo al renderizarlo. */
export function celdaTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  // exceljs entrega las fechas a la medianoche en UTC: con la hora local salían
  // un día antes en Panamá. Día/mes/año, como en el resto del sistema.
  if (valor instanceof Date) {
    return Number.isNaN(valor.getTime()) ? "" : valor.toISOString().slice(0, 10).split("-").reverse().join("/");
  }
  if (typeof valor === "object") {
    const v = valor as { result?: unknown; text?: unknown; richText?: { text?: string }[] };
    if (Array.isArray(v.richText)) return v.richText.map(r => r.text ?? "").join("");
    if (v.result !== undefined) return celdaTexto(v.result);
    if (v.text !== undefined) return celdaTexto(v.text);
    return "";
  }
  return String(valor);
}
