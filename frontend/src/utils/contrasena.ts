/**
 * Política de contraseñas de las cuentas locales (las del AD siguen la del
 * dominio). Espejo de `problema_de_contrasena` en
 * backend/app/domain/schemas/user.py: si cambias una, cambia la otra.
 */
export const LARGO_MINIMO_CONTRASENA = 12;
export const LARGO_MAXIMO_CONTRASENA = 64;

/** Lo primero que prueba cualquiera (se compara sin tildes ni mayúsculas). */
const PALABRAS_PROHIBIDAS = ["password", "contrasena", "qwerty", "123456", "navis", "migracion", "panama"];

const normalizar = (texto: string) => texto.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

const tieneMayuscula = (c: string) => /\p{Lu}/u.test(c);
const tieneMinuscula = (c: string) => /\p{Ll}/u.test(c);
const tieneNumero    = (c: string) => /\p{Nd}/u.test(c);
const tieneEspecial  = (c: string) => /[^\p{L}\p{N}\s]/u.test(c);

export interface RequisitoContrasena {
  texto:  string;
  cumple: boolean;
}

/** Los requisitos que se muestran bajo el campo, con su estado. */
export function requisitosContrasena(clave: string): RequisitoContrasena[] {
  return [
    { texto: `${LARGO_MINIMO_CONTRASENA} caracteres o más`, cumple: clave.length >= LARGO_MINIMO_CONTRASENA },
    { texto: "Una mayúscula", cumple: tieneMayuscula(clave) },
    { texto: "Una minúscula", cumple: tieneMinuscula(clave) },
    { texto: "Un número", cumple: tieneNumero(clave) },
    { texto: "Un carácter especial (! # % - . @)", cumple: tieneEspecial(clave) },
  ];
}

/** El primer requisito que no cumple, con el mismo texto que el backend; null si la cumple. */
export function problemaContrasena(clave: string, usuario?: string): string | null {
  if (clave.length < LARGO_MINIMO_CONTRASENA) {
    return `La contraseña debe tener al menos ${LARGO_MINIMO_CONTRASENA} caracteres.`;
  }
  if (clave.length > LARGO_MAXIMO_CONTRASENA || new TextEncoder().encode(clave).length > 72) {
    return `La contraseña es demasiado larga (máximo ${LARGO_MAXIMO_CONTRASENA} caracteres).`;
  }
  if (!tieneMayuscula(clave)) return "La contraseña debe tener al menos una mayúscula.";
  if (!tieneMinuscula(clave)) return "La contraseña debe tener al menos una minúscula.";
  if (!tieneNumero(clave)) return "La contraseña debe tener al menos un número.";
  if (!tieneEspecial(clave)) return "La contraseña debe tener al menos un carácter especial (por ejemplo ! # % - . @).";
  const normal = normalizar(clave);
  const nombre = (usuario ?? "").trim();
  if (nombre.length >= 3 && normal.includes(normalizar(nombre))) {
    return "La contraseña no puede contener el nombre de usuario.";
  }
  if (PALABRAS_PROHIBIDAS.some((palabra) => normal.includes(palabra))) {
    return "La contraseña no puede contener palabras fáciles de adivinar (password, navis, 123456…).";
  }
  return null;
}
