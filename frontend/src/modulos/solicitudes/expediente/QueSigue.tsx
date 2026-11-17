import { IconoCheck } from "../../../components/Iconos";
import type { PasoSiguiente } from "./pasosSiguientes";
import styles from "./QueSigue.module.css";

/** «Qué sigue» (rediseño visual del 2026-11-17): los pasos que le tocan a quien mira, en
 *  orden, con los hechos marcados. Sin pasos no se muestra (pasosSiguientes). */
export function QueSigue({ pasos }: { pasos: PasoSiguiente[] }) {
  if (pasos.length === 0) return null;
  return (
    <section className={styles.queSigue} aria-labelledby="que-sigue-titulo">
      <h2 id="que-sigue-titulo" className={styles.titulo}>Qué sigue</h2>
      <ol className={styles.pasos}>
        {pasos.map((p, i) => (
          <li key={p.texto} className={p.hecho ? styles.hecho : undefined}>
            <span className={styles.numero} aria-hidden="true">{p.hecho ? <IconoCheck tamano={13} /> : i + 1}</span>
            <span className={styles.texto}>
              {p.texto}
              {p.hecho && <span className="sr-only"> (hecho)</span>}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
