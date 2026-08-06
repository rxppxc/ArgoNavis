import { IconoReloj } from "./Iconos";
import styles from "./FiltroFechas.module.css";

/** Rango de fechas seleccionado. Fechas en formato ISO `YYYY-MM-DD` (o null = sin límite). */
export interface RangoFechas {
  desde: string | null;
  hasta: string | null;
}

type Preset = "todas" | "hoy" | "7d";

const PRESETS: { id: Preset; etiqueta: string }[] = [
  { id: "todas", etiqueta: "Todas" },
  { id: "hoy",   etiqueta: "Hoy" },
  { id: "7d",    etiqueta: "7 días" },
];

/** Fecha local (no UTC) en formato YYYY-MM-DD — evita el desfase de zona horaria de toISOString. */
function fechaLocalISO(d: Date): string {
  const y  = d.getFullYear();
  const m  = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function haceDias(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return fechaLocalISO(d);
}

interface Props {
  valor: RangoFechas;
  onCambio: (r: RangoFechas) => void;
}

export default function FiltroFechas({ valor, onCambio }: Props) {
  const hoy = fechaLocalISO(new Date());

  // El preset activo se deriva directamente del valor — sin estado propio,
  // así el filtro nunca puede desincronizarse de lo que ve el padre.
  const preset: Preset =
    valor.desde === hoy && valor.hasta === hoy ? "hoy"
    : valor.desde === haceDias(6) && valor.hasta === hoy ? "7d"
    : "todas";

  function aplicar(p: Preset) {
    if (p === "todas") onCambio({ desde: null, hasta: null });
    else if (p === "hoy") onCambio({ desde: hoy, hasta: hoy });
    else onCambio({ desde: haceDias(6), hasta: hoy });
  }

  return (
    <div className={styles.barra}>
      <span className={styles.icono}><IconoReloj tamano={15} /></span>
      <div className={styles.chips}>
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`${styles.chip} ${preset === p.id ? styles.chipActivo : ""}`}
            onClick={() => aplicar(p.id)}
          >
            {p.etiqueta}
          </button>
        ))}
      </div>
    </div>
  );
}
