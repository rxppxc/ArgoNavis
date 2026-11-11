import { describe, expect, it } from "vitest";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import { fechaEnPalabras, normalizarImo, TEXTO_HORARIO_LABORAL } from "./presentacion";

describe("TEXTO_HORARIO_LABORAL", () => {
  it("dice lo mismo que el correo y el PDF (TEXTO_HORARIO de core/horario.py)", () => {
    expect(TEXTO_HORARIO_LABORAL).toBe("lunes a viernes, de 07:00 a 15:00");
  });
});

interface CasoImo extends Caso {
  valor: string;
  esperado: string | null;
}

describe("normalizarImo (espejo de normalizar_imo)", () => {
  it.each(leerEspejo<CasoImo[]>("imo.json"))("$caso", ({ valor, esperado }) => {
    expect(normalizarImo(valor)).toBe(esperado);
  });
});

describe("fechaEnPalabras", () => {
  it("dice la fecha en palabras, sin correrse de día por la zona horaria", () => {
    expect(fechaEnPalabras("2026-11-13")).toBe("viernes, 13 de noviembre de 2026");
    expect(fechaEnPalabras("2026-01-01")).toBe("jueves, 1 de enero de 2026");
    expect(fechaEnPalabras("1988-03-14")).toBe("lunes, 14 de marzo de 1988");
  });

  it("sin fecha o con una que no existe, nada", () => {
    expect(fechaEnPalabras("")).toBe("");
    expect(fechaEnPalabras(null)).toBe("");
    expect(fechaEnPalabras("2026-02-31")).toBe("");
    expect(fechaEnPalabras("13/11/2026")).toBe("");
  });
});
