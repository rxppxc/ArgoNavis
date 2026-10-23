import type { DocumentoSolicitud } from "../../api/solicitudes";
import { TAMANO_MAX_MB } from "../../utils/archivos";
import { ChecklistDocumentos } from "./ChecklistDocumentos";
import type { DocumentosFormulario } from "./useDocumentosFormulario";
import type { FichaTripulante } from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

interface Props {
  documentos:  DocumentosFormulario;
  tripulantes: FichaTripulante[];
  onIrATripulante: (clave: string) => void;
  onVer:           (documento: DocumentoSolicitud) => void;
}

/** Paso 4 del formulario: cuántos documentos le faltan a cada tripulante (los
 *  suyos se adjuntan en su tarjeta) y los de la solicitud, como la lista de
 *  tripulantes. */
export function ChecklistSolicitud({ documentos, tripulantes, onIrATripulante, onVer }: Props) {
  const { casillas, faltantes, casillasSolicitud, casillasPorTripulante, faltantesPorTripulante } = documentos;
  const faltantesSolicitud = faltantes.filter((c) => c.clave_tripulante === null).length;

  return (
    <section className={styles.bloque}>
      <div className={styles.bloqueTitulo}>
        <span className={styles.paso}>4</span> Documentos de la solicitud
        <span className={faltantes.length === 0 ? styles.contadorOk : styles.contadorFalta}>
          {casillas.length - faltantes.length} / {casillas.length} en total
        </span>
      </div>
      <p className={styles.ayudaSeccion}>PDF, Word o Excel, de hasta {TAMANO_MAX_MB} MB cada uno.</p>
      {tripulantes.some((t) => casillasPorTripulante.has(t.clave)) && (
        <div className={styles.resumenTripulantes}>
          {tripulantes.map((t, i) => {
            const total = casillasPorTripulante.get(t.clave)?.length ?? 0;
            if (!total) return null;
            const faltan = faltantesPorTripulante.get(t.clave) ?? 0;
            return (
              <button key={t.clave} type="button" className={styles.resumenTripulante}
                onClick={() => onIrATripulante(t.clave)} title="Ir a la tarjeta del tripulante">
                {i + 1}. {`${t.nombre} ${t.apellido}`.trim() || "Tripulante sin nombre"}
                {faltan === 0
                  ? <span className={styles.resumenOk}>✓ completo</span>
                  : <span className={styles.resumenFalta}>faltan {faltan}</span>}
              </button>
            );
          })}
        </div>
      )}
      {casillasSolicitud.length > 0 ? (
        <ChecklistDocumentos
          casillas={casillasSolicitud}
          nuevos={documentos.nuevos}
          existentes={documentos.existentes}
          onElegir={documentos.elegir}
          onDescartar={documentos.descartar}
          onVer={onVer}
        />
      ) : (
        <div className={styles.sinDocs}>
          Este trámite no pide documentos de la solicitud: solo los de cada tripulante, en su tarjeta.
        </div>
      )}
      {faltantesSolicitud > 0 && casillasSolicitud.length > 0 && (
        <p className={styles.ayudaSeccion}>
          {faltantesSolicitud === 1 ? "Falta 1 documento" : `Faltan ${faltantesSolicitud} documentos`} de la solicitud.
        </p>
      )}
    </section>
  );
}
