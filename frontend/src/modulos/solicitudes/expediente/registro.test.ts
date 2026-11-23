import { describe, expect, it } from "vitest";
import type { ArchivoRegistro, VersionSolicitud } from "../../../api/solicitudes";
import { archivoVisible, estadoArchivo, pasosDeLaVersion, textoSinVersion } from "./registro";

const ARCHIVO: ArchivoRegistro = {
  clase: "documento", id: 7, documento: "Libreta de marino", tripulante: "Raúl Pérez", nombre: "libreta.pdf",
  tamano: 1200, tipo_mime: "application/pdf", sha256: "ab", fecha: "2026-03-10T15:00:00Z", por: "Laura Agencia", retirado_en: null,
};

const VERSION: VersionSolicitud = {
  numero: 1, enviada_en: "2026-03-10T15:00:00Z", enviada_por: "Laura Agencia", devuelta_en: "2026-03-11T15:00:00Z",
  devuelta_por: "Ricardo Revisor", motivo: "Falta una firma", corregida_en: "2026-03-12T15:00:00Z", corregida_por: "Laura Agencia",
  datos: [], tripulantes: [], documentos: [], cambios: [],
};

describe("estadoArchivo", () => {
  it("dice si está vigente, cuándo se retiró o si se emitió", () => {
    expect(estadoArchivo(ARCHIVO)).toBe("Vigente");
    expect(estadoArchivo({ ...ARCHIVO, retirado_en: "2026-03-12T15:00:00Z" })).toBe("Retirado el 12/03/2026");
    expect(estadoArchivo({ ...ARCHIVO, clase: "emitido", documento: "Autorización aprobada" })).toBe("Emitida");
  });
});

describe("archivoVisible", () => {
  it("es lo que pide la vista previa, con su ruta: la del documento o la de la autorización emitida", () => {
    expect(archivoVisible(ARCHIVO)).toEqual({ id: 7, nombre_original: "libreta.pdf", tipo_mime: "application/pdf", emitido: false });
    expect(archivoVisible({ ...ARCHIVO, clase: "emitido" }).emitido).toBe(true);
  });
});

describe("pasosDeLaVersion", () => {
  it("cuenta quién la envió, quién la devolvió y quién la corrigió", () => {
    expect(pasosDeLaVersion(VERSION)).toEqual([
      expect.stringMatching(/^Enviada el 10\/03\/2026, .+ por Laura Agencia$/),
      expect.stringMatching(/^Devuelta el 11\/03\/2026, .+ por Ricardo Revisor$/),
      expect.stringMatching(/^Corregida el 12\/03\/2026, .+ por Laura Agencia$/),
    ]);
    expect(pasosDeLaVersion({ ...VERSION, enviada_por: null, devuelta_en: null })).toHaveLength(2);
  });
});

describe("textoSinVersion", () => {
  it("avisa de las correcciones de antes, que no guardaron lo enviado", () => {
    expect(textoSinVersion(0)).toBeNull();
    expect(textoSinVersion(1)).toBe("Una corrección de antes del 22/11/2026 no guardó lo que se había enviado.");
    expect(textoSinVersion(2)).toBe("2 correcciones de antes del 22/11/2026 no guardaron lo que se había enviado.");
  });
});
