import type { EstadoSolicitud } from "../../api/solicitudes";
import { ETIQUETA_ESTADO } from "./presentacion";
import styles from "./InsigniaEstado.module.css";

interface Props {
  estado: EstadoSolicitud;
  grande?: boolean;
  /** Ladeado, como un sello puesto a mano (el talón del pase). En tablas y
   *  listas va derecho, para leerlo de corrido. */
  inclinado?: boolean;
}

/** Sello con el estado de una solicitud (identidad «pase oficial», 2026-11-11):
 *  doble borde y mayúsculas en el color del estado. Color y texto, nunca solo
 *  color; las mayúsculas son de CSS, así que el texto leído sigue igual. */
export function InsigniaEstado({ estado, grande = false, inclinado = false }: Props) {
  return (
    <span className={`${styles.insignia} ${styles[estado]} ${grande ? styles.grande : ""} ${inclinado ? styles.inclinado : ""}`}>
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  );
}
