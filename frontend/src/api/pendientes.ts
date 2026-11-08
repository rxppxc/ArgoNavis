import { clienteApi } from "./client";
import type { Bandeja, EstadoSolicitud, EventoSolicitud } from "./solicitudes";

/** Lo que le toca hacer al usuario en una de sus bandejas. */
export interface Pendiente {
  clave: "por_revisar" | "por_finalizar" | "por_corregir";
  texto: string;
  cantidad: number;
  bandeja: Bandeja;
  estado: Extract<EstadoSolicitud, "review" | "returned" | "approved">;
  /** El plazo más próximo (corrección o finalización); null si no hay ninguna. */
  vence_en: string | null;
}

/** Un paso reciente de una de sus solicitudes (a la agencia no le llega lo interno). */
export interface Novedad {
  id: number;
  solicitud_id: number;
  numero: string | null;
  titulo: string;
  tipo: EventoSolicitud["tipo"];
  comentario: string | null;
  usuario_nombre: string | null;
  creado_en: string;
  no_leida: boolean;
}

export interface Pendientes {
  /** Si el usuario trabaja solicitudes (el SysAdmin no: no lleva campana). */
  disponible: boolean;
  pendientes: Pendiente[];
  novedades: Novedad[];
  no_leidas: number;
}

export const apiPendientes = {
  consultar: () => clienteApi.get<Pendientes>("/pendientes").then((r) => r.data),

  /** Abrió la campana: sus novedades hasta ahora quedan leídas. */
  marcarVistas: () => clienteApi.post("/pendientes/vistas").then(() => undefined),
};
