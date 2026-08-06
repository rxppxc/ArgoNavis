import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import type { Transferencia } from "../../types";
import { formatBytes } from "../../utils/format";
import { TIPOS_ACEPTADOS, validarArchivos } from "../../utils/archivos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { ModalPreview } from "../../components/ModalPreview";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import {
  IconoArchivo, IconoBasura, IconoSubir, IconoGuardar,
  IconoEnviar, IconoDevolver, IconoCandado, IconoEstrella, IconoOjo,
} from "../../components/Iconos";
import styles from "./PaginaEditarTransferencia.module.css";


export default function PaginaEditarTransferencia() {
  const { id: idStr } = useParams<{ id: string }>();
  const id = Number(idStr);
  const navegar = useNavigate();
  const confirmar = useConfirmar();

  const [t, setT] = useState<Transferencia | null>(null);
  const [puertos, setPuertos] = useState<{ id: number; nombre: string }[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [vista, setVista] = useState<"editar" | "original">("editar");

  // Form
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [destinatario, setDestinatario] = useState("");
  const [puertoId, setPuertoId] = useState<number | "">("");
  const [naviera, setNaviera] = useState("");
  const [marino, setMarino] = useState("");
  const [observaciones, setObservaciones] = useState("");

  // Devolver
  const [mostrarDevolver, setMostrarDevolver] = useState(false);
  const [motivoDevolver, setMotivoDevolver] = useState("");
  const [devolviendo, setDevolviendo] = useState(false);

  // Acciones
  const [guardando, setGuardando] = useState(false);
  const [reenviando, setReenviando] = useState(false);
  const [eliminandoArchivo, setEliminandoArchivo] = useState<number | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const inputArchivos = useRef<HTMLInputElement>(null);

  // Previsualización de archivos (evita descargar el ZIP para revisar).
  const [archivoPreview, setArchivoPreview] =
    useState<{ id: number; original_name: string; mime_type: string | null } | null>(null);

  // Aviso flotante — delega en el sistema de toasts compartido de la app.
  const { mostrar: mostrarToast } = useNotificacion();
  function notificar(texto: string, tipo: "ok" | "err" = "ok") {
    mostrarToast(texto, tipo === "err" ? "error" : "exito");
  }

  const aplicarTransferencia = useCallback((tr: Transferencia) => {
    setT(tr);
    setTitulo(tr.title ?? "");
    setMensaje(tr.message ?? "");
    setDestinatario(tr.recipient ?? "");
    setPuertoId(tr.puerto_id ?? "");
    setNaviera(tr.naviera ?? "");
    setMarino(tr.marino ?? "");
    setObservaciones(tr.observaciones ?? "");
  }, []);

  useEffect(() => {
    if (!id || Number.isNaN(id)) {
      setError("ID inválido."); setCargando(false); return;
    }
    // Cargas paralelas con tolerancia a fallos parciales: si el catálogo de
    // puertos falla podemos seguir mostrando la transferencia con los datos
    // que ya tenía guardados; solo la carga principal es crítica.
    Promise.allSettled([
      apiTransferencias.obtenerPorId(id),
      apiTransferencias.listarPuertos(),
    ]).then(([resTr, resPts]) => {
      if (resTr.status === "rejected") {
        const detalle = (resTr.reason as any)?.response?.data?.detail
                        ?? "No se pudo cargar la transferencia.";
        setError(typeof detalle === "string" ? detalle : "Error desconocido.");
        return;
      }
      aplicarTransferencia(resTr.value);
      if (resPts.status === "fulfilled") setPuertos(resPts.value);
    }).finally(() => setCargando(false));
  }, [id, aplicarTransferencia]);

  async function guardarCambios() {
    if (!t) return;
    setGuardando(true);
    try {
      const tr = await apiTransferencias.procesar(id, {
        title: titulo.trim() || undefined,
        message: mensaje.trim() || "",
        recipient: destinatario.trim() || "",
        puerto_id: puertoId === "" ? null : puertoId,
        naviera: naviera.trim() || "",
        marino: marino.trim() || "",
        observaciones: observaciones.trim() || null,
      });
      aplicarTransferencia(tr);
      notificar("Cambios guardados.");
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al guardar.", "err");
    } finally {
      setGuardando(false);
    }
  }

  async function reenviar() {
    if (!t) return;
    const dest = destinatario.trim();
    if (!dest) {
      notificar("Define un destinatario antes de reenviar.", "err"); return;
    }
    if (!puertoId || !naviera.trim() || !marino.trim()) {
      notificar("Completa puerto, naviera y marino antes de reenviar.", "err"); return;
    }
    const destOriginal = (t.recipient ?? "").trim();
    const cambioDest = destOriginal && destOriginal !== dest;
    const ok = await confirmar({
      titulo: cambioDest ? "Cambio de destinatario" : "Confirmar reenvío",
      mensaje: cambioDest
        ? `Vas a cambiar el destinatario. Original: ${destOriginal} → Nuevo: ${dest}. Se enviará el correo al NUEVO destinatario.`
        : `Se enviará un correo a: ${dest}.`,
      textoOk: "Reenviar",
    });
    if (!ok) return;

    setReenviando(true);
    try {
      // En este punto el guard previo garantiza que puertoId es un número > 0
      // (no la cadena vacía), así que el cast es seguro.
      await apiTransferencias.procesar(id, {
        title: titulo.trim() || undefined,
        message: mensaje.trim() || "",
        recipient: destinatario.trim(),
        puerto_id: puertoId as number,
        naviera: naviera.trim(),
        marino: marino.trim(),
      });
      await apiTransferencias.reenviar(id, {
        message: mensaje.trim() || undefined,
      });
      notificar("Transferencia reenviada — correo en camino.");
      setTimeout(() => navegar("/dashboard"), 1200);
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al reenviar.", "err");
    } finally {
      setReenviando(false);
    }
  }

  async function devolverANaviera() {
    const motivo = motivoDevolver.trim();
    if (!motivo) { notificar("El motivo es obligatorio para devolver.", "err"); return; }
    setDevolviendo(true);
    try {
      await apiTransferencias.devolver(id, motivo);
      notificar("Transferencia devuelta a la Naviera.");
      setTimeout(() => navegar("/dashboard"), 1200);
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al devolver.", "err");
    } finally {
      setDevolviendo(false);
    }
  }

  async function quitarArchivo(archivoId: number) {
    const ok = await confirmar({
      titulo: "Eliminar archivo",
      mensaje: "Esta acción eliminará el archivo permanentemente.",
      textoOk: "Eliminar",
      peligroso: true,
    });
    if (!ok) return;
    setEliminandoArchivo(archivoId);
    try {
      const tr = await apiTransferencias.quitarArchivo(id, archivoId);
      setT(tr);
      notificar("Archivo eliminado.");
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al eliminar.", "err");
    } finally {
      setEliminandoArchivo(null);
    }
  }

  async function subirArchivos(files: FileList | null) {
    if (!files || files.length === 0) return;
    const errorValidacion = validarArchivos(Array.from(files));
    if (errorValidacion) {
      notificar(errorValidacion, "err");
      if (inputArchivos.current) inputArchivos.current.value = "";
      return;
    }
    setSubiendo(true);
    try {
      const fd = new FormData();
      Array.from(files).forEach(f => fd.append("files", f));
      const tr = await apiTransferencias.agregarArchivos(id, fd);
      setT(tr);
      notificar(`${files.length} archivo${files.length !== 1 ? "s añadidos" : " añadido"}.`);
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al subir.", "err");
    } finally {
      setSubiendo(false);
      if (inputArchivos.current) inputArchivos.current.value = "";
    }
  }

  if (cargando) {
    return (
      <div className={styles.page}>
        <main className={styles.main}>
          <div className={styles.loading}><span className={styles.spinner} /> Cargando…</div>
        </main>
      </div>
    );
  }

  if (error || !t) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.headerInner}>
            <BotonVolver to="/dashboard" />
            <div className={styles.headerCenter}>
              <img src="/images/logo-snm.png" alt="SNM" className={styles.logo} />
            </div>
            <div className={styles.headerRight}><MenuCabecera /></div>
          </div>
        </header>
        <main className={styles.main}>
          <div className={styles.errorBox}>{error ?? "No se encontró la transferencia."}</div>
        </main>
      </div>
    );
  }

  const archivosOriginales = t.files.filter(f => f.es_original !== false);
  const archivosAnexados   = t.files.filter(f => f.es_original === false);
  const tieneCambios = (
    titulo !== (t.title ?? "") ||
    mensaje !== (t.message ?? "") ||
    destinatario !== (t.recipient ?? "") ||
    (puertoId === "" ? null : puertoId) !== (t.puerto_id ?? null) ||
    naviera !== (t.naviera ?? "") ||
    marino !== (t.marino ?? "")
  );

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <BotonVolver to="/dashboard" />
          <div className={styles.headerCenter}>
            <img src="/images/logo-snm.png" alt="SNM" className={styles.logo} />
            <div className={styles.headerText}>
              <div className={styles.org}>Servicio Nacional de Migración</div>
              <div className={styles.app}>FileDrop - SNM</div>
            </div>
          </div>
          <div className={styles.headerRight}><MenuCabecera /></div>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.titulo}>
          <h1>Procesar transferencia</h1>
          <p>Transferencia #{t.id} · {t.files.length} archivos · {formatBytes(t.total_size)}</p>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${vista === "editar" ? styles.tabActive : ""}`}
            onClick={() => setVista("editar")}
          >
            En edición
          </button>
          <button
            className={`${styles.tab} ${vista === "original" ? styles.tabActive : ""}`}
            onClick={() => setVista("original")}
          >
            <IconoCandado tamano={12} /> Original (Naviera)
          </button>
        </div>

        {vista === "original" ? (
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              Snapshot inmutable de lo que envió la Naviera
            </div>
            <div className={styles.panelBody}>
              <dl className={styles.snapList}>
                <div className={styles.snapRow}>
                  <dt>Título</dt><dd>{t.titulo_original || <em className={styles.muted}>—</em>}</dd>
                </div>
                <div className={styles.snapRow}>
                  <dt>Mensaje</dt><dd>{t.mensaje_original || <em className={styles.muted}>(sin mensaje)</em>}</dd>
                </div>
                <div className={styles.snapRow}>
                  <dt>Destinatario</dt><dd>{t.destinatario_original || <em className={styles.muted}>(no definido)</em>}</dd>
                </div>
                <div className={styles.snapRow}>
                  <dt>Archivos originales</dt>
                  <dd>
                    {archivosOriginales.length === 0
                      ? <em className={styles.muted}>(ninguno)</em>
                      : (
                        <ul className={styles.fileListPlain}>
                          {archivosOriginales.map(f => (
                            <li key={f.id}><IconoArchivo /> {f.original_name} <span className={styles.muted}>· {formatBytes(f.size)}</span></li>
                          ))}
                        </ul>
                      )}
                  </dd>
                </div>
              </dl>
            </div>
          </section>
        ) : (
          <>
            {/* Form de edición */}
            <section className={styles.panel}>
              <div className={styles.panelHeader}>Datos para el envío</div>
              <div className={styles.panelBody}>
                <div className={styles.formGrid}>
                  <div className={styles.field}>
                    <label>Título</label>
                    <input
                      className={styles.input}
                      value={titulo}
                      onChange={e => setTitulo(e.target.value)}
                      maxLength={255}
                    />
                  </div>
                  <div className={styles.field}>
                    <label>Destinatario (email)</label>
                    <input
                      className={styles.input}
                      type="email"
                      value={destinatario}
                      onChange={e => setDestinatario(e.target.value)}
                      placeholder="correo@migracion.gob.pa"
                    />
                  </div>
                  <div className={styles.fieldFull}>
                    <label>Mensaje</label>
                    <textarea
                      className={styles.textarea}
                      value={mensaje}
                      onChange={e => setMensaje(e.target.value)}
                      rows={3}
                      maxLength={2000}
                      placeholder="Añade un mensaje para el destinatario…"
                    />
                  </div>
                  <div className={styles.field}>
                    <label>Puerto / Muelle</label>
                    <select
                      className={styles.select}
                      value={puertoId}
                      onChange={e => setPuertoId(e.target.value === "" ? "" : Number(e.target.value))}
                    >
                      <option value="">— Selecciona —</option>
                      {puertos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </select>
                  </div>
                  <div className={styles.field}>
                    <label>Naviera</label>
                    <input
                      className={styles.input}
                      value={naviera}
                      onChange={e => setNaviera(e.target.value)}
                      placeholder="Nombre de la naviera"
                      maxLength={255}
                    />
                  </div>
                  <div className={styles.fieldFull}>
                    <label>Marino / motonave</label>
                    <input
                      className={styles.input}
                      value={marino}
                      onChange={e => setMarino(e.target.value)}
                      placeholder="Nombre del marino o motonave"
                      maxLength={255}
                    />
                  </div>
                  <div className={styles.fieldFull}>
                    <label>Vigencia desde el reenvío</label>
                    <p className={styles.expNota}>
                      <IconoCandado tamano={14} />
                      Al reenviar, la vigencia se renueva automáticamente a <strong>7 días</strong> desde ese momento.
                    </p>
                  </div>
                  <div className={styles.fieldFull}>
                    <label>Observaciones internas</label>
                    <textarea
                      className={styles.textarea}
                      value={observaciones}
                      onChange={e => setObservaciones(e.target.value)}
                      rows={3}
                      maxLength={2000}
                      placeholder="Notas internas del Sector Pacífico — no se envían al destinatario…"
                    />
                  </div>
                </div>

                <div className={styles.acciones}>
                  <button
                    className={styles.btnSecundario}
                    onClick={guardarCambios}
                    disabled={guardando || !tieneCambios}
                  >
                    {guardando ? <span className={styles.spinner} /> : <IconoGuardar />}
                    Guardar cambios
                  </button>
                  <button
                    className={styles.btnPrimario}
                    onClick={reenviar}
                    disabled={reenviando}
                  >
                    {reenviando ? <span className={styles.spinner} /> : <IconoEnviar />}
                    Reenviar al destinatario
                  </button>
                  <button
                    className={styles.btnDevolver}
                    onClick={() => setMostrarDevolver(v => !v)}
                    type="button"
                  >
                    <IconoDevolver />
                    Devolver a Naviera
                  </button>
                </div>

                {mostrarDevolver && (
                  <div className={styles.devolverBox}>
                    <label className={styles.devolverLabel}>Motivo (visible para la Naviera)</label>
                    <textarea
                      className={styles.textarea}
                      value={motivoDevolver}
                      onChange={e => setMotivoDevolver(e.target.value)}
                      rows={3}
                      maxLength={2000}
                      placeholder="Indica qué debe corregir o adjuntar la Naviera…"
                      autoFocus
                    />
                    <div className={styles.devolverAcciones}>
                      <button className={styles.btnCancelar} onClick={() => setMostrarDevolver(false)} type="button">
                        Cancelar
                      </button>
                      <button
                        className={styles.btnDevolverConfirmar}
                        onClick={devolverANaviera}
                        disabled={devolviendo || !motivoDevolver.trim()}
                        type="button"
                      >
                        {devolviendo ? <span className={styles.spinner} /> : <IconoDevolver />}
                        Confirmar devolución
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Archivos */}
            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                Archivos
                <span className={styles.count}>{t.files.length}</span>
              </div>
              <div className={styles.panelBody}>
                <div className={styles.fileList}>
                  {archivosOriginales.length > 0 && (
                    <div className={styles.fileGroup}>
                      <div className={styles.fileGroupTitle}><IconoEstrella /> Originales de la Naviera</div>
                      {archivosOriginales.map(f => (
                        <div key={f.id} className={styles.fileRow}>
                          <IconoArchivo />
                          <span className={styles.fileName}>{f.original_name}</span>
                          <span className={styles.fileSize}>{formatBytes(f.size)}</span>
                          <button
                            className={styles.btnPreview}
                            onClick={() => setArchivoPreview(f)}
                            title="Previsualizar archivo"
                            aria-label={`Previsualizar ${f.original_name}`}
                          >
                            <IconoOjo tamano={16} />
                          </button>
                          <button
                            className={styles.btnQuitar}
                            onClick={() => quitarArchivo(f.id)}
                            disabled={eliminandoArchivo === f.id}
                            title="Eliminar archivo"
                            aria-label={`Eliminar ${f.original_name}`}
                          >
                            {eliminandoArchivo === f.id ? <span className={styles.spinnerSm} /> : <IconoBasura />}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {archivosAnexados.length > 0 && (
                    <div className={styles.fileGroup}>
                      <div className={styles.fileGroupTitle}>Anexados por el Sector Pacífico</div>
                      {archivosAnexados.map(f => (
                        <div key={f.id} className={styles.fileRow}>
                          <IconoArchivo />
                          <span className={styles.fileName}>{f.original_name}</span>
                          <span className={styles.fileSize}>{formatBytes(f.size)}</span>
                          <button
                            className={styles.btnPreview}
                            onClick={() => setArchivoPreview(f)}
                            title="Previsualizar archivo"
                            aria-label={`Previsualizar ${f.original_name}`}
                          >
                            <IconoOjo tamano={16} />
                          </button>
                          <button
                            className={styles.btnQuitar}
                            onClick={() => quitarArchivo(f.id)}
                            disabled={eliminandoArchivo === f.id}
                            title="Eliminar archivo"
                            aria-label={`Eliminar ${f.original_name}`}
                          >
                            {eliminandoArchivo === f.id ? <span className={styles.spinnerSm} /> : <IconoBasura />}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className={styles.uploadZone}>
                  <input
                    ref={inputArchivos}
                    type="file"
                    multiple
                    hidden
                    accept={TIPOS_ACEPTADOS}
                    onChange={e => subirArchivos(e.target.files)}
                  />
                  <button
                    className={styles.btnSubir}
                    onClick={() => inputArchivos.current?.click()}
                    disabled={subiendo}
                  >
                    {subiendo ? <span className={styles.spinner} /> : <IconoSubir />}
                    Anexar más archivos
                  </button>
                </div>
              </div>
            </section>
          </>
        )}
      </main>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>

      {archivoPreview && t && (
        <ModalPreview
          token={t.token}
          archivo={archivoPreview}
          onCerrar={() => setArchivoPreview(null)}
        />
      )}
    </div>
  );
}
