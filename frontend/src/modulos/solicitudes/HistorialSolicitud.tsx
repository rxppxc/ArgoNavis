import type { EventoSolicitud } from "../../api/solicitudes";
import { ETIQUETA_EVENTO, formatearFechaHora } from "./presentacion";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  eventos: EventoSolicitud[];
  /** Puesto donde terminó la operación (para el evento "finalizada"). */
  puestoFinalizacion?: string | null;
}

/** Línea de tiempo del expediente: quién hizo qué y cuándo. A la agencia el
 *  backend ya le manda solo los estados y los motivos que le corresponden. */
export function HistorialSolicitud({ eventos, puestoFinalizacion }: Props) {
  return (
    <section className={styles.panel}>
      <h2 className={styles.panelTitulo}>Historial</h2>
      {eventos.length === 0 ? (
        <p className={styles.vacio}>Sin movimientos registrados.</p>
      ) : (
        <ol className={styles.historial}>
          {[...eventos].reverse().map((e) => (
            <li key={e.id} className={`${styles.evento} ${styles[`evento_${e.tipo}`] ?? ""}`}>
              <span className={styles.eventoPunto} aria-hidden="true" />
              <div className={styles.eventoCuerpo}>
                <div className={styles.eventoTitulo}>
                  {e.tipo === "finalizada" && puestoFinalizacion ? `Finalizada en ${puestoFinalizacion}` : ETIQUETA_EVENTO[e.tipo] ?? e.tipo}
                </div>
                <div className={styles.eventoMeta}>
                  {formatearFechaHora(e.creado_en)} · {e.usuario_nombre ?? "Sistema"}
                </div>
                {e.comentario && <div className={styles.eventoComentario}>{e.comentario}</div>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
