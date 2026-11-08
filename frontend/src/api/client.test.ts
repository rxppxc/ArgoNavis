import { describe, expect, it } from "vitest";
import { leerErrorDeBlob } from "./client";
import { mensajeDeError } from "../utils/errores";

const POR_DEFECTO = "No se pudo abrir el documento.";
const errorCon = (cuerpo: Blob) => ({ response: { status: 403, data: cuerpo as unknown } });

describe("errores de las descargas (llegan como Blob)", () => {
  it("muestran el motivo real del servidor", async () => {
    const error = errorCon(new Blob([JSON.stringify({ detail: "No tienes acceso a esta solicitud." })],
      { type: "application/json" }));
    await leerErrorDeBlob(error);
    expect(mensajeDeError(error, POR_DEFECTO)).toBe("No tienes acceso a esta solicitud.");
  });

  it("si el cuerpo no es JSON, queda el mensaje genérico", async () => {
    const error = errorCon(new Blob(["<html>error</html>"], { type: "text/html" }));
    await leerErrorDeBlob(error);
    expect(mensajeDeError(error, POR_DEFECTO)).toBe(POR_DEFECTO);
  });

  it("un JSON roto o un error sin respuesta no rompen nada", async () => {
    const roto = errorCon(new Blob(["{no es json"], { type: "application/json" }));
    await leerErrorDeBlob(roto);
    expect(mensajeDeError(roto, POR_DEFECTO)).toBe(POR_DEFECTO);
    await expect(leerErrorDeBlob(new Error("sin red"))).resolves.toBeUndefined();
    await expect(leerErrorDeBlob(null)).resolves.toBeUndefined();
  });
});
