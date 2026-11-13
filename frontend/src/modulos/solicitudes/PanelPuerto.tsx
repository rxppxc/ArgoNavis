import { useState } from "react";
import { apiSolicitudes, releerSiCambio, type SolicitudDetalle } from "../../api/solicitudes";
import { IconoExito } from "../../components/Iconos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import { formatearFechaHora, puestoAutorizado, tiempoRestante } from "./presentacion";
import type { VerificacionImpedimentos } from "./useVerificacionImpedimentos";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  /** La verificación de impedimentos del puesto, que se marca en la tabla de tripulantes. */
  verificacion: VerificacionImpedimentos;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Panel del puesto de control, en tres pasos numerados (revisión de UX del
 *  2026-11-08; antes eran tres párrafos seguidos en la columna angosta):
 *    1. verificar los impedimentos en SIMPLUS (obligatoria desde el 2026-11-06;
 *       se marca en la tabla de tripulantes);
 *    2. escribir lo ocurrido en la operación;
 *    3. finalizar (fecha, hora y usuario automáticos).
 *  Arriba, el plazo: hasta cuándo se puede finalizar. Se finaliza en el puesto
 *  autorizado: una operación en otro puesto es una solicitud nueva de la agencia
 *  (reunión del 2026-10-30). */
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
      mensaje: `Se registrará la operación con tu comentario como finalizada en ${puestoAutorizado(solicitud)} `
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
      const finalizada = await apiSolicitudes.finalizar(solicitud.id, texto);
      onActualizada(finalizada);
      setComentario("");
      mostrar(`Solicitud${finalizada.numero ? ` ${finalizada.numero}` : ""} finalizada.`, "exito", { sello: "finalizada" });
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo finalizar."), "error");
      await releerSiCambio(error, solicitud.id, onActualizada);   // ya finalizada o vencida (409)
    } finally {
      setTrabajando(false);
    }
  }

  const plazo = tiempoRestante(solicitud.vigente_hasta);
  const comentarioListo = comentario.trim().length >= 3;

  return (
    <section className={`${styles.panel} ${styles.panelAccion}`}>
      <h2 className={styles.panelTitulo}>Puesto de control</h2>
      <p className={plazo.vencido ? styles.plazoPanelVencido : styles.plazoPanel}>
        {plazo.vencido ? "Venció el plazo para finalizar" : "Finalizar antes del"}{" "}
        <strong>{formatearFechaHora(solicitud.vigente_hasta)}</strong>
        {!plazo.vencido && <> · {plazo.frase}</>}
      </p>

      <ol className={styles.pasos}>
        <li className={lista ? styles.pasoHecho : styles.pasoActual}>
          <span className={styles.pasoNumero} aria-hidden="true">{lista ? "✓" : "1"}</span>
          <div className={styles.pasoCuerpo}>
            <strong className={styles.pasoTitulo}>Verifica los impedimentos en SIMPLUS</strong>
            <span className={styles.pasoTexto}>
              {v.corrigiendo
                ? "Corrigiendo: guarda o cancela la corrección en la tabla de pasajeros."
                : v.registrada
                  ? (v.conImpedimento.length
                    ? <>Guardada. Con impedimento: <strong>{v.conImpedimento.join(", ")}</strong></>
                    : "Guardada: ningún pasajero con impedimento.")
                  : `Marca a cada pasajero en la tabla (${total - v.pendientes} de ${total}) y guarda la verificación.`}
            </span>
          </div>
        </li>
        <li className={lista && comentarioListo ? styles.pasoHecho : lista ? styles.pasoActual : styles.pasoEspera}>
          <span className={styles.pasoNumero} aria-hidden="true">{lista && comentarioListo ? "✓" : "2"}</span>
          <div className={styles.pasoCuerpo}>
            <label className={styles.pasoTitulo} htmlFor="comentario-puerto">Comentario de la operación *</label>
            <span className={styles.pasoTexto}>Qué pasó en la operación, con lo que haya pasado con cada pasajero.</span>
            <textarea id="comentario-puerto" className={styles.textarea} rows={3} maxLength={2000} value={comentario}
              placeholder="Ej. Pasajeros presentados en garita, desembarque sin novedad…"
              onChange={(e) => setComentario(e.target.value)} />
          </div>
        </li>
        <li className={lista ? styles.pasoActual : styles.pasoEspera}>
          <span className={styles.pasoNumero} aria-hidden="true">3</span>
          <div className={styles.pasoCuerpo}>
            <strong className={styles.pasoTitulo}>Finaliza</strong>
            <span className={styles.pasoTexto}>
              Solo si la operación se hizo en <strong>{puestoAutorizado(solicitud)}</strong>
              {solicitud.puesto_destino_nombre && <> (cambio de puerto desde {solicitud.puesto_nombre})</>}. Si fue en
              otro puesto, no la finalices: vence sola y la agencia presenta una nueva solicitud.
            </span>
          </div>
        </li>
      </ol>

      {/* A todo el ancho, como las decisiones de UCVMM: es la acción del panel. Sin la
          verificación guardada se desactiva, con el porqué en el paso 1. */}
      <button type="button" className={`${styles.btnFinalizar} ${styles.anchoCompleto}`} onClick={finalizar}
        disabled={trabajando || v.trabajando || !lista}
        title={lista ? undefined : "Primero guarda la verificación de impedimentos (paso 1)"}>
        <IconoExito tamano={15} /> {trabajando ? "Finalizando…" : "Finalizar"}
      </button>
      <p className={styles.pieAccion}>Queda registrada con la fecha, la hora y tu usuario.</p>
    </section>
  );
}
