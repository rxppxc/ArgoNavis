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

/** El personal del SNM que trabaja solicitudes: UCVMM, los supervisores y el
 *  puesto de control (el Administrador los tiene todos). Espejo de
 *  ContextoAcceso.es_personal_snm. */
export const PERMISOS_PERSONAL_SNM = [
  "T-PROCESAR-PACIFICO", "T-SUPERVISAR-SECTOR", "T-SUPERVISAR-TODO", "T-FINALIZAR-PUERTO",
];

/** La consulta histórica (2026-11-11): UCVMM, el supervisor de sector y el Administrador. El
 *  supervisor general no la tiene desde el 2026-11-16 ni el puesto de control desde el
 *  2026-11-22. Espejo de ContextoAcceso.ve_historico. */
export const PERMISOS_HISTORICO = ["T-PROCESAR-PACIFICO", "T-SUPERVISAR-SECTOR"];

/** Las estadísticas de su alcance: el supervisor de sector (y el Administrador). UCVMM no,
 *  desde el 2026-11-18; el supervisor general tampoco, desde el 2026-11-16. Espejo de
 *  _PUEDE_VER_ESTADISTICAS (api/v1/solicitudes.py). */
export const PERMISOS_ESTADISTICAS = ["T-SUPERVISAR-SECTOR"];

/** Permisos del usuario actual. Se cargan una sola vez por sesión en
 *  <ProveedorPermisos>. La fuente de verdad de los dos roles fijos es
 *  rol_personalizado.nombre: "Administrador" y "SysAdmin". */
export function usePermisos(): ValorPermisos {
  const valor = useContext(ContextoPermisos);
  if (!valor) throw new Error("usePermisos debe usarse dentro de <ProveedorPermisos>");
  return valor;
}
