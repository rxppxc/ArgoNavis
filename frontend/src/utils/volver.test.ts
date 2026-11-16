import { describe, expect, it } from "vitest";
import { INICIO, destinoDeVolver, estadoDeVolver, estadoParaVolver, pasajeroDelEstado } from "./volver";

describe("volver al origen del expediente", () => {
  it("regresa a la página de origen, con su búsqueda", () => {
    const estado = estadoParaVolver("/historico", "?texto=ESTRELLA&estado=finalized");
    expect(destinoDeVolver(estado)).toBe("/historico?texto=ESTRELLA&estado=finalized");
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

describe("el pasajero de la consulta histórica viaja en el estado, no en la URL (2026-11-14)", () => {
  it("va al expediente y vuelve con el «Volver»", () => {
    const estado = estadoParaVolver("/historico", "?estado=finalized", { pasajero: "Pérez" });
    expect(destinoDeVolver(estado)).toBe("/historico?estado=finalized");
    expect(estadoDeVolver(estado)).toEqual({ pasajero: "Pérez" });
    expect(estadoParaVolver("/historico", "", { pasajero: "" })).toEqual({ volverA: "/historico" });
  });

  it("solo un texto, con el tope del campo", () => {
    expect(pasajeroDelEstado({ pasajero: 5 })).toBe("");
    expect(pasajeroDelEstado(null)).toBe("");
    expect(pasajeroDelEstado({ pasajero: "x".repeat(150) })).toHaveLength(100);
    expect(estadoDeVolver({ volverA: "/historico" })).toBeUndefined();
  });
});
