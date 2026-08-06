import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import type { TransferenciaPublica } from "../../types";
import { formatBytes, formatDate } from "../../utils/format";
import { infoTipo } from "../../utils/tipoArchivo";
import { copiarAlPortapapeles } from "../../utils/portapapeles";
import { useNotificacion } from "../../components/Notificaciones";
import { BotonVolver } from "../../components/BotonVolver";
import {
  IconoCarpeta, IconoArchivo, IconoDescargar, IconoEnlace,
  IconoCheck, IconoReloj, IconoXCirculo, IconoExito, IconoOjo,
  IconoX, IconoImagen, IconoPdf,
} from "../../components/Iconos";
import styles from "./PaginaTransferencia.module.css";

// ── Componente ────────────────────────────────────────────
export default function PaginaTransferencia() {
  const { token } = useParams<{ token: string }>();
  const [params] = useSearchParams();
  const esNuevo = params.get("new") === "1";
  const { estaAutenticado } = useAutenticacion();
  const { mostrar: mostrarToast } = useNotificacion();

  const [transferencia, setTransferencia] = useState<TransferenciaPublica | null>(null);
  const [cargando,      setCargando]      = useState(true);
  const [noEncontrado,  setNoEncontrado]  = useState(false);
  const [copiado,       setCopiado]       = useState(false);
  const [modalAbierto,  setModalAbierto]  = useState(false);
  const [avisoVolver,   setAvisoVolver]   = useState(false);
  const timersRef = useRef<number[]>([]);

  // Cancela cualquier timer pendiente al desmontar para evitar setState tardío
  useEffect(() => () => { timersRef.current.forEach(window.clearTimeout); }, []);

  function programar(callback: () => void, ms: number) {
    const id = window.setTimeout(callback, ms);
    timersRef.current.push(id);
  }

  function intentarVolver() {
    setAvisoVolver(true);
    programar(() => setAvisoVolver(false), 3500);
  }

  useEffect(() => {
    if (!token) return;
    apiTransferencias.obtenerPublica(token)
      .then(setTransferencia)
      .catch(() => setNoEncontrado(true))
      .finally(() => setCargando(false));
  }, [token]);

  const cerrarModal = useCallback(() => setModalAbierto(false), []);

  useEffect(() => {
    if (!modalAbierto) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") cerrarModal(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalAbierto, cerrarModal]);

  async function copiarEnlace() {
    const url = new URL(window.location.href);
    url.search = "";
    const ok = await copiarAlPortapapeles(url.toString());
    if (!ok) {
      mostrarToast("No se pudo copiar el enlace. Copiálo manualmente.", "error");
      return;
    }
    setCopiado(true);
    programar(() => setCopiado(false), 2200);
  }

  // Icono del encabezado según tipo de transferencia
  function iconoEncabezado() {
    if (!transferencia || transferencia.files.length !== 1) return <IconoCarpeta tamano={26} />;
    const { categoria } = infoTipo(transferencia.files[0].mime_type, transferencia.files[0].original_name);
    if (categoria === "imagen") return <IconoImagen />;
    if (categoria === "pdf")   return <IconoPdf />;
    return <IconoCarpeta tamano={26} />;
  }

  // Botón de preview para archivo único imagen o PDF
  function botonPreview() {
    if (!transferencia || transferencia.files.length !== 1 || !token) return null;
    const { categoria } = infoTipo(transferencia.files[0].mime_type, transferencia.files[0].original_name);
    if (categoria !== "imagen" && categoria !== "pdf") return null;
    return (
      <button className={styles.previewBtn} onClick={() => setModalAbierto(true)}>
        <IconoOjo tamano={16} />
        Previsualizar archivo
      </button>
    );
  }

  // Contenido del modal según tipo
  function contenidoModal() {
    if (!transferencia || transferencia.files.length !== 1 || !token) return null;
    const archivo = transferencia.files[0];
    const { categoria } = infoTipo(archivo.mime_type, archivo.original_name);
    const urlPrev = apiTransferencias.urlPreview(token, archivo.id);

    if (categoria === "imagen") {
      return <img src={urlPrev} alt={archivo.original_name} className={styles.modalImg} />;
    }
    if (categoria === "pdf") {
      return <iframe src={urlPrev} title={archivo.original_name} className={styles.modalPdf} />;
    }
    return null;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          {estaAutenticado
            ? <BotonVolver to="/dashboard" />
            : <BotonVolver onClick={intentarVolver} />
          }
          <div className={styles.headerCenter}>
            <img src="/images/logo-snm.png" alt="SNM" className={styles.logo} />
            <div className={styles.headerText}>
              <div className={styles.org}>Servicio Nacional de Migración</div>
              <div className={styles.app}>FileDrop - SNM</div>
            </div>
          </div>
          <div />
        </div>
      </header>

      {avisoVolver && (
        <div className={styles.toastAviso}>
          Esta opción no está disponible para usuarios externos.
        </div>
      )}

      <div className={styles.body}>
        {cargando ? (
          <div className={styles.loading}>
            <div className={styles.loadingSpinner} />
            Cargando transferencia…
          </div>
        ) : noEncontrado ? (
          <div className={styles.card}>
            <div className={styles.stateCard}>
              <div className={`${styles.stateIcon} ${styles.error}`}><IconoXCirculo /></div>
              <h2>Transferencia no encontrada</h2>
              <p>El enlace puede ser inválido o haber sido eliminado.</p>
            </div>
          </div>
        ) : transferencia!.is_expired ? (
          <div className={styles.card}>
            <div className={styles.stateCard}>
              <div className={`${styles.stateIcon} ${styles.expired}`}><IconoReloj tamano={32} /></div>
              <h2>Enlace expirado</h2>
              <p>Este enlace ya no está disponible para descarga.</p>
            </div>
          </div>
        ) : (
          <div className={styles.card}>
            {esNuevo && (
              <div className={styles.successBanner}>
                <IconoExito />
                ¡Transferencia creada! Comparte el enlace de abajo.
              </div>
            )}

            <div className={styles.cardHeader}>
              <div className={styles.iconWrap}>{iconoEncabezado()}</div>
              <h1 className={styles.cardTitle}>{transferencia!.title || "Transferencia de archivos"}</h1>
              <p className={styles.sender}>Enviado por <strong>{transferencia!.sender}</strong></p>
            </div>

            {transferencia!.message && (
              <div className={styles.message}>{transferencia!.message}</div>
            )}

            {/* Botón de preview para archivo único */}
            {botonPreview()}

            <div className={styles.filesSection}>
              <div className={styles.filesMeta}>
                <IconoArchivo tamano={15} />
                {transferencia!.files.length} archivo{transferencia!.files.length !== 1 ? "s" : ""} · {formatBytes(transferencia!.total_size)}
              </div>
              <ul className={styles.fileList}>
                {transferencia!.files.map((f) => {
                  const tipo = infoTipo(f.mime_type, f.original_name);
                  return (
                    <li key={f.id} className={styles.fileItem}>
                      <span className={styles.fileItemIcon}><IconoArchivo tamano={15} /></span>
                      <span className={styles.fileName}>{f.original_name}</span>
                      <span className={`${styles.typeBadge} ${styles[`badge_${tipo.categoria}`]}`}>
                        {tipo.etiqueta}
                      </span>
                      <span className={styles.fileSize}>{formatBytes(f.size)}</span>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className={styles.infoRow}>
              <span className={styles.infoItem}><IconoDescargar tamano={12} />{transferencia!.downloads} descarga{transferencia!.downloads !== 1 ? "s" : ""}</span>
              {transferencia!.expires_at && (
                <span className={styles.infoItem}><IconoReloj tamano={12} />Expira: {formatDate(transferencia!.expires_at)}</span>
              )}
            </div>

            <a
              href={apiTransferencias.urlDescarga(token!)}
              className={styles.downloadBtn}
              target="_blank"
              rel="noreferrer"
            >
              <IconoDescargar />
              Descargar {transferencia!.files.length > 1 ? "todos (.zip)" : "archivo"}
            </a>

            <div className={styles.shareSection}>
              <div className={styles.shareLabel}><IconoEnlace tamano={12} />Enlace para compartir</div>
              <div className={styles.shareRow}>
                <span className={styles.shareUrl}>{new URL(window.location.href).origin + new URL(window.location.href).pathname}</span>
                <button className={`${styles.copyBtn} ${copiado ? styles.copied : ""}`} onClick={copiarEnlace}>
                  {copiado ? <><IconoCheck tamano={12} />Copiado</> : <><IconoEnlace tamano={12} />Copiar</>}
                </button>
              </div>
            </div>

          </div>
        )}
      </div>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>

      {/* Modal de previsualización */}
      {modalAbierto && (
        <div className={styles.modalBackdrop} onClick={cerrarModal}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <span className={styles.modalTitle}>
                <IconoOjo tamano={11} /> {transferencia?.files[0]?.original_name}
              </span>
              <button className={styles.modalClose} onClick={cerrarModal} aria-label="Cerrar">
                <IconoX tamano={18} />
              </button>
            </div>
            <div className={styles.modalBody}>
              {contenidoModal()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
