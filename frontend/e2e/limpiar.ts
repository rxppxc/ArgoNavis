/** Al terminar: borra la BD temporal del backend de prueba. Playwright corta el
 *  servidor sin dejarlo cerrar (en Windows), así que la limpieza va aparte. */
import { execFileSync } from "node:child_process";
import path from "node:path";
import { PYTHON } from "../playwright.config";

export default function limpiar() {
  execFileSync(PYTHON, ["tests/servidor_e2e.py", "--limpiar"], {
    cwd: path.resolve(import.meta.dirname, "..", "..", "backend"),
    stdio: "inherit",
  });
}
