import { describe, expect, it } from "vitest";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import { tripulanteDePrueba } from "../../pruebas/datos";
import {
  ETIQUETA_EVENTO, normalizarImo, TEXTO_HORARIO_LABORAL, textoSector, textoSectorCorto,
  avisoImpedimentos, avisoSubirYBajar, textoVigencia, tituloColumnaRango,
} from "./presentacion";

describe("tituloColumnaRango (la ocupación salió del formulario el 2026-11-16)", () => {
  it("dice la ocupación solo si algún pasajero la tiene (una solicitud de antes)", () => {
    expect(tituloColumnaRango([tripulanteDePrueba(), tripulanteDePrueba({ id: 2 })])).toBe("Rango");
    expect(tituloColumnaRango([tripulanteDePrueba(), tripulanteDePrueba({ id: 2, ocupacion: "Cocinero" })]))
      .toBe("Rango / ocupación");
    expect(tituloColumnaRango([])).toBe("Rango");
  });
});

describe("ETIQUETA_EVENTO", () => {
  it("nombra los eventos de la boleta de recargo (2026-11-16, internos del SNM)", () => {
    expect(ETIQUETA_EVENTO.boleta_generada).toBe("Boleta de recargo generada");
    expect(ETIQUETA_EVENTO.boleta_anulada).toBe("Boleta de recargo anulada");
  });
});

describe("TEXTO_HORARIO_LABORAL", () => {
  it("dice lo mismo que el correo y el PDF (TEXTO_HORARIO de core/horario.py)", () => {
    expect(TEXTO_HORARIO_LABORAL).toBe("lunes a viernes, de 07:00 a 15:00");
  });
});

interface CasoImo extends Caso {
  valor: string;
  esperado: string | null;
}

describe("normalizarImo (espejo de normalizar_imo)", () => {
  it.each(leerEspejo<CasoImo[]>("imo.json"))("$caso", ({ valor, esperado }) => {
    expect(normalizarImo(valor)).toBe(esperado);
  });
});

describe("textoSector (2026-11-22)", () => {
  it("es el que la revisó y, si el puesto cambió de sector, también el de hoy", () => {
    expect(textoSector({ sector_nombre: "Sector Pacífico", sector_actual_nombre: null })).toBe("Sector Pacífico");
    expect(textoSector({ sector_nombre: "Sector Pacífico", sector_actual_nombre: "Sector Atlántico" }))
      .toBe("Sector Pacífico, que la revisó. Hoy el puesto es del Sector Atlántico");
    expect(textoSector({ sector_nombre: null, sector_actual_nombre: null })).toBeNull();
    expect(textoSectorCorto({ sector_nombre: "Sector Pacífico", sector_actual_nombre: null })).toBe("Sector Pacífico");
    expect(textoSectorCorto({ sector_nombre: "Sector Pacífico", sector_actual_nombre: "Sector Atlántico" }))
      .toBe("Sector Pacífico (hoy, Sector Atlántico)");
  });
});

describe("textoVigencia (espejo de texto_vigencia, core/horario.py; 2026-11-26)", () => {
  interface CasoVigencia extends Caso { horas: number; texto: string }
  it.each(leerEspejo<CasoVigencia[]>("vigencia.json"))("$caso", ({ horas, texto }) => {
    expect(textoVigencia(horas)).toBe(texto);
  });
});

describe("avisoImpedimentos (espejo de aviso_impedimentos, models/solicitud.py; 2026-11-26)", () => {
  interface CasoImpedimentos extends Caso { nombres: string[]; texto: string | null }
  it.each(leerEspejo<CasoImpedimentos[]>("impedimentos.json"))("$caso", ({ nombres, texto }) => {
    expect(avisoImpedimentos(nombres)).toBe(texto);
  });
});

describe("avisoSubirYBajar (la operación del trámite de Técnico; 2026-11-26)", () => {
  const form7 = { nombre: "Carta de Responsabilidad (Form. No. 7)", condicion: "subir_y_bajar" as const };
  const garantia = { nombre: "Carta de garantía de la agencia contratante", condicion: "subir_y_bajar" as const };
  const generales = { nombre: "Generales de Pasaporte", condicion: "siempre" as const };

  it("nombra lo que «Subir y bajar» suma a la solicitud, una de cada una", () => {
    expect(avisoSubirYBajar([
      { ...generales, alcance: "marino" }, { ...form7, alcance: "solicitud" }, { ...garantia, alcance: "solicitud" },
    ]))
      .toBe("Con «Subir y bajar» se adjuntan además, una por solicitud, «Carta de Responsabilidad (Form. No. 7)» "
        + "y «Carta de garantía de la agencia contratante», en los documentos de la solicitud.");
  });

  it("si un documento va por tripulante, lo dice aparte", () => {
    expect(avisoSubirYBajar([{ ...form7, alcance: "marino" }, { ...garantia, alcance: "solicitud" }]))
      .toBe("Con «Subir y bajar» se adjuntan además, una por solicitud, «Carta de garantía de la agencia contratante», "
        + "en los documentos de la solicitud. Cada tripulante adjunta «Carta de Responsabilidad (Form. No. 7)» "
        + "en sus documentos.");
  });

  it("sin documentos de «Subir y bajar», nada que avisar", () => {
    expect(avisoSubirYBajar([{ ...generales, alcance: "marino" }])).toBeNull();
  });
});
