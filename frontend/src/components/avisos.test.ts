import { describe, expect, it } from "vitest";
import {
  MAX_AVISOS, agregarAviso, duracionDe, esUrgente, partesDelTexto, textoDelSello, type TipoNotificacion,
} from "./avisos";

describe("el sello de cada aviso", () => {
  it("dice el estado al que pasó la solicitud o, si no, el tipo", () => {
    expect(textoDelSello("exito", "devuelta")).toBe("Devuelta");
    expect(textoDelSello("exito", "finalizada")).toBe("Finalizada");
    expect(textoDelSello("exito")).toBe("Listo");
    expect(textoDelSello("aviso")).toBe("Revisa");
    expect(textoDelSello("error")).toBe("No se pudo");
    expect(textoDelSello("info")).toBe("Aviso");
  });

  it("errores y validaciones se anuncian enseguida y duran más; una decisión, 6 s", () => {
    expect(["error", "aviso"].every((t) => esUrgente(t as TipoNotificacion))).toBe(true);
    expect(esUrgente("exito") || esUrgente("info")).toBe(false);
    expect(duracionDe("exito")).toBe(4000);
    expect(duracionDe("error")).toBe(10000);
    expect(duracionDe("aviso")).toBe(10000);
    expect(duracionDe("exito", "aprobada")).toBe(6000);
  });
});

describe("partesDelTexto", () => {
  it("aparta el número de solicitud", () => {
    expect(partesDelTexto("Solicitud AM-2026-000142 enviada a revisión.")).toEqual([
      { texto: "Solicitud ", numero: false },
      { texto: "AM-2026-000142", numero: true },
      { texto: " enviada a revisión.", numero: false },
    ]);
  });

  it("sin número, un solo pedazo", () => {
    expect(partesDelTexto("Cambios guardados.")).toEqual([{ texto: "Cambios guardados.", numero: false }]);
  });

  it("la hora no se parte entre «a.» y «m.»", () => {
    const [parte] = partesDelTexto("Tiene hasta el 30/10/2026, 10:30 a. m. para corregirla.");
    expect(parte.texto).toBe("Tiene hasta el 30/10/2026, 10:30 a. m. para corregirla.");
    expect(partesDelTexto("a las 3:05 p. m.")[0].texto).toBe("a las 3:05 p. m.");
  });
});

describe("agregarAviso", () => {
  const aviso = (texto: string, tipo: TipoNotificacion = "exito") => ({ texto, tipo });

  it("el más nuevo va arriba, y como mucho tres", () => {
    let lista = [aviso("uno")];
    for (const t of ["dos", "tres", "cuatro"]) lista = agregarAviso(lista, aviso(t));
    expect(lista.map((m) => m.texto)).toEqual(["cuatro", "tres", "dos"]);
    expect(lista).toHaveLength(MAX_AVISOS);
  });

  it("uno repetido no se apila: reemplaza al anterior", () => {
    const lista = agregarAviso([aviso("Revisa los datos", "aviso"), aviso("Guardado")], aviso("Revisa los datos", "aviso"));
    expect(lista.map((m) => m.texto)).toEqual(["Revisa los datos", "Guardado"]);
    // Mismo texto con otro tipo es otro aviso.
    expect(agregarAviso([aviso("Hecho", "info")], aviso("Hecho", "exito"))).toHaveLength(2);
  });
});
