import { describe, expect, it } from "vitest";
import { categoriaAccion } from "./categoriaAccion";

describe("categoriaAccion: el color de cada acción en la bitácora (rediseño del 2026-11-17)", () => {
  it.each([
    ["LOGIN_EXITOSO", "sesion"], ["CERRAR_SESION", "sesion"], ["SESION_EXPIRADA", "sesion"],
    ["LOGIN_FALLIDO", "alerta"], ["CUENTA_BLOQUEADA", "alerta"],
    ["CONTRASENA_CAMBIADA", "credencial"], ["CONTRASENA_RESTABLECIDA", "credencial"],
    ["SOLICITUD_CREADA", "solicitud"], ["SOLICITUD_APROBADA", "solicitud"], ["IMPEDIMENTOS_REGISTRADOS", "solicitud"],
    ["DOCUMENTO_VISTO", "documento"], ["DOCUMENTO_DESCARGADO", "documento"],
    ["AUTORIZACION_DESCARGADA", "documento"], ["AUTORIZACION_VERIFICADA", "documento"],
    ["BOLETA_GENERADA", "boleta"], ["BOLETA_ANULADA", "boleta"], ["BOLETA_DESCARGADA", "boleta"],
    ["USUARIO_CREADO", "administracion"], ["ROL_ELIMINADO", "administracion"], ["PERMISO_ACTUALIZADO", "administracion"],
    ["PUESTO_CREADO", "administracion"], ["SECTOR_ACTUALIZADO", "administracion"], ["AGENCIA_ELIMINADA", "administracion"],
    ["PAIS_ACTUALIZADO", "administracion"],
    ["TRANSFERENCIA_CREADA", "historico"], ["DESCARGA_REALIZADA", "historico"], ["CHAT_CONSULTA", "historico"],
  ])("%s → %s", (accion, categoria) => {
    expect(categoriaAccion(accion)).toBe(categoria);
  });

  it("una acción que no conoce queda neutra", () => {
    expect(categoriaAccion("ALGO_NUEVO")).toBe("otra");
  });
});
