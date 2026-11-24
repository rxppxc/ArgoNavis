import { afterEach, describe, expect, it, vi } from "vitest";
import { leerEspejo, type Caso } from "../pruebas/espejo";
import { TEXTO_HORARIO_LABORAL, enPanama, estadoHorario, fueraDeHorario } from "./horario";

interface CasoHorario extends Caso {
  momento: string;
  fuera:   boolean;
}

describe("fueraDeHorario (espejo de core/horario.py)", () => {
  it.each(leerEspejo<CasoHorario[]>("horario.json").map((c) => [c.caso, c] as const))("%s", (_, c) => {
    expect(fueraDeHorario(new Date(c.momento))).toBe(c.fuera);
  });
});

describe("enPanama", () => {
  afterEach(() => { vi.unstubAllEnvs(); });

  it("da el día, la hora y el día de la semana de Panamá (1 = lunes … 7 = domingo)", () => {
    expect(enPanama(new Date("2026-11-24T03:05:00Z"))).toEqual({ iso: "2026-11-23", diaSemana: 1, hora: 22, minuto: 5 });
    expect(enPanama(new Date("2026-11-29T15:00:00Z"))).toEqual({ iso: "2026-11-29", diaSemana: 7, hora: 10, minuto: 0 });
  });

  it("no depende de la zona horaria del equipo", () => {
    vi.stubEnv("TZ", "Asia/Tokyo");
    expect(enPanama(new Date("2026-11-24T03:05:00Z"))).toEqual({ iso: "2026-11-23", diaSemana: 1, hora: 22, minuto: 5 });
  });
});

describe("estadoHorario: si es laboral y hasta cuándo", () => {
  const panama = (fechaHora: string) => new Date(`${fechaHora}-05:00`);

  it("en horario, hasta las 15:00 (que todavía es laboral)", () => {
    expect(estadoHorario(panama("2026-11-23T10:00:00"))).toEqual({ laboral: true, hasta: "las 15:00" });
    expect(estadoHorario(panama("2026-11-23T15:00:30"))).toEqual({ laboral: true, hasta: "las 15:00" });
  });

  it("antes de las 07:00 de un día de semana, hasta las 07:00", () => {
    expect(estadoHorario(panama("2026-11-24T06:30:00"))).toEqual({ laboral: false, hasta: "las 07:00" });
  });

  it("desde las 15:01, hasta mañana a las 07:00", () => {
    expect(estadoHorario(panama("2026-11-23T15:01:00"))).toEqual({ laboral: false, hasta: "mañana a las 07:00" });
    expect(estadoHorario(panama("2026-11-26T20:00:00"))).toEqual({ laboral: false, hasta: "mañana a las 07:00" });
  });

  it("del viernes a las 15:01 al domingo, hasta el lunes", () => {
    expect(estadoHorario(panama("2026-11-27T15:01:00"))).toEqual({ laboral: false, hasta: "el lunes a las 07:00" });
    expect(estadoHorario(panama("2026-11-28T09:00:00"))).toEqual({ laboral: false, hasta: "el lunes a las 07:00" });
    // El domingo, el lunes ya es mañana.
    expect(estadoHorario(panama("2026-11-29T23:59:00"))).toEqual({ laboral: false, hasta: "mañana a las 07:00" });
  });
});

it("la frase del horario es la del correo y el PDF (TEXTO_HORARIO, core/horario.py)", () => {
  expect(TEXTO_HORARIO_LABORAL).toBe("lunes a viernes, de 07:00 a 15:00");
});
