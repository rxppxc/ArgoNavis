import { describe, expect, it } from "vitest";
import { INICIO, destinoDeVolver, estadoParaVolver } from "./volver";

describe("volver al origen del expediente", () => {
  it("regresa a la página de origen, con su búsqueda", () => {
    const estado = estadoParaVolver("/historico", "?pasajero=P%C3%A9rez&estado=finalized");
    expect(destinoDeVolver(estado)).toBe("/historico?pasajero=P%C3%A9rez&estado=finalized");
    expect(destinoDeVolver(estadoParaVolver("/admin/stats"))).toBe("/admin/stats");
  });

  it("sin origen (correo, campana, pestaña nueva), al inicio", () => {
    for (const estado of [null, undefined, {}, "texto", { volverA: 5 }, { desde: "/historico" }]) {
      expect(destinoDeVolver(estado)).toBe(INICIO);
    }
  });

  it("solo rutas de esta aplicación", () => {
    for (const volverA of ["https://otro.sitio", "//otro.sitio", "/\\otro.sitio", "javascript:alert(1)", "historico", ""]) {
      expect(destinoDeVolver({ volverA })).toBe(INICIO);
    }
  });
});
