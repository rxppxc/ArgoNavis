import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./CabeceraInstitucional.module.css";

interface Props {
  derecha?: ReactNode;
  /** Con sesión, el escudo lleva al inicio (como el logo de cualquier sitio):
   *  antes la única forma de volver era "Volver". */
  inicio?: string;
}

/** Franja institucional de todas las páginas, la misma del login: escudo del
 *  SNM a la izquierda, jerarquía al centro y, a la derecha, lo que toque (el
 *  menú del usuario; en el login y en las páginas públicas, nada). */
export function CabeceraInstitucional({ derecha, inicio }: Props) {
  return (
    <header className={styles.franja}>
      <div className={styles.interior}>
        {inicio ? (
          <Link to={inicio} className={styles.inicio} aria-label="Ir al inicio" title="Ir al inicio">
            <img src="/images/logo-snm.png" alt="" className={styles.escudo} />
          </Link>
        ) : (
          <img src="/images/logo-snm.png" alt="Escudo del Servicio Nacional de Migración" className={styles.escudo} />
        )}
        <div className={styles.jerarquia}>
          <small>República de Panamá</small>
          <small>Ministerio de Seguridad Pública</small>
          <strong>Servicio Nacional de Migración</strong>
        </div>
        <div className={styles.derecha}>{derecha}</div>
      </div>
      <div className={styles.bandera} aria-hidden="true" />
    </header>
  );
}
