import { useState } from "react";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { IconoReloj } from "../../../components/Iconos";
import { SelectorFecha } from "../../../components/SelectorFecha";
import { fechaISOLocal } from "../../../utils/fechas";
import { PRESETS, presetDeRango, rangoDePreset } from "./calculos";
import styles from "./Estadisticas.module.css";

/** El periodo de las estadísticas: atajos (el mes pasado sirve para el informe
 *  mensual) y, con «Otras fechas», desde y hasta. Acota todo lo que hay debajo. */
export default function SelectorPeriodo({ valor, onCambio }: { valor: RangoFechas; onCambio: (r: RangoFechas) => void }) {
  const hoy = new Date();
  const hoyISO = fechaISOLocal(hoy);
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
          {/* Hasta hoy: lo que viene no tiene datos (va rayado en el calendario). */}
          <SelectorFecha className={styles.campoFecha} etiqueta="Desde" valor={valor.desde ?? ""}
            onCambiar={(iso) => cambiarDesde(iso || null)} max={hoyISO}
            motivoDespues="Las estadísticas llegan hasta hoy." atajos={[{ etiqueta: "Hoy", fecha: hoyISO }]}
            borrable nota={false} />
          <SelectorFecha className={styles.campoFecha} etiqueta="Hasta" valor={valor.hasta ?? ""}
            onCambiar={(iso) => cambiarHasta(iso || null)} max={hoyISO}
            motivoDespues="Las estadísticas llegan hasta hoy." atajos={[{ etiqueta: "Hoy", fecha: hoyISO }]}
            borrable nota={false} />
        </div>
      )}
    </div>
  );
}
