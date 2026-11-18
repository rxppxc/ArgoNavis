/**
 * El avance del formulario de solicitud (rediseño visual del 2026-11-17, pedido del usuario:
 * que nadie se pierda): los cuatro pasos obligatorios, cada uno listo o con lo que le falta.
 * Sale de lo mismo que ya valida el formulario (validarFormulario) y de las casillas sin
 * archivo (useDocumentosFormulario); no agrega reglas.
 */
export interface PasoAvance {
  numero: number;
  titulo: string;
  completo: boolean;
  detalle: string;
  /** El id de su sección, para ir a ella. */
  ancla: string;
}

const LISTO = "Listo";
const plural = (n: number, uno: string, varios: string) => (n === 1 ? uno : varios);

/** Los avisos que son de la lista de tripulantes y no de uno en particular. */
function esDeLaLista(error: string): boolean {
  return error.startsWith("Registra al menos un tripulante") || error.startsWith("Una solicitud admite hasta");
}

export function avanceFormulario({ tipoElegido, errores, faltantes }: {
  tipoElegido: boolean; errores: string[]; faltantes: number;
}): PasoAvance[] {
  if (!tipoElegido) {
    const antes = "Primero elige el trámite";
    return [
      { numero: 1, titulo: "Tipo de trámite", completo: false, detalle: "Elige el trámite", ancla: "paso-tramite" },
      { numero: 2, titulo: "Datos del trámite", completo: false, detalle: antes, ancla: "paso-datos" },
      { numero: 3, titulo: "Tripulantes", completo: false, detalle: antes, ancla: "paso-tripulantes" },
      { numero: 4, titulo: "Documentos", completo: false, detalle: antes, ancla: "paso-documentos" },
    ];
  }

  const deDatos = errores.filter((e) => !e.startsWith("Tripulante") && !esDeLaLista(e)).length;
  const tripulantes = new Set(errores.map((e) => /^Tripulante (\d+)/.exec(e)?.[1]).filter(Boolean)).size;
  const deLaLista = errores.filter(esDeLaLista).length;

  return [
    { numero: 1, titulo: "Tipo de trámite", completo: true, detalle: LISTO, ancla: "paso-tramite" },
    {
      numero: 2, titulo: "Datos del trámite", completo: deDatos === 0, ancla: "paso-datos",
      detalle: deDatos === 0 ? LISTO : `${plural(deDatos, "Falta", "Faltan")} ${deDatos} ${plural(deDatos, "dato", "datos")}`,
    },
    {
      numero: 3, titulo: "Tripulantes", completo: tripulantes === 0 && deLaLista === 0, ancla: "paso-tripulantes",
      detalle: tripulantes > 0 ? `${tripulantes} ${plural(tripulantes, "tripulante", "tripulantes")} por completar`
        : deLaLista > 0 ? `${deLaLista} ${plural(deLaLista, "aviso", "avisos")} por revisar` : LISTO,
    },
    {
      numero: 4, titulo: "Documentos", completo: faltantes === 0, ancla: "paso-documentos",
      detalle: faltantes === 0 ? LISTO
        : `${plural(faltantes, "Falta", "Faltan")} ${faltantes} ${plural(faltantes, "documento", "documentos")}`,
    },
  ];
}
