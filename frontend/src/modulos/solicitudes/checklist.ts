import type { TipoTramite } from "../../api/tramites";

/** Lo que el checklist necesita saber de cada tripulante. `clave` es estable
 *  (no depende de la posición), así un archivo sigue en su casilla aunque se
 *  quite o reordene otro tripulante. */
export interface TripulanteChecklist {
  clave: string;
  nombre: string;
  es_panameno: boolean;
  porta_libreta: boolean;
  restringida: boolean;
}

export interface CasillaFormulario {
  clave: string;
  documento_codigo: string;
  documento_nombre: string;
  descripcion: string | null;
  clave_tripulante: string | null;
  nombre_tripulante: string | null;
}

export function claveCasilla(documentoCodigo: string, claveTripulante: string | null): string {
  return `${documentoCodigo}|${claveTripulante ?? "s"}`;
}

/** Casillas que la solicitud debe cubrir, ya resueltas las condiciones.
 *  Espeja ServicioTramite.construir_casillas del backend: si cambias uno,
 *  cambia el otro. */
export function construirCasillas(tipo: TipoTramite, tripulantes: TripulanteChecklist[]): CasillaFormulario[] {
  const resultado: CasillaFormulario[] = [];

  for (const d of [...tipo.documentos].sort((a, b) => a.orden - b.orden)) {
    if (d.alcance === "solicitud") {
      if (d.condicion === "nacionalidad_restringida" && !tripulantes.some((t) => t.restringida)) continue;
      resultado.push({
        clave: claveCasilla(d.codigo, null),
        documento_codigo: d.codigo,
        documento_nombre: d.nombre,
        descripcion: d.descripcion,
        clave_tripulante: null,
        nombre_tripulante: null,
      });
      continue;
    }

    for (const t of tripulantes) {
      if (d.condicion === "solo_panamenos" && !t.es_panameno) continue;
      if (d.condicion === "nacionalidad_restringida" && !t.restringida) continue;
      if (d.requiere_libreta && !t.porta_libreta) continue;
      resultado.push({
        clave: claveCasilla(d.codigo, t.clave),
        documento_codigo: d.codigo,
        documento_nombre: d.nombre,
        descripcion: d.descripcion,
        clave_tripulante: t.clave,
        nombre_tripulante: t.nombre,
      });
    }
  }
  return resultado;
}
