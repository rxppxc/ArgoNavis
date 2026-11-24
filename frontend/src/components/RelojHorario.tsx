/**
 * La hora de Panamá y si es horario laboral, en el inicio de cada rol (pedido del usuario del
 * 2026-11-24: en todos los roles, con el horario y bien integrado; solo en el inicio).
 * - Se ve como el sello de fecha y hora de un documento: la franja arriba, la hora en letra de
 *   máquina y el estado como sello de tinta. Verde en horario y morado fuera, el color del chip
 *   «Aprobada fuera del horario».
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
}

export function RelojHorario({ conRecargo = true }: Props) {
  const ahora = useMinutoActual();
  const { iso, hora, minuto } = enPanama(ahora);
  const { laboral, hasta } = estadoHorario(ahora);
  const hhmm = `${dosCifras(hora)}:${dosCifras(minuto)}`;

  return (
    <div className={styles.reloj} data-horario={laboral ? "laboral" : "fuera"}
      role="group" aria-labelledby="reloj-horario-rotulo">
      <p className={styles.linea}>
        <span id="reloj-horario-rotulo" className={styles.rotulo}>Hora de Panamá</span>
        <span className={styles.fecha}>{fechaLarga(iso)}</span>
      </p>
      {/* La hora, el sello y «hasta …», sueltos: en el celular, la hora y el sello van juntos
          y «hasta …» debajo. */}
      <p className={styles.principal}>
        <time className={styles.hora} dateTime={`${iso}T${hhmm}-05:00`}>{hhmm}</time>
        {" "}<span className={styles.sello}>{laboral ? "Horario laboral" : "Fuera del horario"}</span>
        {" "}<span className={styles.hasta}>hasta {hasta}</span>
      </p>
      {!laboral && conRecargo && <p className={styles.recargo}>Lo que se apruebe ahora lleva recargo.</p>}
      <p className={styles.horario}><IconoReloj tamano={12} /> Horario: {TEXTO_HORARIO_LABORAL}</p>
    </div>
  );
}
