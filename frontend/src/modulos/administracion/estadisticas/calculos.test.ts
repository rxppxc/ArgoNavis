import { describe, expect, it } from "vitest";
import {
  duracion, enHorarioLaboral, escalaEje, horarioDeCasilla, nivelCalor, partesPeriodo, porcentaje, presetDeRango,
  rangoDePreset, textoPeriodo, unidadSugerida,
} from "./calculos";

describe("porcentaje", () => {
  it.each([
    [1, 4, "25 %"],
    [0, 4, "0 %"],
    [1, 300, "<1 %"],
    [299, 300, "99 %"],   // le falta una: no puede decir 100 %
    [300, 300, "100 %"],
    [3, 0, "—"],
  ])("%i de %i = %s", (parte, total, esperado) => {
    expect(porcentaje(parte, total)).toBe(esperado);
  });
});

describe("duracion", () => {
  it.each([
    [0.5, "30 min"],
    [6.4, "6 h 24 min"],
    [5, "5 h"],
    [47.9, "47 h 54 min"],
    [51, "2 días y 3 h"],
    [72, "3 días"],
    [null, "—"],
  ])("%s h = %s", (horas, esperado) => {
    expect(duracion(horas)).toBe(esperado);
  });
});

describe("escalaEje", () => {
  it.each([
    [27, 30, [0, 10, 20, 30]],
    [128, 150, [0, 50, 100, 150]],
    [3, 3, [0, 1, 2, 3]],
    [1, 1, [0, 1]],
    [0, 1, [0, 1]],
  ])("máximo %i → tope %i", (maximo, tope, marcas) => {
    expect(escalaEje(maximo)).toEqual({ tope, marcas });
  });
});

describe("nivelCalor", () => {
  it("cero es vacío; lo demás va de 1 a 5 según el máximo", () => {
    expect([0, 1, 2, 5, 9, 10].map((v) => nivelCalor(v, 10))).toEqual([0, 1, 1, 3, 5, 5]);
    expect(nivelCalor(3, 0)).toBe(0);
  });
});

describe("horario laboral", () => {
  it("el mapa va por horas enteras: laboral de 07 a 14, de lunes a viernes", () => {
    expect(enHorarioLaboral(1, 7)).toBe(true);
    expect(enHorarioLaboral(5, 14)).toBe(true);
    expect(enHorarioLaboral(5, 15)).toBe(false);
    expect(enHorarioLaboral(3, 6)).toBe(false);
    expect(enHorarioLaboral(6, 10)).toBe(false);
    expect(enHorarioLaboral(7, 10)).toBe(false);
  });

  it("la casilla de las 15 es el borde (las 15:00 en punto son laborales), salvo el fin de semana", () => {
    expect(horarioDeCasilla(2, 10)).toBe("laboral");
    expect(horarioDeCasilla(2, 15)).toBe("borde");
    expect(horarioDeCasilla(2, 16)).toBe("fuera");
    expect(horarioDeCasilla(2, 6)).toBe("fuera");
    expect(horarioDeCasilla(6, 15)).toBe("fuera");
  });
});

describe("partesPeriodo", () => {
  it.each([
    ["2026-10-05", { arriba: "5", abajo: "oct", largo: "lunes 5 de octubre de 2026" }],
    ["2026-10", { arriba: "oct", abajo: "2026", largo: "octubre de 2026" }],
    ["2026", { arriba: "2026", abajo: "", largo: "año 2026" }],
  ])("%s", (periodo, esperado) => {
    expect(partesPeriodo(periodo)).toEqual(esperado);
  });
});

describe("periodos", () => {
  const hoy = new Date(2026, 10, 2);   // lunes 2 de noviembre de 2026

  it("arma cada preset y lo reconoce de vuelta", () => {
    expect(rangoDePreset("30d", hoy)).toEqual({ desde: "2026-10-04", hasta: "2026-11-02" });
    expect(rangoDePreset("mes", hoy)).toEqual({ desde: "2026-11-01", hasta: "2026-11-02" });
    expect(rangoDePreset("mesPasado", hoy)).toEqual({ desde: "2026-10-01", hasta: "2026-10-31" });
    expect(rangoDePreset("anio", hoy)).toEqual({ desde: "2026-01-01", hasta: "2026-11-02" });
    for (const p of ["todo", "30d", "mes", "mesPasado", "anio"] as const) {
      expect(presetDeRango(rangoDePreset(p, hoy), hoy)).toBe(p);
    }
    expect(presetDeRango({ desde: "2026-09-15", hasta: "2026-10-14" }, hoy)).toBeNull();
  });

  it("el mes pasado de enero es diciembre del año anterior", () => {
    expect(rangoDePreset("mesPasado", new Date(2027, 0, 10))).toEqual({ desde: "2026-12-01", hasta: "2026-12-31" });
  });

  it.each([
    [{ desde: null, hasta: null }, "en todo el historial"],
    [{ desde: "2026-11-02", hasta: "2026-11-02" }, "el 2 de noviembre de 2026"],
    [{ desde: "2026-10-01", hasta: "2026-10-31" }, "del 1 al 31 de octubre de 2026"],
    [{ desde: "2026-09-15", hasta: "2026-10-14" }, "del 15 de septiembre al 14 de octubre de 2026"],
    [{ desde: "2025-12-01", hasta: "2026-01-31" }, "del 1 de diciembre de 2025 al 31 de enero de 2026"],
    [{ desde: "2026-01-05", hasta: null }, "desde el 5 de enero de 2026"],
  ])("%j → %s", (rango, esperado) => {
    expect(textoPeriodo(rango)).toBe(esperado);
  });
});

describe("unidadSugerida", () => {
  const hoy = new Date(2026, 10, 10);   // martes 10 de noviembre de 2026

  it("por día hasta un mes, por mes hasta un año y por año más allá", () => {
    expect(unidadSugerida({ desde: null, hasta: null }, hoy)).toBe("mes");
    expect(unidadSugerida(rangoDePreset("30d", hoy), hoy)).toBe("dia");
    expect(unidadSugerida(rangoDePreset("mes", hoy), hoy)).toBe("dia");
    expect(unidadSugerida(rangoDePreset("mesPasado", hoy), hoy)).toBe("dia");
    expect(unidadSugerida(rangoDePreset("anio", hoy), hoy)).toBe("mes");
    expect(unidadSugerida({ desde: "2026-10-01", hasta: "2026-11-01" }, hoy)).toBe("mes");   // 32 días
    expect(unidadSugerida({ desde: "2025-01-01", hasta: "2025-12-31" }, hoy)).toBe("mes");
    expect(unidadSugerida({ desde: "2024-01-01", hasta: "2025-12-31" }, hoy)).toBe("anio");
  });

  it("sin «hasta», cuenta hasta hoy", () => {
    expect(unidadSugerida({ desde: "2026-11-01", hasta: null }, hoy)).toBe("dia");
    expect(unidadSugerida({ desde: "2025-12-01", hasta: null }, hoy)).toBe("mes");
    // Más de un año: por mes se verían solo los últimos 12 (el tope de la serie).
    expect(unidadSugerida({ desde: "2025-06-01", hasta: null }, hoy)).toBe("anio");
  });
});
