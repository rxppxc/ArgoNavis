import type { DocumentoSolicitud } from "../../../api/solicitudes";
import { IconoArchivo, IconoCheck, IconoOjo, IconoUsuario, IconoX } from "../../../components/Iconos";
import { TIPOS_ACEPTADOS } from "../../../utils/archivos";
import type { CasillaFormulario } from "../checklist";
import { archivosDeCasilla } from "./envioSolicitud";
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
  /** En las casillas que admiten varios archivos (la Form. 7, 2026-11-27): agregar otro y quitar
   *  uno ya cargado. Las de cada tripulante admiten uno: su tarjeta no los pasa. */
  onElegirOtro?:      (clave: string, archivo: File) => void;
  onQuitarExistente?: (clave: string, id: number) => void;
}

/** Una fila por documento exigible: adjuntar, reemplazar o ver lo ya cargado. */
export function ChecklistDocumentos({
  casillas, nuevos, existentes, sinTripulante = false, onElegir, onDescartar, onVer, onElegirOtro, onQuitarExistente,
}: Props) {
  if (casillas.length === 0) {
    return <div className={styles.sinDocs}>Este trámite no exige documentos adjuntos.</div>;
  }

  return (
    <div className={styles.casillas}>
      {casillas.map((c) => {
        if (c.maximo > 1 && onElegirOtro && onQuitarExistente) {
          return (
            <CasillaConVarios key={c.clave} c={c} propios={archivosDeCasilla(nuevos, c.clave)}
              cargados={existentes[c.clave] ?? []} onElegir={onElegir} onElegirOtro={onElegirOtro}
              onDescartar={onDescartar} onQuitarExistente={onQuitarExistente} onVer={onVer} />
          );
        }
        const nuevo = nuevos[c.clave];
        const cargados = existentes[c.clave] ?? [];
        const cubierta = !!nuevo || cargados.length > 0;
        return (
          <div key={c.clave} className={`${styles.casilla} ${cubierta ? styles.casillaOk : ""}`}>
            <div className={styles.casillaInfo}>
              <div className={styles.casillaDoc}>
                {c.clave_tripulante === null ? <IconoArchivo tamano={13} /> : <IconoUsuario tamano={13} />}
                {c.documento_nombre}
                {!c.obligatoria && <span className={styles.casillaOpcional}>Opcional</span>}
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
                    title={cargados.length ? "Conservar el archivo ya cargado" : "Quitar archivo"}
                    aria-label={cargados.length ? `Conservar el archivo ya cargado de ${c.documento_nombre}` : `Quitar ${nuevo.name}`}>
                    <IconoX tamano={12} />
                  </button>
                </>
              ) : cargados.length > 0 ? (
                <>
                  <span className={styles.archivoCargado} title={cargados[0].nombre_original}>
                    Cargado: {cargados[0].nombre_original}
                  </span>
                  <button type="button" className={styles.btnMiniVer} onClick={() => onVer(cargados[0])}
                    title="Ver documento cargado" aria-label={`Ver ${cargados[0].nombre_original}`}>
                    <IconoOjo tamano={13} />
                  </button>
                </>
              ) : null}
              <label className={styles.btnArchivo}>
                {nuevo || cargados.length ? "Reemplazar" : "Adjuntar"}
                {/* Nombre completo para lectores de pantalla: «Adjuntar» solo no dice cuál. */}
                <input type="file" hidden accept={TIPOS_ACEPTADOS}
                  aria-label={`${nuevo || cargados.length ? "Reemplazar" : "Adjuntar"} ${c.documento_nombre}`
                    + (c.nombre_tripulante ? ` de ${c.nombre_tripulante}` : "")
                    + (c.obligatoria ? "" : " (opcional)")}
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

/** Una casilla que admite varios archivos (la Form. 7 de Renovación, Urgencias y Técnico, 2026-11-27):
 *  uno obligatorio y, debajo, «Agregar otra (opcional)» hasta su máximo. Cada archivo se quita por
 *  separado; al corregir, los ya cargados se conservan salvo los que se quiten. */
function CasillaConVarios({ c, propios, cargados, onElegir, onElegirOtro, onDescartar, onQuitarExistente, onVer }: {
  c: CasillaFormulario;
  propios: [string, File][];
  cargados: DocumentoSolicitud[];
  onElegir: (clave: string, archivo: File) => void;
  onElegirOtro: (clave: string, archivo: File) => void;
  onDescartar: (clave: string) => void;
  onQuitarExistente: (clave: string, id: number) => void;
  onVer: (documento: DocumentoSolicitud) => void;
}) {
  const total = propios.length + cargados.length;
  const ninguno = total === 0;
  return (
    <div className={`${styles.casilla} ${styles.casillaVarios} ${ninguno ? "" : styles.casillaOk}`}>
      <div className={styles.casillaInfo}>
        <div className={styles.casillaDoc}>
          <IconoArchivo tamano={13} />
          {c.documento_nombre}
        </div>
        <div className={styles.casillaAlcance}>
          De la solicitud · una obligatoria; puedes agregar hasta {c.maximo - 1} más, opcionales
          {c.descripcion && <> · {c.descripcion}</>}
        </div>
      </div>
      <div className={styles.casillaArchivos}>
        {cargados.map((d) => (
          <div key={d.id} className={styles.archivoFila}>
            <span className={styles.archivoCargado} title={d.nombre_original}>Cargado: {d.nombre_original}</span>
            <button type="button" className={styles.btnMiniVer} onClick={() => onVer(d)}
              title="Ver documento cargado" aria-label={`Ver ${d.nombre_original}`}>
              <IconoOjo tamano={13} />
            </button>
            <button type="button" className={styles.btnMiniQuitar} onClick={() => onQuitarExistente(c.clave, d.id)}
              title="Quitar" aria-label={`Quitar ${d.nombre_original}`}>
              <IconoX tamano={12} />
            </button>
          </div>
        ))}
        {propios.map(([clave, archivo]) => (
          <div key={clave} className={styles.archivoFila}>
            <span className={styles.archivoNombre} title={archivo.name}><IconoCheck tamano={12} /> {archivo.name}</span>
            <button type="button" className={styles.btnMiniQuitar} onClick={() => onDescartar(clave)}
              title="Quitar archivo" aria-label={`Quitar ${archivo.name}`}>
              <IconoX tamano={12} />
            </button>
          </div>
        ))}
        {total < c.maximo && (
          <label className={styles.btnArchivo}>
            {ninguno ? "Adjuntar" : "Agregar otra (opcional)"}
            <input type="file" hidden accept={TIPOS_ACEPTADOS}
              aria-label={ninguno ? `Adjuntar ${c.documento_nombre}` : `Agregar otra ${c.documento_nombre} (opcional)`}
              onChange={(e) => {
                const archivo = e.target.files?.[0];
                if (archivo) (ninguno ? onElegir : onElegirOtro)(c.clave, archivo);
                e.target.value = "";
              }} />
          </label>
        )}
      </div>
    </div>
  );
}
