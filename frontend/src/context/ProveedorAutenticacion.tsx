import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
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

  // Otra pestaña cerró la sesión o entró con otra cuenta: esta la sigue al
  // instante (antes seguía mostrando la sesión hasta su siguiente pedido al
  // servidor). key null = se vació el localStorage.
  useEffect(() => {
    function alCambiarEnOtraPestana(e: StorageEvent) {
      if (e.key === "user" || e.key === null) setUsuario(leerUsuarioGuardado());
    }
    window.addEventListener("storage", alCambiarEnOtraPestana);
    return () => window.removeEventListener("storage", alCambiarEnOtraPestana);
  }, []);

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
    // Primero se cierra aquí, en el acto, y después se avisa al servidor con el
    // token de esta sesión (sin él, el backend respondería 401 y no quedaría el
    // cierre en la bitácora). Al revés, mientras esperaba ese aviso la página
    // seguía con el usuario: «Cerrar sesión» navega a /login, y con el cambio de
    // ruta la campana consultaba /pendientes con el token ya revocado (un 401 en
    // la consola).
    const token = localStorage.getItem("access_token");
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    localStorage.removeItem("permisos");
    setUsuario(null);
    if (reportar && token) {
      // Si el token ya no es válido o falla la red, la sesión ya quedó cerrada aquí.
      if (expirada) await apiAutenticacion.notificarExpiracion(token);
      else await apiAutenticacion.cerrarSesion(token);
    }
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
