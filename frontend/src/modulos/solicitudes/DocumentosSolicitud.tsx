import { useMemo, useState } from "react";
import { apiSolicitudes, type DocumentoSolicitud, type SolicitudDetalle } from "../../api/solicitudes";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoArchivo, IconoCheck, IconoDescargar, IconoOjo, IconoX } from "../../components/Iconos";
import { mensajeDeError } from "../../utils/errores";
import { formatBytes } from "../../utils/format";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  onVer: (documento: DocumentoSolicitud) => void;
  /** Los de este tripulante (su "documentación"). Sin él, los de la solicitud. */
  tripulanteId?: number;
}

/** Documentos del expediente de un solo dueño, para no mostrar ninguno dos
 *  veces: los de la solicitud (lista de tripulantes, adicionales) o los de un
 *  tripulante, que se abren desde su fila. Ver y descargar exige la sesión y
 *  queda en la bitácora. */
export function DocumentosSolicitud({ solicitud, onVer, tripulanteId }: Props) {
  const { mostrar } = useNotificacion();
  const [descargando, setDescargando] = useState<number | null>(null);
  const dueno = tripulanteId ?? null;   // null = de la solicitud

  const documentosPorId = useMemo(
    () => new Map(solicitud.documentos.map((d) => [d.id, d])),
    [solicitud.documentos],
  );

  const casillas = useMemo(
    () => solicitud.checklist.filter((c) => c.tripulante_id === dueno),
    [solicitud.checklist, dueno],
  );

  const adicionales = useMemo(
    () => solicitud.documentos.filter((d) => d.documento_id === null && d.tripulante_id === dueno),
    [solicitud.documentos, dueno],
  );

  // Documentos de una casilla que ya no aplica (p. ej. cambió la nacionalidad del tripulante)
  const otros = useMemo(() => {
    const usados = new Set(solicitud.checklist.flatMap((c) => c.documento_ids));
    return solicitud.documentos.filter((d) => d.documento_id !== null && !usados.has(d.id) && d.tripulante_id === dueno);
  }, [solicitud.checklist, solicitud.documentos, dueno]);

  async function descargar(documento: DocumentoSolicitud) {
    setDescargando(documento.id);
    try {
      await apiSolicitudes.descargarDocumento(solicitud.id, documento);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar el documento."), "error");
    } finally {
      setDescargando(null);
    }
  }

  const fila = (d: DocumentoSolicitud) => (
    <div key={d.id} className={styles.archivo}>
      <IconoArchivo tamano={13} />
      <span className={styles.archivoNombre} title={d.nombre_original}>{d.nombre_original}</span>
      <span className={styles.archivoPeso}>{formatBytes(d.tamano)}</span>
      <button type="button" className={styles.btnIconoVer} onClick={() => onVer(d)}
        title="Ver documento" aria-label={`Ver ${d.nombre_original}`}>
        <IconoOjo tamano={13} />
      </button>
      <button type="button" className={styles.btnIconoVer} onClick={() => descargar(d)} disabled={descargando === d.id}
        title="Descargar documento" aria-label={`Descargar ${d.nombre_original}`}>
        <IconoDescargar tamano={13} />
      </button>
    </div>
  );

  if (casillas.length === 0 && adicionales.length === 0 && otros.length === 0) {
    return <p className={styles.vacio}>Sin documentos.</p>;
  }

  return (
    <div className={styles.documentos}>
      {casillas.length > 0 && (
        <div className={styles.grupoDocs}>
          {casillas.map((c) => (
            <div key={`${c.documento_id}-${c.tripulante_id ?? "s"}`} className={styles.casilla}>
              <div className={styles.casillaCabecera}>
                {c.cubierta
                  ? <span className={styles.casillaOk}><IconoCheck tamano={12} /></span>
                  : <span className={styles.casillaFalta}><IconoX tamano={12} /></span>}
                <span className={styles.casillaNombre}>{c.documento_nombre}</span>
                {!c.cubierta && <span className={styles.textoFalta}>Falta</span>}
              </div>
              {c.documento_ids.map((id) => {
                const documento = documentosPorId.get(id);
                return documento ? fila(documento) : null;
              })}
            </div>
          ))}
        </div>
      )}
      {adicionales.length > 0 && (
        <div className={styles.grupoDocs}>
          <div className={styles.grupoTitulo}>Documentos adicionales</div>
          {adicionales.map(fila)}
        </div>
      )}
      {otros.length > 0 && (
        <div className={styles.grupoDocs}>
          <div className={styles.grupoTitulo}>Otros documentos</div>
          {otros.map(fila)}
        </div>
      )}
    </div>
  );
}
