import { useCallback, useMemo, useState, type ReactNode } from "react";
import { apiAutenticacion } from "../api/auth";
import { ContextoAutenticacion, type ValorAutenticacion } from "../hooks/useAutenticacion";
import type { Usuario } from "../types";

function leerUsuarioGuardado(): Usuario | null {
  try { return JSON.parse(localStorage.getItem("user") ?? "null"); }
  catch { return null; }
}

/** Una sola fuente del usuario de la sesión para toda la app (antes cada
 *  componente leía localStorage por su cuenta). */
export function ProveedorAutenticacion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(leerUsuarioGuardado);

  const guardarUsuario = useCallback((u: Usuario) => {
    localStorage.setItem("user", JSON.stringify(u));
    setUsuario(u);
  }, []);

  const iniciarSesion = useCallback(async (nombreUsuario: string, contrasena: string) => {
    const datos = await apiAutenticacion.iniciarSesion(nombreUsuario, contrasena);
    // Si había otro usuario antes (login directo en /login sin pasar por
    // "Cerrar sesión"), sus permisos cacheados no deben usarse ni un instante.
    localStorage.removeItem("permisos");
    localStorage.setItem("access_token", datos.access_token);
    guardarUsuario(datos.user);
    return datos.user;
  }, [guardarUsuario]);

  const cerrarSesion = useCallback(async (reportar = true, expirada = false) => {
    // Reportar ANTES de borrar el token: si no, la llamada sale sin
    // Authorization y el backend la rechaza con 401 sin dejar registro de
    // auditoría del cierre de sesión.
    if (reportar) {
      try {
        if (expirada) await apiAutenticacion.notificarExpiracion();
        else await apiAutenticacion.cerrarSesion();
      } catch {
        // Si el token ya no es válido o falla la red, igual cerramos localmente.
      }
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("permisos");
    setUsuario(null);
  }, []);

  const extenderSesion = useCallback(async () => {
    const datos = await apiAutenticacion.refrescarSesion();
    localStorage.setItem("access_token", datos.access_token);
    guardarUsuario(datos.user);
  }, [guardarUsuario]);

  const cambiarContrasena = useCallback(async (actual: string, nueva: string) => {
    const datos = await apiAutenticacion.cambiarContrasena(actual, nueva);
    localStorage.setItem("access_token", datos.access_token);
    guardarUsuario(datos.user);
  }, [guardarUsuario]);

  const valor = useMemo<ValorAutenticacion>(() => ({
    usuario, estaAutenticado: !!usuario, iniciarSesion, cerrarSesion, extenderSesion, cambiarContrasena,
  }), [usuario, iniciarSesion, cerrarSesion, extenderSesion, cambiarContrasena]);

  return <ContextoAutenticacion.Provider value={valor}>{children}</ContextoAutenticacion.Provider>;
}
