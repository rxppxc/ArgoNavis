import type { DocumentoSolicitud } from "../../api/solicitudes";
import { IconoArchivo, IconoCheck, IconoOjo, IconoX } from "../../components/Iconos";
import { TIPOS_ACEPTADOS } from "../../utils/archivos";
import { formatBytes } from "../../utils/format";
import styles from "./PaginaSolicitud.module.css";

/** Máximo de documentos adicionales por solicitud (igual que el backend). */
export const MAX_ADICIONALES = 20;

export interface AdicionalNuevo {
  clave: string;
  archivo: File;
}

interface Props {
  /** Ya cargados en la solicitud que se corrige (se conservan salvo que se quiten). */
  existentes: DocumentoSolicitud[];
  nuevos:     AdicionalNuevo[];
  onAgregar:        (archivos: File[]) => void;
  onQuitarNuevo:    (clave: string) => void;
  onQuitarExistente: (id: number) => void;
  onVer:            (documento: DocumentoSolicitud) => void;
}

/** Documentos fuera del checklist (cartas, oficios u otros soportes): van al
 *  expediente igual que los requeridos, pero no son obligatorios. */
export function DocumentosAdicionales({
  existentes, nuevos, onAgregar, onQuitarNuevo, onQuitarExistente, onVer,
}: Props) {
  const total = existentes.length + nuevos.length;
  return (
    <div className={styles.casillas}>
      {existentes.map((d) => (
        <div key={`e${d.id}`} className={`${styles.casilla} ${styles.casillaOk}`}>
          <div className={styles.casillaInfo}>
            <div className={styles.casillaDoc}><IconoArchivo tamano={13} /> {d.nombre_original}</div>
            <div className={styles.casillaAlcance}>Cargado · {formatBytes(d.tamano)}</div>
          </div>
          <div className={styles.casillaAccion}>
            <button type="button" className={styles.btnMini} onClick={() => onVer(d)} title="Ver documento">
              <IconoOjo tamano={13} />
            </button>
            <button type="button" className={styles.btnMini} onClick={() => onQuitarExistente(d.id)}
              title="Quitar del expediente" aria-label={`Quitar ${d.nombre_original}`}>
              <IconoX tamano={12} />
            </button>
          </div>
        </div>
      ))}
      {nuevos.map((n) => (
        <div key={n.clave} className={`${styles.casilla} ${styles.casillaOk}`}>
          <div className={styles.casillaInfo}>
            <div className={styles.casillaDoc}><IconoCheck tamano={12} /> {n.archivo.name}</div>
            <div className={styles.casillaAlcance}>Nuevo · {formatBytes(n.archivo.size)}</div>
          </div>
          <div className={styles.casillaAccion}>
            <button type="button" className={styles.btnMini} onClick={() => onQuitarNuevo(n.clave)}
              title="Quitar" aria-label={`Quitar ${n.archivo.name}`}>
              <IconoX tamano={12} />
            </button>
          </div>
        </div>
      ))}
      {total === 0 && <div className={styles.sinDocs}>Sin documentos adicionales.</div>}
      {total < MAX_ADICIONALES && (
        <label className={styles.btnArchivo}>
          Agregar documento
          <input type="file" hidden multiple accept={TIPOS_ACEPTADOS}
            onChange={(e) => {
              const archivos = Array.from(e.target.files ?? []);
              if (archivos.length) onAgregar(archivos);
              e.target.value = "";
            }} />
        </label>
      )}
    </div>
  );
}
