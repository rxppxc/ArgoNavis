import { useState } from "react";
import { apiSolicitudes, type SolicitudDetalle } from "../../api/solicitudes";
import { IconoCheck } from "../../components/Iconos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import { formatearFecha, formatearFechaHora } from "./presentacion";
import styles from "./DetalleSolicitud.module.css";

type Decision = "aprobar" | "devolver" | "negar";

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
  solicitud: SolicitudDetalle;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Panel de UCVMM: verificación de impedimentos y decisión sobre la solicitud. */
export function PanelRevision({ solicitud, onActualizada }: Props) {
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  // Resultado por tripulante: true = con impedimento, false = sin, null = sin marcar.
  const resultadosGuardados = () => Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, t.con_impedimento]));
  const [resultados, setResultados] = useState<Record<number, boolean | null>>(resultadosGuardados);
  const [comentarioImp, setComentarioImp] = useState(solicitud.comentario_impedimentos ?? "");
  // Registrada, la verificación se ve de solo lectura; cambiarla es una corrección con motivo.
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [motivoCorreccion, setMotivoCorreccion] = useState("");
  const registrada = solicitud.impedimentos_verificados;
  const editable = !registrada || corrigiendo;
  const corregida = [...solicitud.eventos].reverse()
    .find((e) => e.tipo === "impedimentos" || e.tipo === "impedimentos_corregidos")?.tipo === "impedimentos_corregidos";
  const pendientes = solicitud.tripulantes.filter((t) => resultados[t.id] == null).length;
  const conImpedimento = solicitud.tripulantes.filter((t) => t.con_impedimento).map((t) => t.nombre_completo);
  const cambiados = solicitud.tripulantes.filter((t) => t.con_impedimento !== null && resultados[t.id] !== t.con_impedimento);
  const hayCambios = solicitud.tripulantes.some((t) => resultados[t.id] !== t.con_impedimento)
    || comentarioImp.trim() !== (solicitud.comentario_impedimentos ?? "");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [texto, setTexto] = useState("");
  const [trabajando, setTrabajando] = useState(false);

  function empezarCorreccion() {
    setResultados(resultadosGuardados());
    setComentarioImp(solicitud.comentario_impedimentos ?? "");
    setMotivoCorreccion("");
    setDecision(null);
    setTexto("");
    setCorrigiendo(true);
  }

  function cancelarCorreccion() {
    setResultados(resultadosGuardados());
    setComentarioImp(solicitud.comentario_impedimentos ?? "");
    setCorrigiendo(false);
  }

  async function guardarImpedimentos() {
    if (pendientes) {
      mostrar(`Falta marcar el resultado de ${pendientes} tripulante${pendientes === 1 ? "" : "s"}.`, "aviso");
      return;
    }
    if (corrigiendo) {
      const motivo = motivoCorreccion.trim();
      if (motivo.length < 5) {
        mostrar("Escribe el motivo de la corrección (al menos 5 caracteres).", "aviso");
        return;
      }
      const resultado = (conImp: boolean | null | undefined) => (conImp ? "con impedimento" : "sin impedimento");
      const ok = await confirmar({
        titulo: "Corregir verificación de impedimentos",
        mensaje: (
          cambiados.length === 1
            ? `${cambiados[0].nombre_completo} pasa de ${resultado(cambiados[0].con_impedimento)} a ${resultado(resultados[cambiados[0].id])}.`
            : cambiados.length > 1
              ? `Cambia el resultado de ${cambiados.map((t) => `${t.nombre_completo} (ahora ${resultado(resultados[t.id])})`).join(", ")}.`
              : "Se actualiza el comentario de la verificación."
        ) + ` Motivo: ${/[.!?]$/.test(motivo) ? motivo : `${motivo}.`} La verificación anterior queda en el historial.`,
        textoOk: "Guardar corrección",
      });
      if (!ok) return;
    }
    setTrabajando(true);
    try {
      const lista = solicitud.tripulantes.map((t) => ({ tripulante_id: t.id, con_impedimento: !!resultados[t.id] }));
      onActualizada(await apiSolicitudes.registrarImpedimentos(
        solicitud.id, lista, comentarioImp.trim() || null, corrigiendo ? motivoCorreccion.trim() : null,
      ));
      mostrar(corrigiendo ? "Verificación de impedimentos corregida." : "Verificación de impedimentos registrada.", "exito");
      setCorrigiendo(false);
      setMotivoCorreccion("");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo registrar la verificación."), "error");
    } finally {
      setTrabajando(false);
    }
  }

  async function decidir() {
    if (!decision) return;
    const motivo = texto.trim();
    if (decision !== "aprobar" && motivo.length < 5) {
      mostrar("Escribe el motivo (al menos 5 caracteres).", "aviso");
      return;
    }
    const ok = await confirmar(
      decision === "aprobar"
        ? {
            titulo: "Aprobar autorización",
            mensaje: conImpedimento.length
              ? `Con impedimento en SIMPLUS: ${conImpedimento.join(", ")}. Confirma que se informó a Operaciones. `
                + "Se emitirá la autorización en PDF y se avisará a la agencia y al puesto de control."
              : "Se emitirá la autorización en PDF y se avisará a la agencia y al puesto de control.",
            textoOk: "Aprobar",
            exito: true,
          }
        : decision === "devolver"
          ? {
              titulo: "Devolver a corrección",
              mensaje: "La agencia recibirá el motivo y tendrá un plazo para corregir. Si no corrige a tiempo, la solicitud expira.",
              textoOk: "Devolver",
            }
          : {
              titulo: "Denegar solicitud",
              mensaje: "La solicitud quedará denegada de forma definitiva y se avisará a la agencia.",
              textoOk: "Denegar",
              peligroso: true,
            },
    );
    if (!ok) return;

    setTrabajando(true);
    try {
      const actualizada =
        decision === "aprobar" ? await apiSolicitudes.aprobar(solicitud.id, motivo || null)
        : decision === "devolver" ? await apiSolicitudes.devolver(solicitud.id, motivo)
        : await apiSolicitudes.negar(solicitud.id, motivo);
      onActualizada(actualizada);
      mostrar(
        decision === "aprobar" ? "Autorización aprobada."
        : decision === "devolver" ? "Solicitud devuelta a la agencia."
        : "Solicitud denegada.",
        "exito",
      );
      setDecision(null);
      setTexto("");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo completar la acción."), "error");
    } finally {
      setTrabajando(false);
    }
  }

  const etiquetaTexto =
    decision === "aprobar" ? "Observación interna (opcional — la agencia no la ve)"
    : decision === "devolver" ? "¿Qué debe corregir la agencia? *"
    : "Motivo de la denegación *";

  return (
    <section className={`${styles.panel} ${styles.panelAccion}`}>
      <h2 className={styles.panelTitulo}>Revisión UCVMM</h2>

      <div className={styles.paso}>
        <div className={styles.pasoTitulo}>1. Verificación de impedimentos (SIMPLUS)</div>
        {editable ? (
          <>
            <div className={styles.impedimentosCabecera}>
              <span className={styles.ayuda}>
                {corrigiendo ? "Corrige el resultado de cada tripulante:" : "Resultado de cada tripulante en SIMPLUS:"}
              </span>
              <button type="button" className={styles.btnPequeno}
                onClick={() => setResultados(Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, false])))}>
                Marcar todos sin impedimento
              </button>
            </div>
            <ul className={styles.listaImpedimentos}>
              {solicitud.tripulantes.map((t) => (
                <li key={t.id} className={`${styles.filaImpedimento} ${resultados[t.id] ? styles.filaConImpedimento : ""}`}>
                  <div>
                    <div className={styles.celdaPrincipal}>{t.nombre_completo}</div>
                    <div className={styles.celdaSecundaria}>{t.nacionalidad_nombre ?? t.nacionalidad} · Pasaporte {t.pasaporte}</div>
                  </div>
                  <div className={styles.opcionesImpedimento} role="radiogroup" aria-label={`Impedimentos de ${t.nombre_completo}`}>
                    <label className={resultados[t.id] === false ? styles.opcionSin : undefined}>
                      <input type="radio" name={`impedimento-${t.id}`} checked={resultados[t.id] === false}
                        onChange={() => setResultados((r) => ({ ...r, [t.id]: false }))} />
                      Sin impedimento
                    </label>
                    <label className={resultados[t.id] === true ? styles.opcionCon : undefined}>
                      <input type="radio" name={`impedimento-${t.id}`} checked={resultados[t.id] === true}
                        onChange={() => setResultados((r) => ({ ...r, [t.id]: true }))} />
                      Con impedimento
                    </label>
                  </div>
                </li>
              ))}
            </ul>
            <textarea className={styles.textarea} rows={3} maxLength={2000}
              placeholder="Comentarios u observaciones (opcional)"
              value={comentarioImp} onChange={(e) => setComentarioImp(e.target.value)} />
            {corrigiendo && (
              <>
                <label className={styles.etiqueta} htmlFor="motivo-correccion">Motivo de la corrección *</label>
                <textarea id="motivo-correccion" className={styles.textarea} rows={2} maxLength={2000}
                  placeholder="Ej. se revisó de nuevo en SIMPLUS"
                  value={motivoCorreccion} onChange={(e) => setMotivoCorreccion(e.target.value)} />
              </>
            )}
            <div className={styles.filaBotones}>
              {corrigiendo && (
                <button type="button" className={styles.btnTexto} onClick={cancelarCorreccion} disabled={trabajando}>
                  Cancelar
                </button>
              )}
              <button type="button" className={styles.btnPrimario} onClick={guardarImpedimentos}
                disabled={trabajando || !hayCambios} title={hayCambios ? undefined : "No hay cambios que guardar"}>
                {corrigiendo ? "Guardar corrección" : "Guardar verificación"}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className={styles.verificacionRegistrada}>
              <IconoCheck tamano={13} />
              {corregida ? "Corregida" : "Registrada"} por {solicitud.impedimentos_verificados_por ?? "—"} el{" "}
              {formatearFechaHora(solicitud.impedimentos_verificados_en)}
            </p>
            <ul className={styles.listaImpedimentos}>
              {solicitud.tripulantes.map((t) => (
                <li key={t.id} className={`${styles.filaImpedimento} ${t.con_impedimento ? styles.filaConImpedimento : ""}`}>
                  <div>
                    <div className={styles.celdaPrincipal}>{t.nombre_completo}</div>
                    <div className={styles.celdaSecundaria}>{t.nacionalidad_nombre ?? t.nacionalidad} · Pasaporte {t.pasaporte}</div>
                  </div>
                  <span className={t.con_impedimento ? styles.resultadoCon : styles.resultadoSin}>
                    {t.con_impedimento ? "Con impedimento" : "Sin impedimento"}
                  </span>
                </li>
              ))}
            </ul>
            {solicitud.comentario_impedimentos && (
              <div className={styles.observaciones}>{solicitud.comentario_impedimentos}</div>
            )}
            <div className={styles.filaBotones}>
              <button type="button" className={styles.btnSecundario} onClick={empezarCorreccion} disabled={trabajando}>
                Corregir verificación
              </button>
            </div>
          </>
        )}
      </div>

      <div className={styles.paso}>
        <div className={styles.pasoTitulo}>2. Decisión</div>
        <div className={styles.decisiones}>
          <button type="button" disabled={trabajando || corrigiendo || !registrada}
            className={`${styles.btnDecision} ${styles.aprobar} ${decision === "aprobar" ? styles.activa : ""}`}
            onClick={() => setDecision("aprobar")}
            title={registrada ? "" : "Primero registra la verificación de impedimentos de cada tripulante"}>
            Aprobar
          </button>
          <button type="button" disabled={trabajando || corrigiendo}
            className={`${styles.btnDecision} ${decision === "devolver" ? styles.activa : ""}`}
            onClick={() => {
              setDecision("devolver");
              if (!texto.trim()) setTexto(motivoPorVencimientos(solicitud));
            }}>
            Devolver a corrección
          </button>
          <button type="button" disabled={trabajando || corrigiendo}
            className={`${styles.btnDecision} ${styles.negar} ${decision === "negar" ? styles.activa : ""}`}
            onClick={() => setDecision("negar")}>
            Denegar
          </button>
        </div>
        {corrigiendo ? (
          <p className={styles.ayuda}>Guarda o cancela la corrección de impedimentos antes de decidir.</p>
        ) : !registrada && (
          <p className={styles.ayuda}>Para aprobar, primero guarda la verificación de impedimentos de cada tripulante.</p>
        )}
        {decision && (
          <div className={styles.formDecision}>
            <label className={styles.etiqueta}>{etiquetaTexto}</label>
            <textarea className={styles.textarea} rows={3} maxLength={2000} value={texto}
              onChange={(e) => setTexto(e.target.value)} autoFocus />
            <div className={styles.filaBotones}>
              <button type="button" className={styles.btnTexto} onClick={() => { setDecision(null); setTexto(""); }}>
                Cancelar
              </button>
              <button type="button" onClick={decidir} disabled={trabajando}
                className={decision === "aprobar" ? styles.btnExito : decision === "negar" ? styles.btnPeligro : styles.btnPrimario}>
                {trabajando ? "Procesando…" : "Confirmar"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
