import { createContext, useContext } from "react";

export interface ValorPermisos {
  /** Códigos de permiso del rol (ej. "T-CREAR-BASICA"). */
  codigos: string[];
  cargando: boolean;
  esAdmin: boolean;
  /** Rol técnico: usuarios, roles y bitácora. No ve solicitudes. */
  esSysAdmin: boolean;
  tiene: (codigo: string) => boolean;
  tieneAlguno: (...codigos: string[]) => boolean;
}

export const ContextoPermisos = createContext<ValorPermisos | null>(null);

/** Permisos del usuario actual. Se cargan una sola vez por sesión en
 *  <ProveedorPermisos>. La fuente de verdad de los dos roles fijos es
 *  rol_personalizado.nombre: "Administrador" y "SysAdmin". */
export function usePermisos(): ValorPermisos {
  const valor = useContext(ContextoPermisos);
  if (!valor) throw new Error("usePermisos debe usarse dentro de <ProveedorPermisos>");
  return valor;
}
