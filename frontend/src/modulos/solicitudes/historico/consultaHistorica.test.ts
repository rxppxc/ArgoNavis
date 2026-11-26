import { describe, expect, it } from "vitest";
import {
  FILTROS_VACIOS, anioDelRango, aniosDisponibles, consultaDeFiltros, filtrosConCambio, filtrosDeUrl, hayFiltros,
  motivoExpiracion, paginaDeUrl, primerosEncontrados, rangoDeAnio, sinOpcionesDesconocidas, ultimaPagina, urlDeFiltros,
  type FiltrosHistorico,
} from "./consultaHistorica";

describe("cambiar un filtro con algo escrito que todavía no se buscó (2026-11-23)", () => {
  // Lo escrito se busca 350 ms después. Una pestaña pulsada antes dejaba la búsqueda, la URL
  // y el «Volver» del expediente con el tripulante anterior (la CI, más rápida, caía ahí).
  const aplicados: FiltrosHistorico = { ...FILTROS_VACIOS, texto: "ESTRELLA", pasajero: "gomez, juan", estado: "autorizadas" };

  it("lo escrito entra con el cambio, sin esperar", () => {
    const escrito = { texto: "ESTRELLA", pasajero: "Pérez Gómez" };
    expect(filtrosConCambio(aplicados, escrito, { estado: "finalized" }))
      .toEqual({ ...aplicados, pasajero: "Pérez Gómez", estado: "finalized" });
  });

  it("y el resto de los filtros queda como estaba", () => {
    const conAgencia = { ...aplicados, agencia: "3", desde: "2026-01-01" };
    expect(filtrosConCambio(conAgencia, { texto: "MSC", pasajero: "gomez, juan" }, { puesto: "7" }))
      .toEqual({ ...conAgencia, texto: "MSC", puesto: "7" });
  });
});

const LLENOS: FiltrosHistorico = {
  texto: "ESTRELLA", pasajero: "Ana Rios", agencia: "3", puesto: "7", tramite: "2", estado: "finalized",
  fecha: "operacion", desde: "2027-01-01", hasta: "2027-12-31", fueraDeHorario: true,
};

describe("los filtros en la URL", () => {
  it("van y vuelven iguales, salvo el tripulante buscado, que no va en la URL (2026-11-14)", () => {
    const url = new URLSearchParams(urlDeFiltros(LLENOS, 3));
    expect(url.has("pasajero")).toBe(false);
    expect(filtrosDeUrl(url)).toEqual({ ...LLENOS, pasajero: "" });
    expect(paginaDeUrl(url)).toBe(3);
    expect(filtrosDeUrl(new URLSearchParams("pasajero=Ana")).pasajero).toBe("");
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

describe("las autorizadas (2026-11-22)", () => {
  const autorizadas: FiltrosHistorico = { ...FILTROS_VACIOS, estado: "autorizadas" };

  it("son una pestaña más: no van junto a un estado", () => {
    expect(urlDeFiltros(autorizadas)).toEqual({ estado: "autorizadas" });
    expect(filtrosDeUrl(new URLSearchParams("estado=autorizadas"))).toEqual(autorizadas);
    const consulta = consultaDeFiltros(autorizadas, 1, 25);
    expect(consulta.autorizadas).toBe(true);
    expect(consulta.estado).toBeUndefined();
    expect(consultaDeFiltros(LLENOS, 1, 25).autorizadas).toBeUndefined();
    expect(hayFiltros(autorizadas)).toBe(true);
  });
});

describe("motivoExpiracion", () => {
  it("dice si la expirada se llegó a aprobar; de las demás, nada", () => {
    expect(motivoExpiracion({ estado: "expired", aprobada_en: "2026-11-02T15:00:00Z" })).toBe("Aprobada; venció sin finalizarse");
    expect(motivoExpiracion({ estado: "expired", aprobada_en: null })).toBe("No se corrigió a tiempo");
    expect(motivoExpiracion({ estado: "finalized", aprobada_en: "2026-11-02T15:00:00Z" })).toBeNull();
  });
});

describe("primerosEncontrados", () => {
  it("muestra hasta tres y cuenta el resto", () => {
    expect(primerosEncontrados(["A", "B"])).toEqual({ visibles: ["A", "B"], mas: 0 });
    expect(primerosEncontrados(["A", "B", "C", "D", "E"])).toEqual({ visibles: ["A", "B", "C"], mas: 2 });
    expect(primerosEncontrados(null)).toEqual({ visibles: [], mas: 0 });
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

describe("los ids que no están en las opciones", () => {
  const opciones = {
    agencias: [{ id: 3, nombre: "A", activo: true }],
    puestos: [{ id: 7, nombre: "P", activo: false }],
    tramites: [{ id: 2, nombre: "T", activo: true }],
  };

  it("se quitan; lo que existe (también lo desactivado) se queda", () => {
    expect(sinOpcionesDesconocidas({ ...LLENOS, agencia: "99", puesto: "7" }, opciones))
      .toEqual({ ...LLENOS, agencia: "", puesto: "7" });
  });

  it("si no cambia nada, el mismo objeto", () => {
    expect(sinOpcionesDesconocidas(LLENOS, opciones)).toBe(LLENOS);
    expect(sinOpcionesDesconocidas(FILTROS_VACIOS, opciones)).toBe(FILTROS_VACIOS);
  });
});
