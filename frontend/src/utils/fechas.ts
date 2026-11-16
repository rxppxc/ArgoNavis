/** «05»: horas, días y meses en las fechas que se arman a mano. */
export function dosCifras(n: number): string {
  return String(n).padStart(2, "0");
}

/** La fecha local (no la de UTC) como AAAA-MM-DD, la de los `<input type="date">`.
 *  `toISOString` daría la de Greenwich: en Panamá, desde las 7 p. m., el día siguiente. */
export function fechaISOLocal(d: Date = new Date()): string {
  return `${d.getFullYear()}-${dosCifras(d.getMonth() + 1)}-${dosCifras(d.getDate())}`;
}
