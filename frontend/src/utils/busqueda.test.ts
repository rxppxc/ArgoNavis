import { describe, expect, it } from "vitest";
import { filtrarOpciones, normalizarBusqueda, opcionEscrita, type OpcionBuscable } from "./busqueda";

const PAISES: OpcionBuscable[] = [
  { valor: "DEU", texto: "Alemania" },
  { valor: "ESP", texto: "España" },
  { valor: "USA", texto: "Estados Unidos" },
  { valor: "JPN", texto: "Japón" },
  { valor: "PAN", texto: "Panamá" },
  { valor: "PNG", texto: "Papúa Nueva Guinea" },
  { valor: "PER", texto: "Perú" },
];
const nombres = (opciones: OpcionBuscable[]) => opciones.map((o) => o.texto);

describe("selector con buscador", () => {
  it("no distingue mayúsculas, tildes ni espacios de más", () => {
    expect(normalizarBusqueda("  PANAMÁ  ")).toBe("panama");
    expect(normalizarBusqueda("Papúa   Nueva")).toBe("papua nueva");
    expect(nombres(filtrarOpciones(PAISES, "japon"))).toEqual(["Japón"]);
    expect(nombres(filtrarOpciones(PAISES, "PERÚ"))).toEqual(["Perú"]);
  });

  it("primero el código exacto, después lo que empieza, la palabra que empieza y lo que contiene", () => {
    expect(nombres(filtrarOpciones(PAISES, "pan"))).toEqual(["Panamá", "España"]);
    expect(nombres(filtrarOpciones(PAISES, "pa"))).toEqual(["Panamá", "Papúa Nueva Guinea", "España"]);
    expect(nombres(filtrarOpciones(PAISES, "apo"))).toEqual(["Japón"]);
    expect(nombres(filtrarOpciones(PAISES, "nueva"))).toEqual(["Papúa Nueva Guinea"]);
    expect(nombres(filtrarOpciones(PAISES, "usa"))).toEqual(["Estados Unidos"]);
    expect(nombres(filtrarOpciones(PAISES, "unidos"))).toEqual(["Estados Unidos"]);
  });

  it("sin nada escrito, todas, en el orden del catálogo", () => {
    expect(filtrarOpciones(PAISES, "")).toBe(PAISES);
    expect(filtrarOpciones(PAISES, "   ")).toBe(PAISES);
    expect(filtrarOpciones(PAISES, "xyz")).toEqual([]);
  });

  it("al salir sin elegir, vale lo escrito si es un nombre, un código o una sola coincidencia", () => {
    expect(opcionEscrita(PAISES, "panama")?.valor).toBe("PAN");
    expect(opcionEscrita(PAISES, "esp")?.valor).toBe("ESP");    // el código
    expect(opcionEscrita(PAISES, "Panam")?.valor).toBe("PAN");  // la única
    expect(opcionEscrita(PAISES, "pa")).toBeNull();               // varias: no adivina
    expect(opcionEscrita(PAISES, "xyz")).toBeNull();
    expect(opcionEscrita(PAISES, "")).toBeNull();
  });
});
