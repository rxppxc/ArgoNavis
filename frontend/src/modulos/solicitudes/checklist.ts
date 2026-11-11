import type { RangoMarino } from "../../api/solicitudes";
import type { TipoTramite, TramiteDocumento } from "../../api/tramites";
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

/** Casillas que la solicitud debe cubrir, ya resueltas las condiciones.
 *  Espeja ServicioTramite.construir_casillas del backend: si cambias uno,
 *  cambia el otro. */
export function construirCasillas(tipo: TipoTramite, tripulantes: TripulanteChecklist[]): CasillaFormulario[] {
  const resultado: CasillaFormulario[] = [];

  for (const d of [...tipo.documentos].sort((a, b) => a.orden - b.orden)) {
    if (d.alcance === "solicitud") {
      if (d.condicion === "nacionalidad_restringida" && !tripulantes.some((t) => t.restringida)) continue;
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
      });
      continue;
    }

    for (const t of tripulantes) {
      if (d.condicion === "solo_panamenos" && !t.es_panameno) continue;
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
      });
    }
  }
  return resultado;
}
