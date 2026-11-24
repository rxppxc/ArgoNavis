import { describe, expect, it } from "vitest";
import {
  acotar, aniosDisponibles, enmascarar, fechaLarga, fueraDeRango, isoATexto, partesDe, semanasDelMes, sumarDias,
  sumarMeses, textoAIso, vistaInicial,
} from "./calendario";

describe("partesDe: solo fechas que existen", () => {
  it("lee AAAA-MM-DD", () => {
    expect(partesDe("2026-11-26")).toEqual({ anio: 2026, mes: 10, dia: 26 });
  });
  it("rechaza el 31 de febrero, el formato equivocado y lo vacío", () => {
    expect(partesDe("2026-02-31")).toBeNull();
    expect(partesDe("26/11/2026")).toBeNull();
    expect(partesDe("")).toBeNull();
  });
});

describe("sumarDias", () => {
  it("cruza meses y años", () => {
    expect(sumarDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(sumarDias("2026-03-01", -1)).toBe("2026-02-28");
    expect(sumarDias("2028-03-01", -1)).toBe("2028-02-29");
  });
});

describe("sumarMeses: el mismo día, o el último del mes si no existe", () => {
  it("avanza y retrocede", () => {
    expect(sumarMeses("2026-11-26", 1)).toBe("2026-12-26");
    expect(sumarMeses("2026-11-26", -12)).toBe("2025-11-26");
  });
  it("el 31 de enero más un mes es el último de febrero", () => {
    expect(sumarMeses("2027-01-31", 1)).toBe("2027-02-28");
    expect(sumarMeses("2028-01-31", 1)).toBe("2028-02-29");
  });
});

describe("semanasDelMes: 6 semanas de domingo a sábado", () => {
  it("noviembre de 2026 empieza en domingo", () => {
    const semanas = semanasDelMes(2026, 10);
    expect(semanas).toHaveLength(6);
    expect(semanas[0]).toHaveLength(7);
    expect(semanas[0][0]).toBe("2026-11-01");
    expect(semanas[5][6]).toBe("2026-12-12");
  });
  it("febrero de 2027 (empieza en lunes) trae el último domingo de enero", () => {
    expect(semanasDelMes(2027, 1)[0][0]).toBe("2027-01-31");
    expect(semanasDelMes(2027, 1)[0][1]).toBe("2027-02-01");
  });
});

describe("enmascarar: las barras se ponen solas mientras se escribe", () => {
  it("con solo números", () => {
    expect(enmascarar("2")).toBe("2");
    expect(enmascarar("26")).toBe("26");
    expect(enmascarar("261")).toBe("26/1");
    expect(enmascarar("2611")).toBe("26/11");
    expect(enmascarar("26112026")).toBe("26/11/2026");
  });
  it("respeta las barras que escribe la persona, también con un solo dígito", () => {
    expect(enmascarar("26/")).toBe("26/");
    expect(enmascarar("1/5/2026")).toBe("1/5/2026");
    expect(enmascarar("26/11")).toBe("26/11");
    expect(enmascarar("26/112026")).toBe("26/11/2026");
  });
  it("acepta guiones y puntos como separador, y no pasa de 4 cifras en el año", () => {
    expect(enmascarar("26-11-2026")).toBe("26/11/2026");
    expect(enmascarar("26.11.20261")).toBe("26/11/2026");
  });
  it("deja intacta una fecha AAAA-MM-DD pegada", () => {
    expect(enmascarar("2026-11-26")).toBe("2026-11-26");
  });
  it("ignora letras", () => {
    expect(enmascarar("2a6b")).toBe("26");
  });
});

describe("textoAIso", () => {
  it("lee dd/mm/aaaa, con uno o dos dígitos", () => {
    expect(textoAIso("26/11/2026")).toBe("2026-11-26");
    expect(textoAIso("1/5/2026")).toBe("2026-05-01");
  });
  it("lee una fecha AAAA-MM-DD pegada", () => {
    expect(textoAIso("2026-11-26")).toBe("2026-11-26");
  });
  it("nada si está incompleta o no existe", () => {
    expect(textoAIso("26/11")).toBeNull();
    expect(textoAIso("26/11/26")).toBeNull();
    expect(textoAIso("31/02/2026")).toBeNull();
    expect(textoAIso("")).toBeNull();
  });
});

describe("isoATexto", () => {
  it("dd/mm/aaaa, o vacío", () => {
    expect(isoATexto("2026-05-01")).toBe("01/05/2026");
    expect(isoATexto("")).toBe("");
    expect(isoATexto("2026-02-31")).toBe("");
  });
});

describe("fueraDeRango y acotar", () => {
  it("dice de qué lado se sale", () => {
    expect(fueraDeRango("2026-11-22", "2026-11-23", "2027-11-23")).toBe("antes");
    expect(fueraDeRango("2027-11-24", "2026-11-23", "2027-11-23")).toBe("despues");
    expect(fueraDeRango("2026-11-23", "2026-11-23", "2027-11-23")).toBeNull();
    expect(fueraDeRango("1900-01-01")).toBeNull();
  });
  it("acotar lleva la fecha al borde más cercano", () => {
    expect(acotar("2026-01-01", "2026-11-23")).toBe("2026-11-23");
    expect(acotar("2030-01-01", undefined, "2027-11-23")).toBe("2027-11-23");
    expect(acotar("2026-12-01", "2026-11-23", "2027-11-23")).toBe("2026-12-01");
  });
});

describe("vistaInicial: qué mes muestra al abrir", () => {
  it("el de la fecha elegida", () => {
    expect(vistaInicial("2027-03-15", "2026-11-23")).toEqual({ anio: 2027, mes: 2 });
  });
  it("sin fecha, el de hoy si se puede elegir; si no, el del borde más cercano", () => {
    expect(vistaInicial("", "2026-11-23")).toEqual({ anio: 2026, mes: 10 });
    expect(vistaInicial("", "2026-11-23", "1900-01-01", "2008-11-23")).toEqual({ anio: 2008, mes: 10 });
  });
});

describe("aniosDisponibles", () => {
  it("un rango corto, en orden", () => {
    expect(aniosDisponibles("2026-11-23", "2026-11-23", "2027-11-23")).toEqual([2026, 2027]);
  });
  it("un rango largo (nacimiento), del más reciente al más antiguo", () => {
    const anios = aniosDisponibles("2026-11-23", "1900-01-01", "2008-11-23");
    expect(anios[0]).toBe(2008);
    expect(anios.at(-1)).toBe(1900);
  });
  it("sin bordes: cien años atrás y veinte adelante", () => {
    const anios = aniosDisponibles("2026-11-23");
    expect(anios[0]).toBe(2046);
    expect(anios.at(-1)).toBe(1926);
  });
});

describe("fechaLarga (bajo el campo, desde el 2026-11-23; antes, fechaEnPalabras)", () => {
  it("en palabras, sin correrse de día por la zona horaria", () => {
    expect(fechaLarga("2026-11-26")).toBe("jueves, 26 de noviembre de 2026");
    expect(fechaLarga("2026-11-13")).toBe("viernes, 13 de noviembre de 2026");
    expect(fechaLarga("2026-01-01")).toBe("jueves, 1 de enero de 2026");
    expect(fechaLarga("1988-03-14")).toBe("lunes, 14 de marzo de 1988");
  });
  it("sin fecha o con una que no existe, nada", () => {
    expect(fechaLarga("")).toBe("");
    expect(fechaLarga(null)).toBe("");
    expect(fechaLarga("2026-02-31")).toBe("");
    expect(fechaLarga("13/11/2026")).toBe("");
  });
});
