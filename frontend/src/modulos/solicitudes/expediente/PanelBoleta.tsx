import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { apiSolicitudes, releerSiCambio, type BoletaRecargo, type SolicitudDetalle } from "../../../api/solicitudes";
import { IconoDescargar } from "../../../components/Iconos";
import { useNotificacion } from "../../../components/Notificaciones";
import { useAtraparFoco } from "../../../hooks/useAtraparFoco";
import { mensajeDeError } from "../../../utils/errores";
import { formatearFechaHora } from "../presentacion";
import styles from "./DetalleSolicitud.module.css";

/** Espejos de LARGO_NUMERO_OFICIO y LARGO_MOTIVO_ANULACION (models/boleta.py). */
const LARGO_OFICIO = 40;
const LARGO_MOTIVO = 500;
const MINIMO_MOTIVO = 5;

type Modo = { tipo: "generar" } | { tipo: "anular"; boleta: BoletaRecargo };

/** Un 409 (número repetido, ya hay una vigente) o un 422 se corrigen escribiendo otra
 *  cosa: van como validación (REVISA), no como error. */
function tipoDelError(error: unknown): "aviso" | "error" {
  const estado = (error as { response?: { status?: number } } | null)?.response?.status;
  return estado === 409 || estado === 422 ? "aviso" : "error";
}

/** La boleta de recargo por atención fuera del horario laboral (2026-11-16), para el
 *  personal del SNM: la agencia no la ve (le llega `boletas` en null). UCVMM, el
 *  supervisor de sector y el puesto de control la generan con el número de oficio y,
 *  como en un talonario, la anulan con motivo y generan otra. El supervisor general
 *  solo la descarga. */
export function PanelBoleta({ s, onActualizada }: {
  s: SolicitudDetalle; onActualizada: (s: SolicitudDetalle) => void;
}) {
  const { mostrar } = useNotificacion();
  const [modo, setModo] = useState<Modo | null>(null);
  const [descargando, setDescargando] = useState<number | null>(null);
  if (s.boletas === null || !s.costo_fuera_de_horario) return null;

  const vigente = s.boletas.find((b) => b.vigente) ?? null;
  const anuladas = s.boletas.filter((b) => !b.vigente);

  async function descargar(b: BoletaRecargo) {
    setDescargando(b.id);
    try {
      await apiSolicitudes.descargarBoleta(s.id, b.id);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar la boleta."), "error");
    } finally {
      setDescargando(null);
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="titulo-boleta">
      <h2 id="titulo-boleta" className={styles.panelTitulo}>Recargo fuera del horario</h2>
      <p className={styles.ayuda}>
        Recargo por atención fuera del horario laboral: <strong>{s.costo_fuera_de_horario}</strong>. La boleta la
        imprime el SNM y se la entrega a la agencia, que no la ve en el sistema.
      </p>
      {vigente ? (
        <div className={styles.boleta}>
          <p className={styles.boletaOficio}>
            <span>N.º de oficio</span> <strong>{vigente.numero_oficio}</strong>
          </p>
          <p className={styles.boletaDato}>
            Generada el <span className={styles.sinCorte}>{formatearFechaHora(vigente.generada_en)}</span>
            {vigente.generada_por && <> por {vigente.generada_por}</>}.
          </p>
        </div>
      ) : (
        <p className={styles.vacio}>Sin boleta vigente.</p>
      )}
      <div className={styles.filaBotones}>
        {vigente && s.acciones.anular_boleta && (
          <button type="button" className={styles.btnAnular} onClick={() => setModo({ tipo: "anular", boleta: vigente })}>
            Anular
          </button>
        )}
        {vigente && (
          <button type="button" className={styles.btnConsultar} onClick={() => descargar(vigente)}
            disabled={descargando === vigente.id}>
            <IconoDescargar tamano={14} /> {descargando === vigente.id ? "Descargando…" : "Descargar boleta"}
          </button>
        )}
        {s.acciones.generar_boleta && (
          <button type="button" className={styles.btnPrimario} onClick={() => setModo({ tipo: "generar" })}>
            Generar boleta
          </button>
        )}
      </div>
      {anuladas.length > 0 && (
        <details className={styles.boletasAnuladas}>
          <summary>Anuladas ({anuladas.length})</summary>
          <ul>
            {anuladas.map((b) => (
              <li key={b.id}>
                <div>
                  <span className={styles.boletaNumero}>{b.numero_oficio}</span>, anulada el{" "}
                  <span className={styles.sinCorte}>{formatearFechaHora(b.anulada_en)}</span>
                  {b.anulada_por && <> por {b.anulada_por}</>}.
                  <span className={styles.textoLibre}> Motivo: {b.motivo_anulacion}</span>
                </div>
                <button type="button" className={styles.btnIconoVer} onClick={() => descargar(b)}
                  disabled={descargando === b.id} aria-label={`Descargar la boleta anulada del oficio ${b.numero_oficio}`}>
                  <IconoDescargar tamano={14} />
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {modo && <ModalBoleta modo={modo} solicitud={s} onCerrar={() => setModo(null)} onActualizada={onActualizada} />}
    </section>
  );
}

/** Generar (pide el número de oficio) o anular (pide el motivo), en un solo paso. En un
 *  portal al body, como ModalDecision: dentro de la columna fija quedaría bajo la cabecera. */
function ModalBoleta({ modo, solicitud, onCerrar, onActualizada }: {
  modo: Modo; solicitud: SolicitudDetalle; onCerrar: () => void; onActualizada: (s: SolicitudDetalle) => void;
}) {
  const { mostrar } = useNotificacion();
  const refModal = useAtraparFoco(true);
  const [texto, setTexto] = useState("");
  const [intentado, setIntentado] = useState(false);
  const [trabajando, setTrabajando] = useState(false);
  const generar = modo.tipo === "generar";
  // El backend también quita los espacios de los extremos y los repetidos.
  const valor = generar ? texto.trim().split(/\s+/).join(" ") : texto.trim();
  const falta = generar ? valor.length === 0 : valor.length < MINIMO_MOTIVO;

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
    if (falta || trabajando) return;
    setTrabajando(true);
    try {
      if (modo.tipo === "generar") {
        const actualizada = await apiSolicitudes.generarBoleta(solicitud.id, valor);
        const boleta = actualizada.boletas?.find((b) => b.vigente) ?? null;
        mostrar(`Boleta de recargo generada (oficio N.º ${boleta?.numero_oficio ?? valor}).`, "exito");
        onCerrar();
        onActualizada(actualizada);
        if (boleta) {
          try {
            await apiSolicitudes.descargarBoleta(solicitud.id, boleta.id);
          } catch (e) {
            mostrar(mensajeDeError(e, "La boleta se generó, pero no se pudo descargar: descárgala desde aquí."), "error");
          }
        }
      } else {
        const actualizada = await apiSolicitudes.anularBoleta(solicitud.id, modo.boleta.id, valor);
        mostrar(`Boleta anulada (oficio N.º ${modo.boleta.numero_oficio}).`, "exito");
        onCerrar();
        onActualizada(actualizada);
      }
    } catch (error) {
      mostrar(mensajeDeError(error, generar ? "No se pudo generar la boleta." : "No se pudo anular la boleta."),
        tipoDelError(error));
      setTrabajando(false);
      // Otro funcionario pudo generarla o anularla (409): el expediente muestra cómo quedó y,
      // si ya no se puede hacer lo que se intentaba, el modal se cierra.
      await releerSiCambio(error, solicitud.id, (s) => {
        onActualizada(s);
        if (!(generar ? s.acciones.generar_boleta : s.acciones.anular_boleta)) onCerrar();
      });
    }
  }

  const titulo = generar ? "Generar boleta de recargo" : "Anular boleta";
  return createPortal(
    <div className={styles.modalFondo} onClick={() => { if (!trabajando) onCerrar(); }}>
      <div ref={refModal} className={`${styles.modal} ${styles.modalAngosto}`} role="dialog" aria-modal="true"
        aria-labelledby="titulo-modal-boleta" aria-describedby="mensaje-modal-boleta" onClick={(e) => e.stopPropagation()}>
        <h2 id="titulo-modal-boleta" className={styles.panelTitulo}>{titulo}</h2>
        <p id="mensaje-modal-boleta" className={styles.modalMensaje}>
          {generar
            ? `Recargo de ${solicitud.costo_fuera_de_horario} por atención fuera del horario laboral. El número de `
              + "oficio no se puede repetir en otra boleta, tampoco en una anulada."
            : `La boleta del oficio N.º ${modo.boleta.numero_oficio} quedará anulada, con su número. Después puedes `
              + "generar otra con otro número."}
        </p>
        {generar ? (
          <>
            <label className={styles.etiqueta} htmlFor="texto-modal-boleta">Número de oficio *</label>
            <input id="texto-modal-boleta" className={styles.textarea} maxLength={LARGO_OFICIO} autoComplete="off"
              data-focus-inicial placeholder="Ej. 045-2026" value={texto} aria-invalid={intentado && falta}
              onChange={(e) => setTexto(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void confirmar(); }} />
          </>
        ) : (
          <>
            <label className={styles.etiqueta} htmlFor="texto-modal-boleta">Motivo de la anulación *</label>
            <textarea id="texto-modal-boleta" className={styles.textarea} rows={3} maxLength={LARGO_MOTIVO}
              data-focus-inicial value={texto} aria-invalid={intentado && falta}
              onChange={(e) => setTexto(e.target.value)} />
          </>
        )}
        {intentado && falta && (
          <p className={styles.textoFalta} role="alert">
            {generar ? "Escribe el número de oficio." : `Escribe el motivo (al menos ${MINIMO_MOTIVO} caracteres).`}
          </p>
        )}
        <div className={styles.filaBotones}>
          <button type="button" className={styles.btnSecundario} onClick={onCerrar} disabled={trabajando}>Cancelar</button>
          <button type="button" className={generar ? styles.btnPrimario : styles.btnPeligro} onClick={confirmar}
            disabled={trabajando}>
            {trabajando ? "Procesando…" : generar ? "Generar y descargar" : "Anular boleta"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
