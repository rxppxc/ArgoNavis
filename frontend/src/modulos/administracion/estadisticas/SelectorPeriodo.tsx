import { useState } from "react";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { IconoReloj } from "../../../components/Iconos";
import { PRESETS, fechaISO, presetDeRango, rangoDePreset } from "./calculos";
import styles from "./Estadisticas.module.css";

/** El periodo de las estadísticas: atajos (el mes pasado sirve para el informe
 *  mensual) y, con «Otras fechas», desde y hasta. Acota todo lo que hay debajo. */
export default function SelectorPeriodo({ valor, onCambio }: { valor: RangoFechas; onCambio: (r: RangoFechas) => void }) {
  const hoy = new Date();
  const hoyISO = fechaISO(hoy);
  const preset = presetDeRango(valor, hoy);
  const [otrasFechas, setOtrasFechas] = useState(preset === null);

  function cambiarDesde(desde: string | null) {
    // Con el desde después del hasta no habría nada que contar: el hasta lo sigue.
    onCambio({ desde, hasta: desde && valor.hasta && valor.hasta < desde ? desde : valor.hasta });
  }
  function cambiarHasta(hasta: string | null) {
    onCambio({ desde: hasta && valor.desde && valor.desde > hasta ? hasta : valor.desde, hasta });
  }

  return (
    <div className={styles.periodo} role="group" aria-label="Periodo de las estadísticas">
      <span className={styles.periodoIcono}><IconoReloj tamano={15} /></span>
      <div className={styles.chips}>
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={styles.chip}
            aria-pressed={!otrasFechas && preset === p.id}
            onClick={() => { setOtrasFechas(false); onCambio(rangoDePreset(p.id, hoy)); }}
          >
            {p.etiqueta}
          </button>
        ))}
        <button type="button" className={styles.chip} aria-pressed={otrasFechas} onClick={() => setOtrasFechas(true)}>
          Otras fechas
        </button>
      </div>
      {otrasFechas && (
        <div className={styles.fechas}>
          <label>
            Desde
            <input type="date" value={valor.desde ?? ""} max={hoyISO} onChange={(e) => cambiarDesde(e.target.value || null)} />
          </label>
          <label>
            Hasta
            <input type="date" value={valor.hasta ?? ""} max={hoyISO} onChange={(e) => cambiarHasta(e.target.value || null)} />
          </label>
        </div>
      )}
    </div>
  );
}
