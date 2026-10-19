import { useState } from "react";
import type { SolicitudDetalle } from "../../api/solicitudes";
import { ModalDecision, type Decision } from "./ModalDecision";
import type { VerificacionImpedimentos } from "./useVerificacionImpedimentos";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  verificacion: VerificacionImpedimentos;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Panel de UCVMM: resume la verificación de impedimentos (que se marca en la
 *  tabla de tripulantes) y decide. Va en la columna lateral, que queda fija al
 *  bajar por la tabla; cada decisión abre un solo modal con su texto. */
export function PanelRevision({ solicitud, verificacion: v, onActualizada }: Props) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const total = solicitud.tripulantes.length;

  return (
    <section className={`${styles.panel} ${styles.panelAccion}`}>
      <h2 className={styles.panelTitulo}>Decisión</h2>
      <div className={styles.resumenVerificacion}>
        {v.corrigiendo ? (
          <>
            <strong className={styles.estadoPendiente}>Corrigiendo la verificación</strong>
            <span>Guarda o cancela la corrección antes de decidir.</span>
          </>
        ) : v.registrada ? (
          <>
            <strong className={styles.estadoOk}>Verificación guardada</strong>
            <span>
              {v.conImpedimento.length
                ? <>Con impedimento: <strong>{v.conImpedimento.join(", ")}</strong></>
                : "Ningún tripulante con impedimento."}
            </span>
          </>
        ) : (
          <>
            <strong className={styles.estadoPendiente}>Verificación pendiente</strong>
            <span>
              {total - v.pendientes} de {total} marcados en la tabla de tripulantes. Para aprobar, primero
              guarda la verificación.
            </span>
          </>
        )}
      </div>
      <div className={styles.decisiones}>
        <button type="button" className={`${styles.btnDecision} ${styles.aprobar}`}
          disabled={!v.registrada || v.corrigiendo || v.trabajando}
          title={v.registrada ? undefined : "Primero guarda la verificación de impedimentos"}
          onClick={() => setDecision("aprobar")}>
          Aprobar
        </button>
        <button type="button" className={styles.btnDecision} disabled={v.corrigiendo || v.trabajando}
          onClick={() => setDecision("devolver")}>
          Devolver a corrección
        </button>
        <button type="button" className={`${styles.btnDecision} ${styles.negar}`} disabled={v.corrigiendo || v.trabajando}
          onClick={() => setDecision("negar")}>
          Denegar
        </button>
      </div>
      {decision && (
        <ModalDecision decision={decision} solicitud={solicitud} conImpedimento={v.conImpedimento}
          onCerrar={() => setDecision(null)} onActualizada={onActualizada} />
      )}
    </section>
  );
}
