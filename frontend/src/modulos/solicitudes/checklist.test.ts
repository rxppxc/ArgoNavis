import { describe, expect, it } from "vitest";
import type { RangoMarino } from "../../api/solicitudes";
import type { AlcanceDocumento, CondicionDocumento } from "../../api/tramites";
import { tramiteDePrueba } from "../../pruebas/datos";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import { claveCasilla, conCartaSubirYBajar, construirCasillas } from "./checklist";

interface CasoChecklist extends Caso {
  documentos: {
    codigo: string; alcance: AlcanceDocumento; condicion: CondicionDocumento; requiere_libreta: boolean; orden: number;
    rangos?: RangoMarino[]; rangos_opcional?: RangoMarino[];
  }[];
  tripulantes: { nombre: string; es_panameno: boolean; rango: RangoMarino; restringida: boolean }[];
  esperado: [string, number | null][];
  opcionales?: [string, number | null][];
  /** Si se pide la Carta de «Subir y bajar» (2026-11-16); sin el campo, no. */
  subir_y_bajar?: boolean;
  /** La operación del trámite de Técnico (2026-11-18); sin el campo, sin elegir. */
  operacion?: string;
}

describe("construirCasillas (espejo de construir_casillas)", () => {
  it.each(leerEspejo<CasoChecklist[]>("checklist.json"))("$caso", ({
    documentos, tripulantes, esperado, opcionales = [], subir_y_bajar = false, operacion = "",
  }) => {
    const tipo = tramiteDePrueba({
      documentos: documentos.map((d, i) => ({
        ...d, rangos: d.rangos ?? null, rangos_opcional: d.rangos_opcional ?? null, id: i + 1, documento_id: i + 1, nombre: d.codigo, descripcion: null,
      })),
    });
    const claves = tripulantes.map((_, i) => `n${i}`);
    const casillas = construirCasillas(tipo, tripulantes.map((t, i) => ({ ...t, clave: claves[i] })), subir_y_bajar,
      operacion);
    const pares = casillas.map((c) => [c.documento_codigo, c.clave_tripulante === null ? null : claves.indexOf(c.clave_tripulante)]);
    expect(pares).toEqual(esperado);
    expect(pares.filter((_, i) => !casillas[i].obligatoria)).toEqual(opcionales);
  });

  it("la clave de una casilla sigue al tripulante, no a su posición", () => {
    expect(claveCasilla("PASAPORTE", "n7")).toBe("PASAPORTE|n7");
    expect(claveCasilla("LISTA", null)).toBe("LISTA|s");
  });
});

interface CasoSubirYBajar extends Caso {
  tramite: { permite_subir_y_bajar: boolean; pide_operacion: boolean };
  subir_y_bajar: boolean;
  operacion: string | null;
  esperado: boolean;
}

describe("la Carta de «Subir y bajar» (espejo de con_carta_subir_y_bajar, 2026-11-18)", () => {
  it.each(leerEspejo<CasoSubirYBajar[]>("subir_y_bajar.json"))("$caso", ({ tramite, subir_y_bajar, operacion, esperado }) => {
    expect(conCartaSubirYBajar(tramiteDePrueba(tramite), subir_y_bajar ? "si" : "no", operacion ?? "")).toBe(esperado);
  });
});
