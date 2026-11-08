import { createContext, useContext } from "react";
import type { Pendientes } from "../api/pendientes";

export interface ValorPendientes {
  /** null hasta la primera respuesta, o sin sesión. */
  datos: Pendientes | null;
  /** Suma de los pendientes: el número de la campana y de la pestaña. */
  total: number;
  /** Vuelve a consultar (por ejemplo, después de aprobar o finalizar). */
  refrescar: () => void;
  /** Marca como leídas las novedades (al abrir la campana). */
  marcarVistas: () => Promise<void>;
}

export const ContextoPendientes = createContext<ValorPendientes | null>(null);

/** Notificaciones internas del usuario actual, de <ProveedorPendientes>. */
export function usePendientes(): ValorPendientes {
  const valor = useContext(ContextoPendientes);
  if (!valor) throw new Error("usePendientes debe usarse dentro de <ProveedorPendientes>");
  return valor;
}
