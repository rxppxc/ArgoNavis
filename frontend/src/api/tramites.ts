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
  /** Rangos a los que se pide (null = a todos). Desde el 30/10/2026, a los
   *  rangos distintos de Marino solo se les piden Generales y boleto aéreo. */
  rangos: RangoMarino[] | null;
  /** Rangos para los que es opcional (null = obligatorio): el boleto de
   *  Desembarque de los técnicos (2026-11-11). */
  rangos_opcional: RangoMarino[] | null;
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
  /** El formulario ofrece el cambio de puerto (2026-11-13: Embarque y Desembarque). */
  permite_cambio_puerto: boolean;
  /** Pasaporte con al menos 3 meses de vigencia desde la operación (2026-11-13; el
   *  seamanbook vencido solo se señala). */
  valida_vigencia: boolean;
  /** Rangos de tripulante que admite el trámite (null = cualquiera). */
  rangos_permitidos: RangoMarino[] | null;
  /** Al aprobar se avisa que se debe tramitar la custodia de los restringidos. */
  aviso_custodia: boolean;
  /** Cuándo se usa el trámite, en una línea (tarjetas del paso 1). */
  descripcion: string | null;
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
/** "marino" es el valor de la API para lo que va por cada tripulante, sea del
 *  rango que sea: en pantalla, "Por tripulante" (con "Por marino", un documento
 *  solo para técnicos o militares se leía contradictorio). */
export const ETIQUETA_ALCANCE: Record<AlcanceDocumento, string> = {
  solicitud: "Por solicitud",
  marino: "Por pasajero",
};

export const ETIQUETA_CONDICION: Record<CondicionDocumento, string> = {
  siempre: "Siempre",
  solo_panamenos: "Solo panameños",
  nacionalidad_restringida: "Nacionalidad restringida",
};
