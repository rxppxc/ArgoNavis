import styles from "./EstadoCarga.module.css";

/** Mientras llega algo del servidor: el mismo giro y qué se está cargando en
 *  todas las pantallas (antes unas tenían giro, otras solo texto). */
export function EstadoCarga({ texto = "Cargando…", pagina = false }: { texto?: string; pagina?: boolean }) {
  return (
    <div className={pagina ? styles.pagina : styles.seccion} role="status">
      <span className={styles.giro} aria-hidden="true" />
      {texto}
    </div>
  );
}

/** Mientras llega el código de una página que se carga aparte (administración). */
export function CargandoRuta() {
  return (
    <div className={styles.ruta} role="status" aria-label="Cargando">
      <span className={`${styles.giro} ${styles.giroGrande}`} aria-hidden="true" />
    </div>
  );
}
