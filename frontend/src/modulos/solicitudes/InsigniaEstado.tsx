import type { EstadoSolicitud } from "../../api/solicitudes";
import { ETIQUETA_ESTADO } from "./presentacion";
import styles from "./InsigniaEstado.module.css";

/** Pastilla con el estado de una solicitud (color + texto, nunca solo color). */
export function InsigniaEstado({ estado, grande = false }: { estado: EstadoSolicitud; grande?: boolean }) {
  return (
    <span className={`${styles.insignia} ${styles[estado]} ${grande ? styles.grande : ""}`}>
      <span className={styles.punto} aria-hidden="true" />
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  );
}
