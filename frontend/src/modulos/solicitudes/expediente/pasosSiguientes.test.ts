import { describe, expect, it } from "vitest";
import type { AccionesSolicitud } from "../../../api/solicitudes";
import { pasosSiguientes, type EntradaPasos } from "./pasosSiguientes";

const NINGUNA: AccionesSolicitud = {
  corregir: false, revisar: false, finalizar: false, descargar_autorizacion: false, conflicto_revision: false,
  generar_boleta: false, anular_boleta: false,
};

function entrada(cambios: Partial<EntradaPasos> = {}): EntradaPasos {
  return {
    estado: "review", acciones: NINGUNA, esAgencia: false, verificacion: null,
    plazo: null, puesto: "Puesto de Balboa", ...cambios,
  };
}

const textos = (e: EntradaPasos) => pasosSiguientes(e).map((p) => p.texto);
const hechos = (e: EntradaPasos) => pasosSiguientes(e).map((p) => p.hecho);

describe("pasosSiguientes: «Qué sigue» del expediente (rediseño del 2026-11-17)", () => {
  it("UCVMM al revisar: marcar, guardar y decidir; los pasos hechos se marcan", () => {
    const revisar = { ...NINGUNA, revisar: true };
    expect(textos(entrada({ acciones: revisar, verificacion: { pendientes: 3, guardada: false } }))).toEqual([
      "Marca «Sin» o «Con» a cada tripulante en la tabla",
      "Guarda la verificación",
      "Aprueba, devuelve a corrección o deniega la solicitud",
    ]);
    expect(hechos(entrada({ acciones: revisar, verificacion: { pendientes: 3, guardada: false } }))).toEqual([false, false, false]);
    expect(hechos(entrada({ acciones: revisar, verificacion: { pendientes: 0, guardada: false } }))).toEqual([true, false, false]);
    expect(hechos(entrada({ acciones: revisar, verificacion: { pendientes: 0, guardada: true } }))).toEqual([true, true, false]);
  });

  it("el puesto con una aprobada: verificar en SIMPLUS, comentar y finalizar en su puesto", () => {
    const finalizar = { ...NINGUNA, finalizar: true };
    const pasos = entrada({ estado: "approved", acciones: finalizar, verificacion: { pendientes: 2, guardada: false } });
    expect(textos(pasos)).toEqual([
      "Verifica los impedimentos de cada tripulante en SIMPLUS y guarda la verificación",
      "Escribe el comentario de la operación",
      "Finaliza la solicitud (solo si la operación se hizo en Puesto de Balboa)",
    ]);
    expect(hechos({ ...pasos, verificacion: { pendientes: 0, guardada: true } })).toEqual([true, false, false]);
  });

  it("con recargo y sin boleta vigente, se suma generar la boleta; si es lo único, va solo", () => {
    const conBoleta = { ...NINGUNA, finalizar: true, generar_boleta: true };
    expect(textos(entrada({ estado: "approved", acciones: conBoleta, verificacion: { pendientes: 1, guardada: false } })).at(-1))
      .toBe("Genera la boleta de recargo (aprobada fuera del horario) y entrégala a la agencia");
    expect(textos(entrada({ estado: "approved", acciones: { ...NINGUNA, generar_boleta: true } }))).toEqual([
      "Genera la boleta de recargo (aprobada fuera del horario) y entrégala a la agencia",
    ]);
  });

  it("la agencia con una devuelta: leer el motivo y corregir antes del plazo", () => {
    expect(textos(entrada({ estado: "returned", esAgencia: true, acciones: { ...NINGUNA, corregir: true }, plazo: "20/11/2026, 04:31 p. m." })))
      .toEqual([
        "Lee el motivo de la devolución",
        "Pulsa «Corregir solicitud» y cambia lo que se pidió",
        "Envíala de nuevo antes del 20/11/2026, 04:31 p. m.",
      ]);
  });

  it("la agencia con una aprobada: descargar la autorización y presentarla en el puesto", () => {
    expect(textos(entrada({ estado: "approved", esAgencia: true, acciones: { ...NINGUNA, descargar_autorizacion: true } })))
      .toEqual([
        "Descarga la autorización (PDF)",
        "Preséntala en Puesto de Balboa el día de la operación",
      ]);
  });

  it("sin nada que hacer, no hay pasos (el recuadro no se muestra)", () => {
    expect(pasosSiguientes(entrada({ esAgencia: true }))).toEqual([]);
    expect(pasosSiguientes(entrada({ estado: "denied", esAgencia: true }))).toEqual([]);
    expect(pasosSiguientes(entrada({ estado: "finalized" }))).toEqual([]);
    expect(pasosSiguientes(entrada({ estado: "approved", acciones: { ...NINGUNA, descargar_autorizacion: true } }))).toEqual([]);
  });
});
