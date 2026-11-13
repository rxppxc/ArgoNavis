/** Búsqueda de los selectores con buscador (`SelectorBuscable`, 2026-11-13): sin
 *  distinguir mayúsculas ni tildes, y con lo que empieza por lo escrito primero. */

export interface OpcionBuscable {
  /** Lo que se guarda (el código del país). */
  valor: string;
  /** Lo que se ve y se busca (el nombre del país). */
  texto: string;
}

/** «Panamá» → «panama»: sin tildes ni diéresis, en minúsculas y sin espacios de más. */
export function normalizarBusqueda(texto: string): string {
  return texto.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** Las opciones que coinciden con lo escrito, en este orden: el código exacto («PAN»),
 *  las que empiezan por lo escrito, las que tienen una palabra que empieza por lo
 *  escrito («unidos» → «Estados Unidos») y las que lo contienen («pan» → «España»).
 *  Dentro de cada grupo, el orden del catálogo. Sin nada escrito, todas. */
export function filtrarOpciones(opciones: OpcionBuscable[], consulta: string): OpcionBuscable[] {
  const buscado = normalizarBusqueda(consulta);
  if (!buscado) return opciones;
  const grupos: OpcionBuscable[][] = [[], [], [], []];
  for (const opcion of opciones) {
    const texto = normalizarBusqueda(opcion.texto);
    if (opcion.valor.toLowerCase() === buscado) grupos[0].push(opcion);
    else if (texto.startsWith(buscado)) grupos[1].push(opcion);
    else if (texto.split(/[\s(),.-]+/).some((palabra) => palabra.startsWith(buscado))) grupos[2].push(opcion);
    else if (texto.includes(buscado)) grupos[3].push(opcion);
  }
  return grupos.flat();
}

/** La opción que corresponde a lo escrito al salir del campo sin elegir de la lista:
 *  la que se llama así o tiene ese código, o la única que coincide. Si no, ninguna. */
export function opcionEscrita(opciones: OpcionBuscable[], consulta: string): OpcionBuscable | null {
  const buscado = normalizarBusqueda(consulta);
  if (!buscado) return null;
  const exacta = opciones.find((o) => normalizarBusqueda(o.texto) === buscado || o.valor.toLowerCase() === buscado);
  if (exacta) return exacta;
  const coincidencias = filtrarOpciones(opciones, consulta);
  return coincidencias.length === 1 ? coincidencias[0] : null;
}
