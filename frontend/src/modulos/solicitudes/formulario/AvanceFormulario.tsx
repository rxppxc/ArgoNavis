import { IconoCheck } from "../../../components/Iconos";
import type { PasoAvance } from "./pasosDelFormulario";
import styles from "./AvanceFormulario.module.css";

/** El avance del formulario (rediseño visual del 2026-11-17): los cuatro pasos obligatorios,
 *  cada uno listo (✓) o con lo que le falta, y un enlace a su sección. */
export function AvanceFormulario({ pasos }: { pasos: PasoAvance[] }) {
  return (
    <nav className={styles.avance} aria-label="Avance de la solicitud">
      <ol className={styles.pasos}>
        {pasos.map((p) => (
          <li key={p.numero} className={p.completo ? styles.completo : undefined}>
            <a href={`#${p.ancla}`} className={styles.enlace}>
              <span className={styles.numero} aria-hidden="true">{p.completo ? <IconoCheck tamano={13} /> : p.numero}</span>
              <span className={styles.texto}>
                <span className={styles.titulo}>{p.titulo}</span>
                <span className={styles.detalle}>{p.detalle}</span>
              </span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
