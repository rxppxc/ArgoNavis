import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { useTema, type PreferenciaTema } from "../context/ContextoTema";
import { IconoLuna, IconoMonitor, IconoSol } from "./Iconos";
import styles from "./SelectorTema.module.css";

const OPCIONES: { valor: PreferenciaTema; etiqueta: string; icono: ReactNode }[] = [
  { valor: "light",  etiqueta: "Claro",   icono: <IconoSol tamano={14} /> },
  { valor: "dark",   etiqueta: "Oscuro",  icono: <IconoLuna tamano={13} /> },
  { valor: "system", etiqueta: "Sistema", icono: <IconoMonitor tamano={14} /> },
];

interface Props {
  /** Solo íconos (los nombres quedan para lectores de pantalla). */
  compacto?: boolean;
}

/** Claro / Oscuro / Sistema. Grupo de radio accesible: las flechas mueven la
 *  selección y solo la opción elegida entra en el orden de tabulación. */
export function SelectorTema({ compacto = false }: Props) {
  const { preferencia, elegirPreferencia } = useTema();
  const botones = useRef<(HTMLButtonElement | null)[]>([]);

  function teclas(e: KeyboardEvent<HTMLDivElement>) {
    const paso = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!paso) return;
    e.preventDefault();
    const actual = OPCIONES.findIndex((o) => o.valor === preferencia);
    const siguiente = (actual + paso + OPCIONES.length) % OPCIONES.length;
    elegirPreferencia(OPCIONES[siguiente].valor);
    botones.current[siguiente]?.focus();
  }

  return (
    <div role="radiogroup" aria-label="Tema" className={`${styles.grupo} ${compacto ? styles.compacto : ""}`}
      onKeyDown={teclas}>
      {OPCIONES.map((o, i) => {
        const elegida = o.valor === preferencia;
        return (
          <button key={o.valor} type="button" role="radio" aria-checked={elegida} tabIndex={elegida ? 0 : -1}
            ref={(el) => { botones.current[i] = el; }}
            className={styles.opcion} onClick={() => elegirPreferencia(o.valor)}
            title={compacto ? `Tema: ${o.etiqueta}` : undefined}>
            {o.icono}
            <span className={compacto ? "sr-only" : undefined}>{o.etiqueta}</span>
          </button>
        );
      })}
    </div>
  );
}
