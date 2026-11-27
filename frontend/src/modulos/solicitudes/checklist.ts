import type { RangoMarino } from "../../api/solicitudes";
import type { CondicionDocumento, TipoTramite, TramiteDocumento } from "../../api/tramites";
import { RANGOS_CON_LIBRETA } from "./presentacion";

/** Lo que el checklist necesita saber de cada tripulante. `clave` es estable
 *  (no depende de la posición), así un archivo sigue en su casilla aunque se
 *  quite o reordene otro tripulante. */
export interface TripulanteChecklist {
  clave: string;
  nombre: string;
  es_panameno: boolean;
  rango: RangoMarino;
  restringida: boolean;
}

export interface CasillaFormulario {
  clave: string;
  documento_codigo: string;
  documento_nombre: string;
  descripcion: string | null;
  clave_tripulante: string | null;
  nombre_tripulante: string | null;
  /** Opcional: se puede enviar sin ella y no cuenta como faltante (2026-11-11). */
  obligatoria: boolean;
  /** Cuántos archivos admite (2026-11-27): la Form. 7, uno obligatorio y hasta 9 opcionales más. */
  maximo: number;
  /** La condición de su fila: la tarjeta del tripulante nombra los documentos que
   *  se le piden por su nacionalidad restringida (2026-11-14). */
  condicion?: CondicionDocumento;
}

export function claveCasilla(documentoCodigo: string, claveTripulante: string | null): string {
  return `${documentoCodigo}|${claveTripulante ?? "s"}`;
}

/** Si la fila del catálogo se le pide a un tripulante de ese rango: sus
 *  `rangos` (null = a todos) y la Libreta, solo a quien porta seamanbook.
 *  Espeja aplica_al_rango del backend. */
export function aplicaAlRango(d: Pick<TramiteDocumento, "rangos" | "requiere_libreta">, rango: RangoMarino): boolean {
  if (d.rangos && !d.rangos.includes(rango)) return false;
  return !d.requiere_libreta || RANGOS_CON_LIBRETA.includes(rango);
}

/** Si la fila es opcional para ese rango. Espeja opcional_para del backend. */
export function opcionalPara(d: Pick<TramiteDocumento, "rangos_opcional">, rango: RangoMarino): boolean {
  return !!d.rangos_opcional && d.rangos_opcional.includes(rango);
}

/** Si se piden los documentos de la condición `subir_y_bajar` (hoy, la carta de garantía de la
 *  agencia contratante; hasta el 2026-11-27, también la Carta Form. 7 de Técnico, que desde entonces
 *  va con toda operación): con la operación «Subir y bajar» del trámite de Técnico (2026-11-18) o
 *  con «¿Subir y bajar? Sí» donde se pregunte (Embarque y Desembarque, del 2026-11-16 al 18).
 *  Espeja ServicioSolicitud.con_carta_subir_y_bajar. */
export function conCartaSubirYBajar(
  tipo: Pick<TipoTramite, "permite_subir_y_bajar" | "pide_operacion">, respuesta: "si" | "no", operacion: string,
): boolean {
  return (tipo.pide_operacion && operacion === "subir_y_bajar") || (tipo.permite_subir_y_bajar && respuesta === "si");
}

/** Casillas que la solicitud debe cubrir, ya resueltas las condiciones.
 *  `subirYBajar`: si se pide la Carta de Responsabilidad de cada tripulante
 *  (`conCartaSubirYBajar`). `operacion`: la del trámite de Técnico (2026-11-18), «» sin
 *  elegir o en los demás; con Embarque o Desembarque se pide la garantía o el contrato.
 *  Espeja ServicioTramite.construir_casillas del backend: si cambias uno,
 *  cambia el otro. */
export function construirCasillas(
  tipo: TipoTramite, tripulantes: TripulanteChecklist[], subirYBajar = false, operacion = "",
): CasillaFormulario[] {
  const resultado: CasillaFormulario[] = [];

  for (const d of [...tipo.documentos].sort((a, b) => a.orden - b.orden)) {
    if (d.condicion === "subir_y_bajar" && !subirYBajar) continue;
    if (d.condicion === "embarque_o_desembarque" && operacion !== "embarque" && operacion !== "desembarque") continue;
    if (d.alcance === "solicitud") {
      if (d.condicion === "nacionalidad_restringida" && !tripulantes.some((t) => t.restringida)) continue;
      if (d.condicion === "solo_extranjeros" && tripulantes.every((t) => t.es_panameno)) continue;
      // Un documento de la solicitud con rangos: si algún tripulante es de esos rangos.
      const rangos = d.rangos;
      if (rangos && !tripulantes.some((t) => rangos.includes(t.rango))) continue;
      resultado.push({
        clave: claveCasilla(d.codigo, null),
        documento_codigo: d.codigo,
        documento_nombre: d.nombre,
        descripcion: d.descripcion,
        clave_tripulante: null,
        nombre_tripulante: null,
        obligatoria: true,
        maximo: d.maximo_archivos ?? 1,
        condicion: d.condicion,
      });
      continue;
    }

    for (const t of tripulantes) {
      // A los panameños no se les pide visa ni boleto aéreo en Embarque y Desembarque (2026-11-14).
      if (d.condicion === "solo_extranjeros" && t.es_panameno) continue;
      if (d.condicion === "nacionalidad_restringida" && !t.restringida) continue;
      if (!aplicaAlRango(d, t.rango)) continue;
      resultado.push({
        clave: claveCasilla(d.codigo, t.clave),
        documento_codigo: d.codigo,
        documento_nombre: d.nombre,
        descripcion: d.descripcion,
        clave_tripulante: t.clave,
        nombre_tripulante: t.nombre,
        obligatoria: !opcionalPara(d, t.rango),
        maximo: d.maximo_archivos ?? 1,
        condicion: d.condicion,
      });
    }
  }
  return resultado;
}
