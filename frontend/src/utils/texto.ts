/** «Atlántico» → «Atlantico»: sin tildes ni diéresis (la ñ queda como n). Con NFD,
 *  como `sin_tildes` en el backend (core/texto.py): la política de contraseñas,
 *  que lo usa, está espejada allá. */
export function sinTildes(texto: string): string {
  return texto.normalize("NFD").replace(/\p{M}/gu, "");
}
