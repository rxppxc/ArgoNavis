import { describe, expect, it } from "vitest";
import { avanceFormulario } from "./pasosDelFormulario";

describe("avanceFormulario: el indicador de los pasos del formulario (rediseño del 2026-11-17)", () => {
  it("sin trámite elegido, lo primero es elegirlo", () => {
    const pasos = avanceFormulario({ tipoElegido: false, errores: [], faltantes: 0 });
    expect(pasos.map((p) => [p.numero, p.titulo, p.completo, p.detalle])).toEqual([
      [1, "Tipo de trámite", false, "Elige el trámite"],
      [2, "Datos del trámite", false, "Primero elige el trámite"],
      [3, "Pasajeros", false, "Primero elige el trámite"],
      [4, "Documentos", false, "Primero elige el trámite"],
    ]);
  });

  it("separa lo que falta de los datos, de los pasajeros y de los documentos", () => {
    const pasos = avanceFormulario({
      tipoElegido: true,
      errores: [
        "Elige el puesto de Control Migratorio.",
        "Indica la fecha de la operación.",
        "Pasajero 1 (Ana Ríos): falta sexo, N° de pasaporte.",
        "Pasajero 2: falta nombre.",
      ],
      faltantes: 3,
    });
    expect(pasos.map((p) => [p.completo, p.detalle])).toEqual([
      [true, "Listo"],
      [false, "Faltan 2 datos"],
      [false, "2 pasajeros por completar"],
      [false, "Faltan 3 documentos"],
    ]);
  });

  it("los avisos de la lista de pasajeros cuentan para su paso; en singular, sin plural", () => {
    const pasos = avanceFormulario({ tipoElegido: true, errores: ["Registra al menos un pasajero."], faltantes: 1 });
    expect(pasos.map((p) => p.detalle)).toEqual(["Listo", "Listo", "1 aviso por revisar", "Falta 1 documento"]);
  });

  it("con todo completo, los cuatro pasos están listos", () => {
    expect(avanceFormulario({ tipoElegido: true, errores: [], faltantes: 0 }).every((p) => p.completo && p.detalle === "Listo"))
      .toBe(true);
  });
});
