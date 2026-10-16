import { createContext, useContext } from "react";
import type { Usuario } from "../types";

export interface ValorAutenticacion {
  usuario: Usuario | null;
  estaAutenticado: boolean;
  iniciarSesion: (nombreUsuario: string, contrasena: string) => Promise<Usuario>;
  cerrarSesion: (reportar?: boolean, expirada?: boolean) => Promise<void>;
  extenderSesion: () => Promise<void>;
  /** Cambia la propia contraseña y sigue con el token nuevo que devuelve el
   *  backend (el anterior queda invalidado). */
  cambiarContrasena: (actual: string, nueva: string) => Promise<void>;
}

export const ContextoAutenticacion = createContext<ValorAutenticacion | null>(null);

/** Sesión del usuario. El estado vive en <ProveedorAutenticacion>: todos los
 *  componentes comparten el mismo usuario. */
export function useAutenticacion(): ValorAutenticacion {
  const valor = useContext(ContextoAutenticacion);
  if (!valor) throw new Error("useAutenticacion debe usarse dentro de <ProveedorAutenticacion>");
  return valor;
}
