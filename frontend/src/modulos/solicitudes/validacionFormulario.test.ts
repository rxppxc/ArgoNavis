import { describe, expect, it } from "vitest";
import type { Pais } from "../../api/catalogos";
import type { RangoMarino, TripulanteEntrada } from "../../api/solicitudes";
import { tramiteDePrueba } from "../../pruebas/datos";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import {
  CABECERA_VACIA, fechaReferencia, nacimientoMaximo, operacionMaxima, validarFormulario,
  type CabeceraFormulario, type FichaTripulante,
} from "./validacionFormulario";

interface CasoTripulantes extends Caso {
  hoy: string;
  fecha_operacion: string;
  tramite: { valida_vigencia: boolean; rangos_permitidos: RangoMarino[] | null };
  tripulantes: Partial<TripulanteEntrada>[];
  esperado: string[];
}

const espejo = leerEspejo<{ base: TripulanteEntrada; paises: string[]; casos: CasoTripulantes[] }>("tripulantes.json");
const paises = new Map<string, Pais>(
  espejo.paises.map((codigo) => [codigo, { codigo, nombre: codigo, nacionalidad_restringida: false }]),
);
const ficha = (cambios: Partial<TripulanteEntrada> = {}, clave = "n1"): FichaTripulante =>
  ({ ...espejo.base, ...cambios, clave });

// Cada mensaje del frontend, a la clave de su regla (el backend tiene su propia tabla).
const REGLAS: Record<string, string> = {
  menor_de_edad: "debe ser mayor de edad",
  nacimiento_invalido: "la fecha de nacimiento no es válida",
  nacimiento_futuro: "la fecha de nacimiento debe ser anterior a hoy",
  pasaporte_antes_de_nacer: "vencimiento del pasaporte debe ser posterior",
  seamanbook_antes_de_nacer: "vencimiento del seamanbook debe ser posterior",
  pasaporte_vencido: "el pasaporte vence el",
  seamanbook_vencido: "el seamanbook vence el",
  rango_no_permitido: "el rango debe ser",
  marino_sin_seamanbook: "falta N° de seamanbook",
  pasaporte_repetido: "ya está registrado en el tripulante",
};

function regla(mensaje: string): string {
  const claves = Object.entries(REGLAS).filter(([, texto]) => mensaje.includes(texto)).map(([clave]) => clave);
  expect(claves, `mensaje sin una única regla: ${mensaje}`).toHaveLength(1);
  return claves[0];
}

describe("ficha del tripulante (espejo de validar_tripulantes)", () => {
  it.each(espejo.casos)("$caso", ({ hoy, fecha_operacion, tramite, tripulantes, esperado }) => {
    const fichas = tripulantes.map((cambios, i) => ficha(cambios, `n${i}`));
    const errores = validarFormulario(tramiteDePrueba(tramite), { ...CABECERA_VACIA, fecha_operacion }, fichas, paises, hoy)
      .filter((e) => e.startsWith("Tripulante"));
    expect(errores.map(regla).sort()).toEqual([...esperado].sort());
  });
});

describe("datos del trámite", () => {
  const hoy = "2026-10-14";
  const completa: CabeceraFormulario = {
    ...CABECERA_VACIA, puesto_control_id: "1", fecha_operacion: "2026-10-20",
    nombre_buque: "ESTRELLA DEL ISTMO", imo: "IMO 9074729", bandera: "PAN",
  };
  const validar = (cambios: Partial<CabeceraFormulario> = {}, tramite = tramiteDePrueba({ requiere_buque: true })) =>
    validarFormulario(tramite, { ...completa, ...cambios }, [ficha()], paises, hoy);

  it("sin errores con todo completo", () => {
    expect(validar()).toEqual([]);
  });

  it("la operación va de hoy a 365 días", () => {
    expect(validar({ fecha_operacion: "2026-10-13" })).toEqual(["La fecha de la operación no puede ser anterior a hoy."]);
    expect(validar({ fecha_operacion: operacionMaxima(hoy) })).toEqual([]);
    expect(validar({ fecha_operacion: "2027-10-15" })).toEqual(["La fecha de la operación no puede estar a más de 365 días."]);
  });

  it("pide el buque solo si el trámite lo usa, con un IMO válido", () => {
    expect(validar({ imo: "1234568" })).toEqual(["El número IMO no es válido (7 dígitos con dígito verificador, ej. IMO 9074729)."]);
    expect(validar({ nombre_buque: "", imo: "", bandera: "" }, tramiteDePrueba())).toEqual([]);
  });

  it("pide puerto, puerto de desembarque, motivo y clínica según el trámite", () => {
    const tramite = tramiteDePrueba({
      requiere_puerto: true, requiere_puerto_desembarque: true, requiere_motivo: true, requiere_clinica: true,
    });
    expect(validar({}, tramite)).toEqual([
      "Indica el nombre del puerto.", "Indica el puerto de desembarque.", "Indica el motivo.", "Indica la clínica u hospital.",
    ]);
  });

  it("al menos un tripulante", () => {
    expect(validarFormulario(tramiteDePrueba(), completa, [], paises, hoy)).toEqual(["Registra al menos un tripulante."]);
  });
});

describe("fechas límite", () => {
  it("18 años cumplidos, también en años bisiestos", () => {
    expect(nacimientoMaximo("2026-10-14")).toBe("2008-10-14");
    expect(nacimientoMaximo("2028-02-29")).toBe("2010-02-28");
    expect(nacimientoMaximo("2026-02-28")).toBe("2008-02-28");
  });

  it("la anticipación y la fecha contra la que se juzga la vigencia", () => {
    expect(operacionMaxima("2026-10-14")).toBe("2027-10-14");
    expect(fechaReferencia("2026-11-01", "2026-10-14")).toBe("2026-11-01");
    expect(fechaReferencia("2026-10-01", "2026-10-14")).toBe("2026-10-14");
    expect(fechaReferencia("", "2026-10-14")).toBe("2026-10-14");
  });
});
