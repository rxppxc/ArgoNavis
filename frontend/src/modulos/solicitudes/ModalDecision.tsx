import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { apiSolicitudes, type SolicitudDetalle } from "../../api/solicitudes";
import { useNotificacion } from "../../components/Notificaciones";
import { useAtraparFoco } from "../../hooks/useAtraparFoco";
import { mensajeDeError } from "../../utils/errores";
import { formatearFecha } from "./presentacion";
import styles from "./DetalleSolicitud.module.css";

export type Decision = "aprobar" | "devolver" | "negar";

const TEXTOS: Record<Decision, { titulo: string; etiqueta: string; boton: string; clase: string; hecho: string }> = {
  aprobar: {
    titulo: "Aprobar autorización", etiqueta: "Observación interna (opcional — la agencia no la ve)",
    boton: "Aprobar", clase: styles.btnExito, hecho: "Autorización aprobada.",
  },
  devolver: {
    titulo: "Devolver a corrección", etiqueta: "¿Qué debe corregir la agencia? *",
    boton: "Devolver", clase: styles.btnPrimario, hecho: "Solicitud devuelta a la agencia.",
  },
  negar: {
    titulo: "Denegar solicitud", etiqueta: "Motivo de la denegación *",
    boton: "Denegar", clase: styles.btnPeligro, hecho: "Solicitud denegada.",
  },
};

function mensaje(decision: Decision, conImpedimento: string[]): string {
  if (decision === "aprobar") {
    return (conImpedimento.length
      ? `Con impedimento en SIMPLUS: ${conImpedimento.join(", ")}. Confirma que se informó a Operaciones. `
      : "") + "Se emitirá la autorización en PDF y se avisará a la agencia y al puesto de control.";
  }
  return decision === "devolver"
    ? "La agencia recibirá el motivo y tendrá un plazo para corregir. Si no corrige a tiempo, la solicitud expira."
    : "La solicitud quedará denegada de forma definitiva y se avisará a la agencia.";
}

/** Motivo sugerido al devolver: qué tripulantes tienen documentación vencida
 *  a la fecha de la operación (el documento de UCVMM pide informarlo). */
function motivoPorVencimientos(s: SolicitudDetalle): string {
  const lineas = s.tripulantes.flatMap((t) => [
    ...(t.pasaporte_vencido ? [`- ${t.nombre_completo}: el pasaporte vence el ${formatearFecha(t.pasaporte_expira)}.`] : []),
    ...(t.libreta_vencida ? [`- ${t.nombre_completo}: el seamanbook vence el ${formatearFecha(t.libreta_expira)}.`] : []),
  ]);
  if (!lineas.length) return "";
  return [
    "Documentación vencida a la fecha de la operación:",
    ...lineas,
    "Adjunta la documentación vigente o retira a esos tripulantes de la solicitud.",
  ].join("\n");
}

interface Props {
  decision: Decision;
  solicitud: SolicitudDetalle;
  /** Con impedimento según la verificación guardada. */
  conImpedimento: string[];
  onCerrar: () => void;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Una decisión de UCVMM en un solo paso: el texto y el botón final en el
 *  mismo modal. Antes eran cuatro: elegir, escribir, "Confirmar" y otro
 *  modal que volvía a pedir confirmación. */
export function ModalDecision({ decision, solicitud, conImpedimento, onCerrar, onActualizada }: Props) {
  const { mostrar } = useNotificacion();
  const refModal = useAtraparFoco(true);
  const [texto, setTexto] = useState(() => (decision === "devolver" ? motivoPorVencimientos(solicitud) : ""));
  const [intentado, setIntentado] = useState(false);
  const [trabajando, setTrabajando] = useState(false);
  const t = TEXTOS[decision];
  const motivo = texto.trim();
  const faltaMotivo = decision !== "aprobar" && motivo.length < 5;

  // Escape cierra (mientras no se esté enviando).
  useEffect(() => {
    function alTeclear(e: KeyboardEvent) {
      if (e.key === "Escape" && !trabajando) onCerrar();
    }
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar, trabajando]);

  async function confirmar() {
    setIntentado(true);
    if (faltaMotivo || trabajando) return;
    setTrabajando(true);
    try {
      const actualizada =
        decision === "aprobar" ? await apiSolicitudes.aprobar(solicitud.id, motivo || null)
        : decision === "devolver" ? await apiSolicitudes.devolver(solicitud.id, motivo)
        : await apiSolicitudes.negar(solicitud.id, motivo);
      mostrar(t.hecho, "exito");
      onCerrar();
      onActualizada(actualizada);
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo completar la acción."), "error");
      setTrabajando(false);
    }
  }

  // En el body: el panel de decisión es fijo (sticky) y lo que se pinta dentro
  // queda por debajo de la cabecera, que no se oscurecería.
  return createPortal(
    <div className={styles.modalFondo} onClick={() => { if (!trabajando) onCerrar(); }}>
      <div ref={refModal} className={`${styles.modal} ${styles.modalAngosto}`} role="dialog" aria-modal="true"
        aria-labelledby="titulo-decision" aria-describedby="mensaje-decision" onClick={(e) => e.stopPropagation()}>
        <h2 id="titulo-decision" className={styles.panelTitulo}>{t.titulo}</h2>
        <p id="mensaje-decision" className={styles.modalMensaje}>{mensaje(decision, conImpedimento)}</p>
        <label className={styles.etiqueta} htmlFor="texto-decision">{t.etiqueta}</label>
        <textarea id="texto-decision" className={styles.textarea} rows={4} maxLength={2000} data-focus-inicial
          value={texto} onChange={(e) => setTexto(e.target.value)} aria-invalid={intentado && faltaMotivo} />
        {intentado && faltaMotivo && (
          <p className={styles.textoFalta} role="alert">Escribe el motivo (al menos 5 caracteres).</p>
        )}
        <div className={styles.filaBotones}>
          <button type="button" className={styles.btnTexto} onClick={onCerrar} disabled={trabajando}>Cancelar</button>
          <button type="button" className={t.clase} onClick={confirmar} disabled={trabajando}>
            {trabajando ? "Procesando…" : t.boton}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
