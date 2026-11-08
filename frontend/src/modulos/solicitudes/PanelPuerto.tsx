import { useState } from "react";
import { apiSolicitudes, releerSiCambio, type SolicitudDetalle } from "../../api/solicitudes";
import { IconoExito } from "../../components/Iconos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import { formatearFechaHora } from "./presentacion";
import type { VerificacionImpedimentos } from "./useVerificacionImpedimentos";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  /** La verificación de impedimentos del puesto, que se marca en la tabla de tripulantes. */
  verificacion: VerificacionImpedimentos;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Panel del puesto de control: resume la verificación de impedimentos en
 *  SIMPLUS (obligatoria desde el 2026-11-06, se marca en la tabla de
 *  tripulantes) y finaliza, con el comentario de lo ocurrido (fecha, hora y
 *  usuario automáticos). Se finaliza en el puesto autorizado: una operación en
 *  otro puesto es una solicitud nueva de la agencia (reunión del 2026-10-30). */
export function PanelPuerto({ solicitud, verificacion: v, onActualizada }: Props) {
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();
  const [comentario, setComentario] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const total = solicitud.tripulantes.length;
  const lista = v.registrada && !v.corrigiendo;

  async function finalizar() {
    const texto = comentario.trim();
    if (texto.length < 3) {
      mostrar("Escribe el comentario de la operación (al menos 3 caracteres).", "aviso");
      return;
    }
    const ok = await confirmar({
      titulo: "Finalizar solicitud",
      mensaje: `Se registrará la operación con tu comentario como finalizada en ${solicitud.puesto_nombre} `
        + "y la autorización quedará cerrada."
        + (v.conImpedimento.length
          ? ` Con impedimento en SIMPLUS: ${v.conImpedimento.join(", ")}. Indica en el comentario qué pasó con ${
            v.conImpedimento.length === 1 ? "esa persona" : "esas personas"}.`
          : ""),
      textoOk: "Finalizar",
      tono: "finalizar",
    });
    if (!ok) return;
    setTrabajando(true);
    try {
      onActualizada(await apiSolicitudes.finalizar(solicitud.id, texto));
      setComentario("");
      mostrar("Solicitud finalizada.", "exito");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo finalizar."), "error");
      await releerSiCambio(error, solicitud.id, onActualizada);   // ya finalizada o vencida (409)
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <section className={`${styles.panel} ${styles.panelAccion}`}>
      <h2 className={styles.panelTitulo}>Puesto de control</h2>
      <div className={styles.resumenVerificacion}>
        {v.corrigiendo ? (
          <>
            <strong className={styles.estadoPendiente}>Corrigiendo la verificación</strong>
            <span>Guarda o cancela la corrección antes de finalizar.</span>
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
              Verifica los impedimentos en SIMPLUS: {total - v.pendientes} de {total} marcados en la tabla de
              tripulantes. Para finalizar, primero guarda la verificación.
            </span>
          </>
        )}
      </div>
      <p className={styles.ayuda}>
        Registra lo ocurrido en la operación y finalízala. Queda con la fecha, la hora y tu usuario.
        Debe finalizarse antes del {formatearFechaHora(solicitud.vigente_hasta)} o la autorización expira.
      </p>
      <p className={styles.ayuda}>
        Finalízala solo si la operación se realizó en <strong>{solicitud.puesto_nombre}</strong>. Si se hizo en
        otro puesto, no la finalices: vence sola y la agencia debe presentar una nueva solicitud.
      </p>
      <label className={styles.etiqueta} htmlFor="comentario-puerto">Comentario de la operación *</label>
      <textarea id="comentario-puerto" className={styles.textarea} rows={3} maxLength={2000} value={comentario}
        placeholder="Ej. Tripulantes presentados en garita, desembarque sin novedad…"
        onChange={(e) => setComentario(e.target.value)} />
      {/* A todo el ancho, como las decisiones de UCVMM: es la acción del panel. Sin la
          verificación guardada se desactiva, con el porqué arriba (en el resumen). */}
      <button type="button" className={`${styles.btnFinalizar} ${styles.anchoCompleto}`} onClick={finalizar}
        disabled={trabajando || v.trabajando || !lista}
        title={lista ? undefined : "Primero guarda la verificación de impedimentos"}>
        <IconoExito tamano={15} /> {trabajando ? "Finalizando…" : "Finalizar"}
      </button>
    </section>
  );
}
