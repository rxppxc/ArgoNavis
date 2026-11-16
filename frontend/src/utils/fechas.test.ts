import { describe, expect, it } from "vitest";
import { dosCifras, fechaISOLocal } from "./fechas";
import { sinTildes } from "./texto";

describe("fechas", () => {
  it("dosCifras completa con un cero", () => {
    expect(dosCifras(5)).toBe("05");
    expect(dosCifras(12)).toBe("12");
  });

  it("fechaISOLocal da el día local, no el de UTC", () => {
    // Las 11 p. m. locales del 14/11: en Panamá (UTC-5), toISOString ya daría el 15.
    expect(fechaISOLocal(new Date(2026, 10, 14, 23, 0))).toBe("2026-11-14");
    expect(fechaISOLocal(new Date(2026, 0, 3))).toBe("2026-01-03");
  });
});

describe("sinTildes", () => {
  it("quita tildes y diéresis, y deja la ñ como n", () => {
    expect(sinTildes("Atlántico Pingüino Ñandú")).toBe("Atlantico Pinguino Nandu");
  });
});
