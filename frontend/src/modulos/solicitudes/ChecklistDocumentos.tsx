import type { DocumentoSolicitud } from "../../api/solicitudes";
import { IconoArchivo, IconoCheck, IconoOjo, IconoUsuario, IconoX } from "../../components/Iconos";
import { TIPOS_ACEPTADOS } from "../../utils/archivos";
import type { CasillaFormulario } from "./checklist";
import styles from "./PaginaSolicitud.module.css";

interface Props {
  casillas:   CasillaFormulario[];
  /** Archivos elegidos ahora, por clave de casilla. */
  nuevos:     Record<string, File>;
  /** Archivos ya cargados (solo al corregir), por clave de casilla. */
  existentes: Record<string, DocumentoSolicitud[]>;
  /** Dentro de la tarjeta de un tripulante: no repite su nombre en cada casilla. */
  sinTripulante?: boolean;
  onElegir:    (clave: string, archivo: File) => void;
  onDescartar: (clave: string) => void;
  onVer:       (documento: DocumentoSolicitud) => void;
}

/** Una fila por documento exigible: adjuntar, reemplazar o ver lo ya cargado. */
export function ChecklistDocumentos({ casillas, nuevos, existentes, sinTripulante = false, onElegir, onDescartar, onVer }: Props) {
  if (casillas.length === 0) {
    return <div className={styles.sinDocs}>Este trámite no exige documentos adjuntos.</div>;
  }

  return (
    <div className={styles.casillas}>
      {casillas.map((c) => {
        const nuevo = nuevos[c.clave];
        const cargados = existentes[c.clave] ?? [];
        const cubierta = !!nuevo || cargados.length > 0;
        return (
          <div key={c.clave} className={`${styles.casilla} ${cubierta ? styles.casillaOk : ""}`}>
            <div className={styles.casillaInfo}>
              <div className={styles.casillaDoc}>
                {c.clave_tripulante === null ? <IconoArchivo tamano={13} /> : <IconoUsuario tamano={13} />}
                {c.documento_nombre}
              </div>
              {sinTripulante ? (
                c.descripcion && <div className={styles.casillaAlcance}>{c.descripcion}</div>
              ) : (
                <div className={styles.casillaAlcance}>
                  {c.nombre_tripulante ?? "De la solicitud"}
                  {c.descripcion && <> · {c.descripcion}</>}
                </div>
              )}
            </div>
            <div className={styles.casillaAccion}>
              {nuevo ? (
                <>
                  <span className={styles.archivoNombre} title={nuevo.name}>
                    <IconoCheck tamano={12} /> {nuevo.name}
                  </span>
                  <button type="button" className={styles.btnMiniQuitar} onClick={() => onDescartar(c.clave)}
                    title={cargados.length ? "Conservar el archivo ya cargado" : "Quitar archivo"}>
                    <IconoX tamano={12} />
                  </button>
                </>
              ) : cargados.length > 0 ? (
                <>
                  <span className={styles.archivoCargado} title={cargados[0].nombre_original}>
                    Cargado: {cargados[0].nombre_original}
                  </span>
                  <button type="button" className={styles.btnMiniVer} onClick={() => onVer(cargados[0])}
                    title="Ver documento cargado">
                    <IconoOjo tamano={13} />
                  </button>
                </>
              ) : null}
              <label className={styles.btnArchivo}>
                {nuevo || cargados.length ? "Reemplazar" : "Adjuntar"}
                {/* Nombre completo para lectores de pantalla: «Adjuntar» solo no dice cuál. */}
                <input type="file" hidden accept={TIPOS_ACEPTADOS}
                  aria-label={`${nuevo || cargados.length ? "Reemplazar" : "Adjuntar"} ${c.documento_nombre}`
                    + (c.nombre_tripulante ? ` de ${c.nombre_tripulante}` : "")}
                  onChange={(e) => {
                    const archivo = e.target.files?.[0];
                    if (archivo) onElegir(c.clave, archivo);
                    e.target.value = "";
                  }} />
              </label>
            </div>
          </div>
        );
      })}
    </div>
  );
}
