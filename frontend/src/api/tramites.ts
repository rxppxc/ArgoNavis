import { clienteApi } from "./client";
import type { RangoMarino } from "./solicitudes";

export type Formulario = "formulario_3";
export type AlcanceDocumento = "solicitud" | "marino";
export type CondicionDocumento = "siempre" | "solo_panamenos" | "nacionalidad_restringida";

/** Una fila del checklist de un trámite. */
export interface TramiteDocumento {
  id: number;
  documento_id: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  alcance: AlcanceDocumento;
  condicion: CondicionDocumento;
  orden: number;
  /** Solo se exige a quien porta seamanbook (rango Marino). */
  requiere_libreta: boolean;
}

export interface TipoTramite {
  id: number;
  codigo: string;
  nombre: string;
  formulario: Formulario;
  requiere_buque: boolean;
  requiere_puerto: boolean;
  requiere_puerto_desembarque: boolean;
  requiere_motivo: boolean;
  requiere_clinica: boolean;
  /** Pasaporte y seamanbook deben estar vigentes a la fecha de la operación. */
  valida_vigencia: boolean;
  /** Rangos de tripulante que admite el trámite (null = cualquiera). */
  rangos_permitidos: RangoMarino[] | null;
  /** Al aprobar se avisa que se debe tramitar la custodia de los restringidos. */
  aviso_custodia: boolean;
  nota: string | null;
  orden: number;
  activo: boolean;
  documentos: TramiteDocumento[];
}

export const apiTramites = {
  async listar(): Promise<TipoTramite[]> {
    const { data } = await clienteApi.get<TipoTramite[]>("/tramites");
    return data;
  },

  async obtener(codigo: string): Promise<TipoTramite> {
    const { data } = await clienteApi.get<TipoTramite>(`/tramites/${codigo}`);
    return data;
  },
};

/** Etiquetas legibles para mostrar en la interfaz. */
export const ETIQUETA_ALCANCE: Record<AlcanceDocumento, string> = {
  solicitud: "Por solicitud",
  marino: "Por marino",
};

export const ETIQUETA_CONDICION: Record<CondicionDocumento, string> = {
  siempre: "Siempre",
  solo_panamenos: "Solo panameños",
  nacionalidad_restringida: "Nacionalidad restringida",
};
