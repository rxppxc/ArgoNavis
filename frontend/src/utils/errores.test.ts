import { describe, expect, it } from "vitest";
import {
  MENSAJE_NO_DISPONIBLE, MENSAJE_SIN_CONEXION, MENSAJE_SIN_RESPUESTA, mensajeDeError,
} from "./errores";

const POR_DEFECTO = "No se pudo enviar la solicitud.";

describe("mensajeDeError", () => {
  it("usa el motivo del servidor cuando lo hay, también en un 503", () => {
    const error = { response: { status: 503, data: { detail: "La base de datos no respondió a tiempo." } } };
    expect(mensajeDeError(error, POR_DEFECTO)).toBe("La base de datos no respondió a tiempo.");
  });

  it("junta los mensajes de un 422 de validación", () => {
    const error = { response: { status: 422, data: { detail: [{ msg: "Falta el buque" }, { msg: "IMO inválido" }] } } };
    expect(mensajeDeError(error, POR_DEFECTO)).toBe("Falta el buque; IMO inválido");
  });

  it("sin respuesta del servidor dice que es la conexión", () => {
    expect(mensajeDeError({ request: {}, code: "ERR_NETWORK" }, POR_DEFECTO)).toBe(MENSAJE_SIN_CONEXION);
    expect(mensajeDeError({ request: {}, code: "ECONNABORTED" }, POR_DEFECTO)).toBe(MENSAJE_SIN_RESPUESTA);
  });

  it("nginx sin backend (502, 504) o un 503 sin motivo: no disponible", () => {
    for (const status of [502, 503, 504]) {
      expect(mensajeDeError({ response: { status, data: "<html>Bad Gateway</html>" } }, POR_DEFECTO))
        .toBe(MENSAJE_NO_DISPONIBLE);
    }
  });

  it("en lo demás, el texto de la pantalla", () => {
    expect(mensajeDeError({ response: { status: 500, data: {} } }, POR_DEFECTO)).toBe(POR_DEFECTO);
    expect(mensajeDeError(new Error("algo"), POR_DEFECTO)).toBe(POR_DEFECTO);
    expect(mensajeDeError(null, POR_DEFECTO)).toBe(POR_DEFECTO);
  });
});

describe("mensajeDeError con el código del pedido", () => {
  it("en un 5xx agrega el código, para encontrar la traza en el log", () => {
    const error = { response: { status: 500, data: { detail: "Error interno del servidor.", codigo: "3f2a1b9c0d4e" } } };
    expect(mensajeDeError(error, POR_DEFECTO)).toBe("Error interno del servidor. (código 3f2a1b9c0d4e)");
    const sinDetalle = { response: { status: 500, data: { codigo: "3f2a1b9c0d4e" } } };
    expect(mensajeDeError(sinDetalle, POR_DEFECTO)).toBe(`${POR_DEFECTO} (código 3f2a1b9c0d4e)`);
  });

  it("en un 4xx no: el motivo ya lo explica", () => {
    const error = { response: { status: 409, data: { detail: "Ya la aprobó otra persona.", codigo: "3f2a1b9c0d4e" } } };
    expect(mensajeDeError(error, POR_DEFECTO)).toBe("Ya la aprobó otra persona.");
  });
});
