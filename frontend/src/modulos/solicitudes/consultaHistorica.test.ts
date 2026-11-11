import { describe, expect, it } from "vitest";
import {
  FILTROS_VACIOS, anioDelRango, aniosDisponibles, consultaDeFiltros, filtrosDeUrl, hayFiltros, paginaDeUrl,
  rangoDeAnio, ultimaPagina, urlDeFiltros, type FiltrosHistorico,
} from "./consultaHistorica";

const LLENOS: FiltrosHistorico = {
  texto: "ESTRELLA", pasajero: "Ana Rios", agencia: "3", puesto: "7", tramite: "2", estado: "finalized",
  fecha: "operacion", desde: "2027-01-01", hasta: "2027-12-31", fueraDeHorario: true,
};

describe("los filtros en la URL", () => {
  it("van y vuelven iguales", () => {
    const url = new URLSearchParams(urlDeFiltros(LLENOS, 3));
    expect(filtrosDeUrl(url)).toEqual(LLENOS);
    expect(paginaDeUrl(url)).toBe(3);
  });

  it("sin filtros, la URL queda limpia", () => {
    expect(urlDeFiltros(FILTROS_VACIOS)).toEqual({});
    expect(urlDeFiltros({ ...FILTROS_VACIOS, texto: "   " })).toEqual({});
  });

  it("lo que no se entiende se ignora", () => {
    const url = new URLSearchParams(
      "agencia=abc&puesto=0&tramite=-1&estado=borrada&fecha=otra&desde=2027-13-01&hasta=31/12/2027&fuera=si&pagina=-2",
    );
    expect(filtrosDeUrl(url)).toEqual(FILTROS_VACIOS);
    expect(paginaDeUrl(url)).toBe(1);
    expect(filtrosDeUrl(new URLSearchParams({ texto: "x".repeat(150) })).texto).toHaveLength(100);
  });
});

describe("consultaDeFiltros", () => {
  it("manda los ids como números y deja fuera lo vacío", () => {
    expect(consultaDeFiltros(LLENOS, 2, 25)).toEqual({
      texto: "ESTRELLA", pasajero: "Ana Rios", agencia_id: 3, puesto_id: 7, tipo_tramite_id: 2, estado: "finalized",
      fuera_de_horario: true, fecha: "operacion", desde: "2027-01-01", hasta: "2027-12-31", pagina: 2, por_pagina: 25,
    });
    const vacia = consultaDeFiltros(FILTROS_VACIOS, 1, 25);
    expect(Object.entries(vacia).filter(([, v]) => v !== undefined)).toEqual([["pagina", 1], ["por_pagina", 25]]);
  });
});

describe("hayFiltros", () => {
  it("la fecha «por» sola no acota", () => {
    expect(hayFiltros(FILTROS_VACIOS)).toBe(false);
    expect(hayFiltros({ ...FILTROS_VACIOS, fecha: "operacion" })).toBe(false);
    expect(hayFiltros({ ...FILTROS_VACIOS, fueraDeHorario: true })).toBe(true);
    expect(hayFiltros({ ...FILTROS_VACIOS, pasajero: "Ana" })).toBe(true);
  });
});

describe("ultimaPagina", () => {
  it("es la última con resultados, y 1 si no hay ninguno", () => {
    expect(ultimaPagina(0, 25)).toBe(1);
    expect(ultimaPagina(25, 25)).toBe(1);
    expect(ultimaPagina(26, 25)).toBe(2);
    expect(ultimaPagina(130, 25)).toBe(6);
  });
});

describe("el atajo por año", () => {
  it("va del primer año con solicitudes hasta el de hoy", () => {
    expect(aniosDisponibles(new Date(2028, 5, 1))).toEqual([2028, 2027, 2026]);
    expect(aniosDisponibles(new Date(2026, 10, 11))).toEqual([2026]);
  });

  it("reconoce un año entero; lo demás son otras fechas", () => {
    const anios = [2028, 2027, 2026];
    expect(anioDelRango("", "", anios)).toBe("todos");
    expect(anioDelRango(rangoDeAnio(2027).desde, rangoDeAnio(2027).hasta, anios)).toBe(2027);
    expect(anioDelRango("2027-01-01", "2027-06-30", anios)).toBe("otras");
    expect(anioDelRango("2025-01-01", "2025-12-31", anios)).toBe("otras");
    expect(anioDelRango("2027-03-01", "", anios)).toBe("otras");
  });
});
