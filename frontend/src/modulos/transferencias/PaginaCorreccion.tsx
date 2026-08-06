import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import type { Transferencia } from "../../types";
import { formatBytes } from "../../utils/format";
import { TIPOS_ACEPTADOS, validarArchivos } from "../../utils/archivos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import { IconoArchivo, IconoBasura, IconoSubir, IconoEnviar } from "../../components/Iconos";
import styles from "./PaginaCorreccion.module.css";

export default function PaginaCorreccion() {
  const { id: idStr } = useParams<{ id: string }>();
  const id = Number(idStr);
  const navegar = useNavigate();
  const confirmar = useConfirmar();

  const [t, setT] = useState<Transferencia | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [eliminandoArchivo, setEliminandoArchivo] = useState<number | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const inputArchivos = useRef<HTMLInputElement>(null);

  const { mostrar: mostrarToast } = useNotificacion();
  function notificar(texto: string, tipo: "ok" | "err" = "ok") {
    mostrarToast(texto, tipo === "err" ? "error" : "exito");
  }

  const cargar = useCallback(async () => {
    if (!id || Number.isNaN(id)) { setError("ID inválido."); setCargando(false); return; }
    try {
      const tr = await apiTransferencias.obtenerPorId(id);
      if (tr.status !== "returned") {
        setError("Esta transferencia no está en estado 'Devuelto'.");
      } else {
        setT(tr);
      }
    } catch (err: any) {
      const detalle = err?.response?.data?.detail ?? "No se pudo cargar la transferencia.";
      setError(typeof detalle === "string" ? detalle : "Error desconocido.");
    } finally {
      setCargando(false);
    }
  }, [id]);

  useEffect(() => { cargar(); }, [cargar]);

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
      const tr = await apiTransferencias.corregirQuitarArchivo(id, archivoId);
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
      const tr = await apiTransferencias.corregirAgregarArchivos(id, fd);
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

  async function reEnviar() {
    if (!t) return;
    if (t.files.length === 0) { notificar("Debes tener al menos un archivo antes de re-enviar.", "err"); return; }
    const ok = await confirmar({
      titulo: "Re-enviar a revisión",
      mensaje: "La documentación se enviará nuevamente al Sector Pacífico para revisión.",
      textoOk: "Re-enviar",
    });
    if (!ok) return;
    setEnviando(true);
    try {
      await apiTransferencias.resubmit(id);
      notificar("Enviado a revisión — el Sector Pacífico procesará tu documentación.");
      setTimeout(() => navegar("/dashboard"), 1500);
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      notificar(typeof detalle === "string" ? detalle : "Error al re-enviar.", "err");
    } finally {
      setEnviando(false);
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
          <h1>Corregir transferencia</h1>
          <p>Transferencia #{t.id} · {t.files.length} archivos · {formatBytes(t.total_size)}</p>
        </div>

        {/* Motivo de devolución */}
        <section className={styles.motivoSection}>
          <div className={styles.motivoHeader}>Motivo de devolución — Sector Pacífico</div>
          <div className={styles.motivoBody}>
            {t.observaciones
              ? <p className={styles.motivoTexto}>{t.observaciones}</p>
              : <p className={styles.muted}>No se indicó un motivo específico.</p>}
          </div>
        </section>

        {/* Archivos */}
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            Documentos adjuntos
            <span className={styles.count}>{t.files.length}</span>
          </div>
          <div className={styles.panelBody}>
            {t.files.length > 0 ? (
              <div className={styles.fileList}>
                {t.files.map(f => (
                  <div key={f.id} className={styles.fileRow}>
                    <IconoArchivo />
                    <span className={styles.fileName}>{f.original_name}</span>
                    <span className={styles.fileSize}>{formatBytes(f.size)}</span>
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
            ) : (
              <p className={styles.muted}>No hay archivos — sube al menos uno antes de re-enviar.</p>
            )}

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
                Añadir archivos
              </button>
            </div>
          </div>
        </section>

        {/* Acción re-enviar */}
        <div className={styles.accionFinal}>
          <button
            className={styles.btnEnviar}
            onClick={reEnviar}
            disabled={enviando || t.files.length === 0}
          >
            {enviando ? <span className={styles.spinner} /> : <IconoEnviar />}
            Re-enviar a revisión
          </button>
        </div>
      </main>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
