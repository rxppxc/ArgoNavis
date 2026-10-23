import { describe, expect, it } from "vitest";
import { EXTENSIONES_PERMITIDAS, TAMANO_MAX_BYTES, TAMANO_MAX_MB, TIPOS_ACEPTADOS, validarArchivos } from "./archivos";

// Que las constantes coincidan con las del backend lo comprueba test_espejo.py.
const archivo = (nombre: string, bytes = 10) => new File([new Uint8Array(bytes)], nombre);

describe("validarArchivos", () => {
  it("acepta PDF, Word y Excel sin importar mayúsculas", () => {
    expect(validarArchivos(["a.pdf", "b.DOC", "c.docx", "d.Xls", "e.xlsx"].map((n) => archivo(n)))).toBeNull();
  });

  it("rechaza otros formatos y dice cuáles", () => {
    expect(validarArchivos([archivo("foto.jpg"), archivo("bien.pdf"), archivo("sin-extension")]))
      .toBe("Solo se aceptan archivos PDF, Word o Excel: foto.jpg, sin-extension.");
  });

  it(`admite hasta ${TAMANO_MAX_MB} MB por archivo`, () => {
    expect(validarArchivos([archivo("justo.pdf", TAMANO_MAX_BYTES)])).toBeNull();
    expect(validarArchivos([archivo("grande.pdf", TAMANO_MAX_BYTES + 1)]))
      .toBe(`Cada archivo puede pesar hasta ${TAMANO_MAX_MB} MB. Pesan más: grande.pdf (2.00 MB).`);
  });

  it("el selector de archivos ofrece las mismas extensiones", () => {
    for (const extension of EXTENSIONES_PERMITIDAS) expect(TIPOS_ACEPTADOS).toContain(extension);
  });
});
