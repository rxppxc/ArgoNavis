/**
 * Casos compartidos con el backend (backend/tests/espejo/*.json): las mismas
 * reglas corren en pytest (test_espejo.py) y en Vitest. Si una regla cambia de
 * un solo lado, falla una de las dos pruebas.
 */
import { readFileSync } from "node:fs";

export function leerEspejo<T>(archivo: string): T {
  const ruta = new URL(`../../../backend/tests/espejo/${archivo}`, import.meta.url);
  return JSON.parse(readFileSync(ruta, "utf-8")) as T;
}

/** Nombre de cada caso, para que la prueba que falla diga cuál fue. */
export interface Caso {
  caso: string;
}
