import { describe, expect, it } from "vitest";
import type { Pais } from "../../api/catalogos";
import type { RangoMarino, TripulanteEntrada } from "../../api/solicitudes";
import { tramiteDePrueba } from "../../pruebas/datos";
import { leerEspejo, type Caso } from "../../pruebas/espejo";
import {
  CABECERA_VACIA, MAX_TRIPULANTES, estadoPasaporte, fechaReferencia, nacimientoMaximo, operacionMaxima,
  puestosParaCambio, validarFormulario, vigenciaMinimaPasaporte,
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
  pasaporte_vigencia_corta: "meses de vigencia",   // 2026-11-13; el seamanbook vencido ya no bloquea
  rango_no_permitido: "el rango debe ser",
  marino_sin_seamanbook: "falta N° de seamanbook",
  pasaporte_repetido: "ya está registrado en el pasajero",
};

function regla(mensaje: string): string {
  const claves = Object.entries(REGLAS).filter(([, texto]) => mensaje.includes(texto)).map(([clave]) => clave);
  expect(claves, `mensaje sin una única regla: ${mensaje}`).toHaveLength(1);
  return claves[0];
}

describe("ficha del pasajero (espejo de validar_pasajeros)", () => {
  it.each(espejo.casos)("$caso", ({ hoy, fecha_operacion, tramite, tripulantes, esperado }) => {
    const fichas = tripulantes.map((cambios, i) => ficha(cambios, `n${i}`));
    const errores = validarFormulario(tramiteDePrueba(tramite), { ...CABECERA_VACIA, fecha_operacion }, fichas, paises, hoy)
      .filter((e) => e.startsWith("Pasajero"));
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

  it("al menos un pasajero", () => {
    expect(validarFormulario(tramiteDePrueba(), completa, [], paises, hoy)).toEqual(["Registra al menos un pasajero."]);
  });

  it(`hasta ${MAX_TRIPULANTES} pasajeros`, () => {
    const tripulacion = (n: number) => Array.from({ length: n }, (_, i) => ficha({ pasaporte: `P${1000 + i}` }, `n${i}`));
    expect(validarFormulario(tramiteDePrueba(), completa, tripulacion(MAX_TRIPULANTES), paises, hoy)).toEqual([]);
    expect(validarFormulario(tramiteDePrueba(), completa, tripulacion(MAX_TRIPULANTES + 2), paises, hoy)).toEqual([
      `Una solicitud admite hasta ${MAX_TRIPULANTES} pasajeros: quita 2 y preséntalos en otra solicitud.`,
    ]);
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

  // Los mismos bordes que test_vigencia_minima_del_pasaporte (test_reglas.py).
  it("el pasaporte vence al menos 3 meses después de la operación, con el último día del mes", () => {
    expect(vigenciaMinimaPasaporte("2026-11-13")).toBe("2027-02-13");
    expect(vigenciaMinimaPasaporte("2026-11-30")).toBe("2027-02-28");
    expect(vigenciaMinimaPasaporte("2027-11-29")).toBe("2028-02-29");
    expect(vigenciaMinimaPasaporte("2026-10-31")).toBe("2027-01-31");
    expect(vigenciaMinimaPasaporte("2026-12-31")).toBe("2027-03-31");
  });

  it("vencido, con menos de 3 meses o bien", () => {
    expect(estadoPasaporte("2026-11-12", "2026-11-13")).toBe("vencido");
    expect(estadoPasaporte("2027-01-13", "2026-11-13")).toBe("corto");
    expect(estadoPasaporte("2027-02-12", "2026-11-13")).toBe("corto");
    expect(estadoPasaporte("2027-02-13", "2026-11-13")).toBe("bien");
    expect(estadoPasaporte("", "2026-11-13")).toBe("bien");   // sin fecha: lo dice «falta»
  });
});

describe("cambio de puerto (2026-11-13)", () => {
  const puestos = [
    { id: 1, nombre: "Balboa", sector_id: 10 },
    { id: 2, nombre: "Rodman", sector_id: 10 },
    { id: 3, nombre: "Cristóbal", sector_id: 20 },
    { id: 4, nombre: "Vacamonte", sector_id: 10 },
  ];

  it("solo los puestos del mismo sector, sin el elegido", () => {
    expect(puestosParaCambio(puestos, "1").map((p) => p.nombre)).toEqual(["Rodman", "Vacamonte"]);
    expect(puestosParaCambio(puestos, "3")).toEqual([]);
    expect(puestosParaCambio(puestos, "")).toEqual([]);
  });

  it("con «Sí» hay que elegir el nuevo puesto", () => {
    const hoy = "2026-10-14";
    const cabecera: CabeceraFormulario = {
      ...CABECERA_VACIA, puesto_control_id: "1", fecha_operacion: "2026-10-20", cambio_puerto: "si",
    };
    const conCambio = tramiteDePrueba({ permite_cambio_puerto: true });
    expect(validarFormulario(conCambio, cabecera, [ficha()], paises, hoy))
      .toEqual(["Elige el nuevo puesto de control del cambio de puerto."]);
    expect(validarFormulario(conCambio, { ...cabecera, puesto_destino_id: "2" }, [ficha()], paises, hoy))
      .toEqual([]);
    // Un trámite sin cambio de puerto no lo pide aunque haya quedado «Sí» de otro trámite.
    expect(validarFormulario(tramiteDePrueba(), cabecera, [ficha()], paises, hoy)).toEqual([]);
  });
});
