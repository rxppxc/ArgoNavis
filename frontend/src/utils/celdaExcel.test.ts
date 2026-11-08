import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { celdaTexto } from "./celdaExcel";

describe("celdas de Excel en la vista previa", () => {
  // En Panamá (UTC-5) la medianoche UTC todavía es el día anterior: ahí fallaba.
  beforeEach(() => { vi.stubEnv("TZ", "America/Panama"); });
  afterEach(() => { vi.unstubAllEnvs(); });

  it("las fechas salen el mismo día que en el Excel, en día/mes/año", () => {
    expect(celdaTexto(new Date(Date.UTC(2026, 9, 31)))).toBe("31/10/2026");
    expect(celdaTexto(new Date(Date.UTC(2027, 0, 1)))).toBe("01/01/2027");
  });

  it("una fecha inválida queda vacía", () => {
    expect(celdaTexto(new Date(Number.NaN))).toBe("");
  });

  it("fórmulas, texto enriquecido, números y vacíos", () => {
    expect(celdaTexto({ result: 42 })).toBe("42");
    expect(celdaTexto({ richText: [{ text: "Juan " }, { text: "Pérez" }] })).toBe("Juan Pérez");
    expect(celdaTexto({ text: "enlace" })).toBe("enlace");
    expect(celdaTexto(null)).toBe("");
    expect(celdaTexto(undefined)).toBe("");
    expect(celdaTexto(3.5)).toBe("3.5");
  });
});
