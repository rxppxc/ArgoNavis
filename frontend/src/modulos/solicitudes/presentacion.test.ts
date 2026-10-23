import { describe, expect, it } from "vitest";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import { normalizarImo } from "./presentacion";

interface CasoImo extends Caso {
  valor: string;
  esperado: string | null;
}

describe("normalizarImo (espejo de normalizar_imo)", () => {
  it.each(leerEspejo<CasoImo[]>("imo.json"))("$caso", ({ valor, esperado }) => {
    expect(normalizarImo(valor)).toBe(esperado);
  });
});
