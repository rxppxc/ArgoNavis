import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./CabeceraInstitucional.module.css";

interface Props {
  derecha?: ReactNode;
  /** Con sesión, el escudo lleva al inicio (como el logo de cualquier sitio):
   *  antes la única forma de volver era "Volver". */
  inicio?: string;
}

/** Línea de microtexto de la cabecera, como la de un pasaporte (decorativa). */
const MICROTEXTO = "Servicio Nacional de Migración · ARGO NAVIS · República de Panamá · Sistema Interno Marítimo · "
  .repeat(8);

/** Cabecera de todas las páginas, también la del login (identidad «pase
 *  oficial», 2026-11-11): la hoja de un documento oficial, con la franja
 *  amarilla del escudo arriba, el escudo y la institución a la izquierda, la
 *  marca ARGO NAVIS y, a la derecha, lo que toque (la campana y el menú del
 *  usuario; en el login y en las páginas públicas, nada). */
export function CabeceraInstitucional({ derecha, inicio }: Props) {
  return (
    <header className={styles.cabecera}>
      <div className={styles.franja} aria-hidden="true" />
      <div className={styles.interior}>
        {inicio ? (
          <Link to={inicio} className={styles.inicio} aria-label="Ir al inicio" title="Ir al inicio">
            <img src="/images/logo-snm.png" alt="" className={styles.escudo} />
          </Link>
        ) : (
          <img src="/images/logo-snm.png" alt="Escudo del Servicio Nacional de Migración" className={styles.escudo} />
        )}
        <div className={styles.institucion}>
          <small>República de Panamá · Ministerio de Seguridad Pública</small>
          <strong>Servicio Nacional de Migración</strong>
        </div>
        <div className={styles.marca}>
          <b>ARGO NAVIS</b>
          <small>Sistema Interno Marítimo</small>
        </div>
        <div className={styles.derecha}>{derecha}</div>
      </div>
      <div className={styles.microtexto} aria-hidden="true">{MICROTEXTO}</div>
    </header>
  );
}
