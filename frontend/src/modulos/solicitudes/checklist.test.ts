import { describe, expect, it } from "vitest";
import type { AlcanceDocumento, CondicionDocumento } from "../../api/tramites";
import { tramiteDePrueba } from "../../pruebas/datos";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import { claveCasilla, construirCasillas } from "./checklist";

interface CasoChecklist extends Caso {
  documentos: { codigo: string; alcance: AlcanceDocumento; condicion: CondicionDocumento; requiere_libreta: boolean; orden: number }[];
  tripulantes: { nombre: string; es_panameno: boolean; porta_libreta: boolean; restringida: boolean }[];
  esperado: [string, number | null][];
}

describe("construirCasillas (espejo de construir_casillas)", () => {
  it.each(leerEspejo<CasoChecklist[]>("checklist.json"))("$caso", ({ documentos, tripulantes, esperado }) => {
    const tipo = tramiteDePrueba({
      documentos: documentos.map((d, i) => ({ ...d, id: i + 1, documento_id: i + 1, nombre: d.codigo, descripcion: null })),
    });
    const claves = tripulantes.map((_, i) => `n${i}`);
    const casillas = construirCasillas(tipo, tripulantes.map((t, i) => ({ ...t, clave: claves[i] })));
    const pares = casillas.map((c) => [c.documento_codigo, c.clave_tripulante === null ? null : claves.indexOf(c.clave_tripulante)]);
    expect(pares).toEqual(esperado);
  });

  it("la clave de una casilla sigue al tripulante, no a su posición", () => {
    expect(claveCasilla("PASAPORTE", "n7")).toBe("PASAPORTE|n7");
    expect(claveCasilla("LISTA", null)).toBe("LISTA|s");
  });
});
