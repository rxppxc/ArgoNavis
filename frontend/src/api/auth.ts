import { clienteApi } from "./client";
import type { RespuestaToken, Usuario } from "../types";

export const apiAutenticacion = {
  iniciarSesion: (nombreUsuario: string, contrasena: string) =>
    clienteApi.post<RespuestaToken>("/auth/login", { username: nombreUsuario, password: contrasena }).then((r) => r.data),

  refrescarSesion: () =>
    clienteApi.post<RespuestaToken>("/auth/refresh").then((r) => r.data),

  cerrarSesion: () =>
    clienteApi.post("/auth/logout").catch(() => {}),

  notificarExpiracion: () =>
    clienteApi.post("/auth/session-expired").catch(() => {}),

  perfilActual: () =>
    clienteApi.get<Usuario>("/auth/me").then((r) => r.data),

  misPermisos: () =>
    clienteApi.get<string[]>("/auth/me/permisos").then((r) => r.data),

  /** Cambio de la propia contraseña (solo cuentas locales). Cierra las demás
   *  sesiones de la cuenta y devuelve un token nuevo para esta. */
  cambiarContrasena: (actual: string, nueva: string) =>
    clienteApi.post<RespuestaToken>("/auth/cambiar-contrasena", { actual, nueva }).then((r) => r.data),
};
