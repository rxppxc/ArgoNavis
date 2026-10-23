/**
 * Documentos del formulario de solicitud: el checklist que piden el trámite y
 * los tripulantes, los archivos elegidos para cada casilla, los ya cargados
 * (al corregir) y los adicionales. Las funciones que reciben las tarjetas de
 * los tripulantes (elegir, descartar) son estables: están memoizadas.
 */
import { useCallback, useMemo, useState } from "react";
import type { Pais } from "../../api/catalogos";
import type { DocumentoSolicitud } from "../../api/solicitudes";
import type { TipoTramite } from "../../api/tramites";
import { useNotificacion } from "../../components/Notificaciones";
import { validarArchivos } from "../../utils/archivos";
import { claveCasilla, construirCasillas, type CasillaFormulario } from "./checklist";
import { MAX_ADICIONALES, type AdicionalNuevo } from "./DocumentosAdicionales";
import { nuevaClave, type DocumentosElegidos, type Precarga } from "./envioSolicitud";
import { portaLibreta, type FichaTripulante } from "./validacionFormulario";

const SIN_EXISTENTES: Record<string, DocumentoSolicitud[]> = {};

export interface DocumentosFormulario extends DocumentosElegidos {
  /** Casillas sin archivo nuevo ni cargado. */
  faltantes: CasillaFormulario[];
  /** Las de la solicitud (lista de tripulantes, carta, reporte médico); las de
   *  cada tripulante van en su tarjeta. */
  casillasSolicitud: CasillaFormulario[];
  casillasPorTripulante: Map<string, CasillaFormulario[]>;
  faltantesPorTripulante: Map<string, number>;
  elegir: (clave: string, archivo: File) => void;
  descartar: (clave: string) => void;
  /** Quita los archivos elegidos para un tripulante (al quitarlo del formulario). */
  descartarDeTripulante: (claveTripulante: string) => void;
  /** Quita los archivos elegidos del checklist (al cambiar de trámite). */
  descartarTodos: () => void;
  agregarAdicionales: (archivos: File[]) => void;
  quitarAdicionalNuevo: (clave: string) => void;
  quitarAdicionalExistente: (id: number) => void;
}

export function useDocumentosFormulario(
  tipo: TipoTramite | null,
  tripulantes: FichaTripulante[],
  paisesPorCodigo: Map<string, Pais>,
  precarga: Precarga | null,
): DocumentosFormulario {
  const { mostrar } = useNotificacion();
  const [nuevos, setNuevos] = useState<Record<string, File>>({});
  const [adicionalesNuevos, setAdicionalesNuevos] = useState<AdicionalNuevo[]>([]);
  const [adicionalesExistentes, setAdicionalesExistentes] = useState<DocumentoSolicitud[]>(
    () => precarga?.adicionales ?? [],
  );
  const existentes = precarga?.existentes ?? SIN_EXISTENTES;

  const casillas = useMemo(() => {
    if (!tipo) return [];
    return construirCasillas(
      tipo,
      tripulantes.map((t) => ({
        clave: t.clave,
        nombre: `${t.nombre} ${t.apellido}`.trim() || "Tripulante sin nombre",
        es_panameno: t.nacionalidad === "PAN",
        porta_libreta: portaLibreta(t),
        restringida: paisesPorCodigo.get(t.nacionalidad)?.nacionalidad_restringida ?? false,
      })),
    );
  }, [tipo, tripulantes, paisesPorCodigo]);

  const faltantes = useMemo(
    () => casillas.filter((c) => !nuevos[c.clave] && !(existentes[c.clave]?.length)),
    [casillas, nuevos, existentes],
  );

  const casillasSolicitud = useMemo(() => casillas.filter((c) => c.clave_tripulante === null), [casillas]);
  const casillasPorTripulante = useMemo(() => {
    const grupos = new Map<string, CasillaFormulario[]>();
    for (const c of casillas) {
      if (c.clave_tripulante !== null) grupos.set(c.clave_tripulante, [...(grupos.get(c.clave_tripulante) ?? []), c]);
    }
    return grupos;
  }, [casillas]);
  const faltantesPorTripulante = useMemo(() => {
    const conteo = new Map<string, number>();
    for (const c of faltantes) {
      if (c.clave_tripulante !== null) conteo.set(c.clave_tripulante, (conteo.get(c.clave_tripulante) ?? 0) + 1);
    }
    return conteo;
  }, [faltantes]);

  const elegir = useCallback((clave: string, archivo: File) => {
    const problema = validarArchivos([archivo]);
    if (problema) {
      mostrar(problema, "error");
      return;
    }
    setNuevos((prev) => ({ ...prev, [clave]: archivo }));
  }, [mostrar]);

  const descartar = useCallback((clave: string) => {
    setNuevos((prev) => {
      const siguiente = { ...prev };
      delete siguiente[clave];
      return siguiente;
    });
  }, []);

  const descartarDeTripulante = useCallback((claveTripulante: string) => {
    const sufijo = claveCasilla("", claveTripulante);
    setNuevos((prev) => Object.fromEntries(Object.entries(prev).filter(([clave]) => !clave.endsWith(sufijo))));
  }, []);

  function descartarTodos() {
    setNuevos({});
  }

  function agregarAdicionales(archivos: File[]) {
    const problema = validarArchivos(archivos);
    if (problema) {
      mostrar(problema, "error");
      return;
    }
    const libres = MAX_ADICIONALES - adicionalesExistentes.length - adicionalesNuevos.length;
    if (archivos.length > libres) {
      mostrar(`Se admiten hasta ${MAX_ADICIONALES} documentos adicionales por solicitud.`, "aviso");
    }
    const aceptados = archivos.slice(0, Math.max(libres, 0)).map((archivo) => ({ clave: nuevaClave("a"), archivo }));
    setAdicionalesNuevos((prev) => [...prev, ...aceptados]);
  }

  function quitarAdicionalNuevo(clave: string) {
    setAdicionalesNuevos((prev) => prev.filter((a) => a.clave !== clave));
  }

  function quitarAdicionalExistente(id: number) {
    setAdicionalesExistentes((prev) => prev.filter((d) => d.id !== id));
  }

  return {
    casillas, faltantes, casillasSolicitud, casillasPorTripulante, faltantesPorTripulante,
    nuevos, existentes, adicionalesNuevos, adicionalesExistentes,
    elegir, descartar, descartarDeTripulante, descartarTodos,
    agregarAdicionales, quitarAdicionalNuevo, quitarAdicionalExistente,
  };
}
