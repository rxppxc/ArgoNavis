/**
 * La hora de Panamá y si es horario laboral, en el inicio de cada rol (pedido del usuario del
 * 2026-11-24: en todos los roles, con el horario y bien integrado; solo en el inicio).
 * - Se ve como el sello de fecha y hora de un documento: la franja arriba, la hora en letra de
 *   máquina y el estado como sello de tinta. Verde en horario y morado fuera, el color del chip
 *   «Aprobada fuera del horario».
 * - Va en franja, de borde a borde bajo el encabezado de la página (2026-11-27): entre las acciones
 *   del encabezado no cabía junto al título y saltaba a otra línea.
 * - Es la hora de Panamá aunque el equipo tenga otra zona (utils/horario.ts, espejo de
 *   core/horario.py). Cambia sola con el minuto (useMinutoActual) y no se anuncia al lector de
 *   pantalla: se lee al llegar a ella.
 */
import { useMinutoActual } from "../hooks/useMinutoActual";
import { fechaLarga } from "../utils/calendario";
import { dosCifras } from "../utils/fechas";
import { TEXTO_HORARIO_LABORAL, enPanama, estadoHorario } from "../utils/horario";
import { IconoReloj } from "./Iconos";
import styles from "./RelojHorario.module.css";

interface Props {
  /** Fuera del horario, recuerda que lo que se apruebe lleva recargo. No al SysAdmin, que no
   *  ve solicitudes. */
  conRecargo?: boolean;
  /** El espacio alrededor lo pone quien lo usa. */
  className?: string;
}

export function RelojHorario({ conRecargo = true, className }: Props) {
  const ahora = useMinutoActual();
  const { iso, hora, minuto } = enPanama(ahora);
  const { laboral, hasta } = estadoHorario(ahora);
  const hhmm = `${dosCifras(hora)}:${dosCifras(minuto)}`;

  return (
    <div className={`${styles.reloj} ${className ?? ""}`} data-horario={laboral ? "laboral" : "fuera"}
      role="group" aria-labelledby="reloj-horario-rotulo">
      {/* A la izquierda, lo que importa: la hora, el sello, «hasta …» y el recargo. */}
      <div className={styles.estado}>
        <p className={styles.principal}>
          <span id="reloj-horario-rotulo" className={styles.rotulo}>Hora de Panamá</span>
          {" "}<time className={styles.hora} dateTime={`${iso}T${hhmm}-05:00`}>{hhmm}</time>
          {" "}<span className={styles.sello}>{laboral ? "Horario laboral" : "Fuera del horario"}</span>
          {" "}<span className={styles.hasta}>hasta {hasta}</span>
        </p>
        {!laboral && conRecargo && <p className={styles.recargo}>Lo que se apruebe ahora lleva recargo.</p>}
      </div>
      {/* A la derecha, la referencia: la fecha y el horario. */}
      <p className={styles.datos}>
        <span className={styles.fecha}>{fechaLarga(iso)}</span>
        {" "}<span className={styles.horario}><IconoReloj tamano={12} /> Horario: {TEXTO_HORARIO_LABORAL}</span>
      </p>
    </div>
  );
}
