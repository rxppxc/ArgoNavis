/**
 * Panel principal — dashboard.
 *
 * Storage simple, dos experiencias según el rol:
 *
 *  - **Naviera**: lista de sus propias transferencias. Puede ver, copiar el
 *    enlace y eliminar las que subió.
 *  - **Sector Pacífico** (y Admin): ve TODO lo que suben las navieras —
 *    previsualiza, descarga, copia el enlace. No procesa ni edita nada.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { usePermisos } from "../../hooks/usePermisos";
import type { Transferencia } from "../../types";
import { formatBytes, formatDate } from "../../utils/format";
import { copiarAlPortapapeles } from "../../utils/portapapeles";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { MenuCabecera } from "../../components/MenuCabecera";
import FiltroFechas, { type RangoFechas } from "../../components/FiltroFechas";
import FranjaKPI from "../../components/FranjaKPI";
import {
  IconoMas, IconoCarpeta, IconoArchivo, IconoPeso, IconoDescargar,
  IconoReloj, IconoEnlace, IconoCheck, IconoBasura, IconoOjo,
  IconoNube, IconoGrafico, IconoActividad,
} from "../../components/Iconos";
import styles from "./PaginaPanel.module.css";

function TransferCard({
  t, esPropia, copiado, eliminando, copiarEnlace, eliminarTransferencia, expanded, onToggle,
}: {
  t: Transferencia;
  esPropia: boolean;
  copiado: string | null;
  eliminando: Set<string>;
  copiarEnlace: (token: string) => void;
  eliminarTransferencia: (token: string) => void;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={`${styles.card} ${expanded ? styles.cardOpen : ""}`}>
      <div className={styles.cardTop} onClick={onToggle} role="button" tabIndex={0} onKeyDown={e => e.key === "Enter" && onToggle()}>
        <div className={styles.cardLeft}>
          <div className={styles.fileIcon}><IconoCarpeta tamano={18} /></div>
          <div className={styles.cardInfo}>
            <div className={styles.cardTitle}>{t.title || "Sin título"}</div>
            {t.message && (
              <div className={styles.cardMessagePreview}>
                &ldquo;{t.message}&rdquo;
              </div>
            )}
            <div className={styles.cardMeta}>
              <span className={styles.metaItem}><IconoArchivo tamano={13} />{t.files.length} archivo{t.files.length !== 1 ? "s" : ""}</span>
              <span className={styles.metaItem}><IconoPeso />{formatBytes(t.total_size)}</span>
              <span className={styles.metaItem}><IconoDescargar tamano={13} />{t.downloads} descarga{t.downloads !== 1 ? "s" : ""}</span>
              {t.expires_at && (
                <span className={styles.metaItem}><IconoReloj />{formatDate(t.expires_at)}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className={styles.cardDetail}>
          {t.message && (
            <div className={styles.cardMessage}>
              <span className={styles.msgQuote}>"</span>
              {t.message}
              <span className={styles.msgQuote}>"</span>
            </div>
          )}
          {t.files.length > 0 && (
            <div className={styles.fileExpandList}>
              {t.files.map(f => (
                <div key={f.id} className={styles.fileExpandItem}>
                  <IconoArchivo tamano={13} />
                  <span className={styles.fileExpandName}>{f.original_name}</span>
                  <span className={styles.fileExpandSize}>{formatBytes(f.size)}</span>
                </div>
              ))}
            </div>
          )}
          <div className={styles.actions} onClick={e => e.stopPropagation()}>
            <Link to={`/t/${t.token}`} className={styles.btnView}>
              <IconoOjo />Ver
            </Link>
            <button
              className={`${styles.btnCopy} ${copiado === t.token ? styles.copied : ""}`}
              onClick={() => copiarEnlace(t.token)}
            >
              {copiado === t.token ? <><IconoCheck tamano={13} />Copiado</> : <><IconoEnlace />Copiar enlace</>}
            </button>
            {esPropia && (
              <button
                className={styles.btnDelete}
                onClick={() => eliminarTransferencia(t.token)}
                disabled={eliminando.has(t.token)}
                title="Eliminar"
                aria-label={`Eliminar ${t.title || "transferencia sin título"}`}
              >
                <IconoBasura tamano={15} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PaginaPanel() {
  const { usuario } = useAutenticacion();
  const { tiene, esAdmin } = usePermisos();
  const confirmar = useConfirmar();
  const { mostrar: mostrarToast } = useNotificacion();

  const vistaTodas = tiene("T-PROCESAR-PACIFICO") || esAdmin;

  // ── Estado ─────────────────────────────────────────────────────────────────
  const [transferencias,   setTransferencias]   = useState<Transferencia[]>([]);
  const [cargando,         setCargando]         = useState(true);
  const [copiado,          setCopiado]          = useState<string | null>(null);
  const [eliminando,       setEliminando]       = useState<Set<string>>(new Set());
  const [error,            setError]            = useState<string | null>(null);
  const [mostrarExpiradas, setMostrarExpiradas] = useState(false);
  const [expandidos,       setExpandidos]       = useState<Set<string>>(new Set());
  const [rangoFecha,       setRangoFecha]       = useState<RangoFechas>({ desde: null, hasta: null });

  // ── Carga inicial de transferencias según rol ─────────────────────────────
  useEffect(() => {
    const promesa = vistaTodas ? apiTransferencias.listarTodasActivas() : apiTransferencias.listar();
    promesa
      .then(setTransferencias)
      .catch(() => setError("No se pudieron cargar las transferencias."))
      .finally(() => setCargando(false));
  }, [vistaTodas]);

  // ── Acciones ──────────────────────────────────────────────────────────────
  async function copiarEnlace(token: string) {
    const ok = await copiarAlPortapapeles(`${window.location.origin}/t/${token}`);
    if (!ok) {
      mostrarToast("No se pudo copiar el enlace. Copiálo manualmente.", "error");
      return;
    }
    setCopiado(token);
    setTimeout(() => setCopiado(null), 2200);
  }

  async function eliminarTransferencia(token: string) {
    const ok = await confirmar({
      titulo: "Eliminar transferencia",
      mensaje: "Se eliminarán la transferencia y todos sus archivos. Esta acción no se puede deshacer.",
      textoOk: "Eliminar",
      peligroso: true,
    });
    if (!ok) return;
    if (eliminando.has(token)) return;
    setEliminando((prev) => new Set(prev).add(token));
    try {
      await apiTransferencias.eliminar(token);
      setTransferencias((prev) => prev.filter((t) => t.token !== token));
      setExpandidos((prev) => { const s = new Set(prev); s.delete(token); return s; });
    } catch {
      setError("No se pudo eliminar la transferencia. Inténtalo de nuevo.");
    } finally {
      setEliminando((prev) => { const s = new Set(prev); s.delete(token); return s; });
    }
  }

  function toggleCard(token: string) {
    setExpandidos(prev => { const s = new Set(prev); if (s.has(token)) s.delete(token); else s.add(token); return s; });
  }

  // ── Datos derivados ───────────────────────────────────────────────────────
  const transferenciasFecha =
    rangoFecha.desde === null && rangoFecha.hasta === null
      ? transferencias
      : transferencias.filter((t) => {
          const f = (t.created_at || "").slice(0, 10); // YYYY-MM-DD
          if (rangoFecha.desde && f < rangoFecha.desde) return false;
          if (rangoFecha.hasta && f > rangoFecha.hasta) return false;
          return true;
        });

  const activas   = transferenciasFecha.filter((t) => !t.is_expired);
  const expiradas = transferenciasFecha.filter((t) =>  t.is_expired);

  const estadisticas = {
    total:          transferencias.length,
    activas:        transferencias.filter(t => !t.is_expired).length,
    totalDescargas: transferencias.reduce((s, t) => s + t.downloads, 0),
  };

  const hayFiltroFecha     = rangoFecha.desde !== null || rangoFecha.hasta !== null;
  const mostrarFiltroFecha = vistaTodas && transferencias.length > 0;
  const sinResultadosFecha = hayFiltroFecha && activas.length === 0 && expiradas.length === 0;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div />
          <div className={styles.brand}>
            <img src="/images/logo-snm.png" alt="SNM" />
            <div className={styles.brandText}>
              <div className={styles.org}>Servicio Nacional de Migración</div>
              <div className={styles.app}>FileDrop - SNM</div>
            </div>
          </div>
          <div className={styles.headerRight}>
            <MenuCabecera />
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.topRow}>
          <div className={styles.topRowLeft} />
          <h1 className={styles.pageTitle}>
            Bienvenido, {usuario?.full_name?.split(" ")[0] ?? usuario?.username}
            <span>{vistaTodas ? "Archivos subidos por las navieras" : "Mis transferencias"}</span>
          </h1>
          <div className={styles.topRowRight}>
            {(tiene("T-CREAR-BASICA") || esAdmin) && (
              <Link to="/new" className={styles.btnNew}>
                <IconoMas />
                Subir archivos
              </Link>
            )}
          </div>
        </div>

        {error && (
          <div style={{
            background: "rgba(239,68,68,.13)", border: "1px solid rgba(239,68,68,.22)",
            borderRadius: 8, color: "var(--acc-red)", padding: "11px 14px",
            marginBottom: 20, fontSize: ".87rem",
          }}>
            {error}
          </div>
        )}

        {transferencias.length > 0 && (
          <FranjaKPI items={[
            { icono: <IconoGrafico tamano={18} />, valor: estadisticas.total, etiqueta: "Transferencias totales", color: "gold" },
            { icono: <IconoActividad tamano={18} />, valor: estadisticas.activas, etiqueta: "Activas", color: "green" },
            { icono: <IconoDescargar tamano={18} />, valor: estadisticas.totalDescargas, etiqueta: "Descargas totales", color: "blue" },
          ]} />
        )}

        {cargando ? (
          <div className={styles.loadingWrap}>
            <div className={styles.loadingSpinner} />
            Cargando transferencias…
          </div>
        ) : transferencias.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIllustration}><IconoNube /></div>
            <h3>Sin transferencias aún</h3>
            <p>{vistaTodas
              ? "Aún no hay archivos subidos por ninguna naviera."
              : "Sube tus primeros archivos para generar un enlace de descarga seguro."}</p>
            {(tiene("T-CREAR-BASICA") || esAdmin) && (
              <Link to="/new" className={styles.btnNew}>
                <IconoMas />
                Subir primeros archivos
              </Link>
            )}
          </div>
        ) : (
          <>
            {mostrarFiltroFecha && (
              <FiltroFechas valor={rangoFecha} onCambio={setRangoFecha} />
            )}

            {sinResultadosFecha && (
              <div className={styles.empty}>
                <div className={styles.emptyIllustration}><IconoReloj tamano={34} /></div>
                <h3>Sin transferencias en el rango</h3>
                <p>No hay transferencias creadas en las fechas seleccionadas. Ajusta o limpia el filtro de fecha.</p>
              </div>
            )}

            {activas.length > 0 && (
              <div className={styles.list}>
                {activas.map(t => (
                  <TransferCard
                    key={t.token}
                    t={t}
                    esPropia={t.user_id === usuario?.id}
                    copiado={copiado}
                    eliminando={eliminando}
                    copiarEnlace={copiarEnlace}
                    eliminarTransferencia={eliminarTransferencia}
                    expanded={expandidos.has(t.token)}
                    onToggle={() => toggleCard(t.token)}
                  />
                ))}
              </div>
            )}

            {/* ── Expiradas ── */}
            {expiradas.length > 0 && (
              <div className={styles.expiredSection}>
                <button
                  className={styles.expiredToggle}
                  onClick={() => setMostrarExpiradas((v) => !v)}
                >
                  <span className={styles.expiredToggleLabel}>
                    Expiradas
                    <span className={styles.expiredCount}>{expiradas.length}</span>
                  </span>
                  <span className={`${styles.expiredChevron} ${mostrarExpiradas ? styles.expiredChevronOpen : ""}`}>
                    ›
                  </span>
                </button>

                {mostrarExpiradas && (
                  <div className={styles.expiredList}>
                    {expiradas.map((t) => (
                      <div key={t.token} className={`${styles.card} ${styles.cardExpired}`}>
                        <div className={styles.cardTop}>
                          <div className={styles.cardLeft}>
                            <div className={styles.fileIcon}><IconoCarpeta tamano={18} /></div>
                            <div className={styles.cardInfo}>
                              <div className={styles.cardTitle}>{t.title || "Sin título"}</div>
                              <div className={styles.cardMeta}>
                                <span className={styles.metaItem}><IconoArchivo tamano={13} />{t.files.length} archivo{t.files.length !== 1 ? "s" : ""}</span>
                                <span className={styles.metaItem}><IconoPeso />{formatBytes(t.total_size)}</span>
                                <span className={styles.metaItem}><IconoDescargar tamano={13} />{t.downloads} descarga{t.downloads !== 1 ? "s" : ""}</span>
                              </div>
                              <div className={styles.badges}>
                                <span className={styles.badgeExpired}>Expirado</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className={styles.cardDetail}>
                          <div className={styles.actions}>
                            <Link to={`/t/${t.token}`} className={styles.btnView}>
                              <IconoOjo />Ver
                            </Link>
                            {t.user_id === usuario?.id && (
                              <button
                                className={styles.btnDelete}
                                onClick={() => eliminarTransferencia(t.token)}
                                disabled={eliminando.has(t.token)}
                                title="Eliminar"
                                aria-label={`Eliminar ${t.title || "transferencia sin título"}`}
                              >
                                <IconoBasura tamano={15} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
