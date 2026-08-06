/**
 * Panel principal — dashboard.
 *
 * Muestra tres experiencias distintas según el rol del usuario:
 *
 *  - **Naviera**: lista simple de sus transferencias, con banner para
 *    corregir las devueltas por Sector Pacífico.
 *  - **Sector Pacífico**: cola de revisión unificada (borradores enviados por
 *    navieras + transferencias devueltas por el Muelle con badge propio).
 *  - **Muelle/Operador**: vista jerárquica Puerto → Naviera → Marino de las
 *    transferencias activas asignadas a los puertos que tiene a cargo. Puede
 *    ver, descargar, copiar el enlace, devolver a SP o marcar como procesada.
 *
 *  Admin ve la unión: cola de SP + jerarquía de Muelle.
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
import { ModalDevolucion } from "../../components/ModalDevolucion";
import { useNotificacion } from "../../components/Notificaciones";
import { MenuCabecera } from "../../components/MenuCabecera";
import FiltroFechas, { type RangoFechas } from "../../components/FiltroFechas";
import FranjaKPI from "../../components/FranjaKPI";
import {
  IconoMas, IconoCarpeta, IconoArchivo, IconoPeso, IconoDescargar,
  IconoReloj, IconoEnlace, IconoCheck, IconoBasura, IconoOjo,
  IconoNube, IconoGrafico, IconoActividad, IconoAncla, IconoBandeja,
  IconoUsuario, IconoChevronDerecha, IconoMuelle, IconoProcesada, IconoDevolver,
} from "../../components/Iconos";
import styles from "./PaginaPanel.module.css";

type Modo = "naviera" | "sp" | "muelle";

const IconChevron = ({ open }: { open: boolean }) => (
  <span style={{ display: "inline-flex", transform: open ? "rotate(90deg)" : "none", transition: "transform 0.2s" }}>
    <IconoChevronDerecha />
  </span>
);

function TransferCard({
  t, modo, copiado, eliminando, copiarEnlace, eliminarTransferencia,
  expanded, onToggle, marcarProcesada, devolverAlSP, usuarioActualId,
}: {
  t: Transferencia;
  modo: Modo;
  copiado: string | null;
  eliminando: Set<string>;
  copiarEnlace: (token: string) => void;
  eliminarTransferencia: (token: string) => void;
  expanded: boolean;
  onToggle: () => void;
  marcarProcesada: (id: number) => void;
  devolverAlSP: (id: number, titulo: string | null) => void;
  usuarioActualId: number | undefined;
}) {
  const esSP     = modo === "sp";
  const esMuelle = modo === "muelle";
  const esPropia = t.user_id === usuarioActualId;

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
            <div className={styles.badges}>
              {t.status === "active"    && <span className={styles.badgeActive}>Activo</span>}
              {t.status === "returned"  && <span className={styles.badgeReturned}>Requiere corrección</span>}
              {t.status === "review"    && <span className={styles.badgeReview}>Devuelto por Muelle</span>}
              {t.status === "processed" && <span className={styles.badgeProcessed}><IconoProcesada tamano={12} />Procesada</span>}
            </div>
          </div>
        </div>
        <div className={styles.cardChevron}>
          <IconChevron open={expanded} />
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
          {(t.status === "returned" || t.status === "review") && t.observaciones && (
            <div className={styles.motivoBox}>
              <span className={styles.motivoLabel}>
                {t.status === "review" ? "Motivo del Muelle:" : "Motivo de devolución:"}
              </span>
              <span className={styles.motivoTexto}>{t.observaciones}</span>
            </div>
          )}
          <div className={styles.actions} onClick={e => e.stopPropagation()}>

            {/* ─── Modo NAVIERA ─── */}
            {modo === "naviera" && (
              <>
                {t.status === "draft" && (
                  <Link to={`/t/${t.token}`} className={styles.btnView}>
                    <IconoOjo />Ver
                  </Link>
                )}
                {t.status === "returned" && (
                  <Link to={`/transfers/${t.id}/corregir`} className={styles.btnCorregir}>
                    Corregir
                  </Link>
                )}
                {t.status === "active" && (
                  <>
                    <Link to={`/t/${t.token}`} className={styles.btnView}>
                      <IconoOjo />Ver
                    </Link>
                    <button
                      className={`${styles.btnCopy} ${copiado === t.token ? styles.copied : ""}`}
                      onClick={() => copiarEnlace(t.token)}
                    >
                      {copiado === t.token ? <><IconoCheck tamano={13} />Copiado</> : <><IconoEnlace />Copiar enlace</>}
                    </button>
                  </>
                )}
              </>
            )}

            {/* ─── Modo SECTOR PACÍFICO ─── */}
            {esSP && (
              <>
                {(t.status === "draft" || t.status === "review") && (
                  <Link to={`/transfers/${t.id}/procesar`} className={styles.btnProcesar}>
                    {t.status === "review" ? "Revisar de nuevo" : "Abrir"}
                  </Link>
                )}
                {t.status === "returned" && (
                  <Link to={`/transfers/${t.id}/procesar`} className={styles.btnProcesar}>
                    Revisar
                  </Link>
                )}
                {t.status === "active" && (
                  <>
                    <Link to={`/t/${t.token}`} className={styles.btnView}>
                      <IconoOjo />Ver
                    </Link>
                    <button
                      className={`${styles.btnCopy} ${copiado === t.token ? styles.copied : ""}`}
                      onClick={() => copiarEnlace(t.token)}
                    >
                      {copiado === t.token ? <><IconoCheck tamano={13} />Copiado</> : <><IconoEnlace />Copiar enlace</>}
                    </button>
                    <Link to={`/transfers/${t.id}/procesar`} className={styles.btnProcesar}>
                      Editar
                    </Link>
                  </>
                )}
              </>
            )}

            {/* ─── Modo MUELLE/OPERADOR ─── */}
            {esMuelle && t.status === "active" && (
              <>
                <Link to={`/t/${t.token}`} className={styles.btnView}>
                  <IconoOjo />Ver
                </Link>
                <button
                  className={`${styles.btnCopy} ${copiado === t.token ? styles.copied : ""}`}
                  onClick={() => copiarEnlace(t.token)}
                >
                  {copiado === t.token ? <><IconoCheck tamano={13} />Copiado</> : <><IconoEnlace />Copiar enlace</>}
                </button>
                <button
                  className={styles.btnDevolverMuelle}
                  onClick={() => devolverAlSP(t.id, t.title)}
                  title="Devolver a Sector Pacífico"
                >
                  <IconoDevolver />Devolver a SP
                </button>
                <button
                  className={styles.btnMarcarProcesada}
                  onClick={() => marcarProcesada(t.id)}
                  title="Marcar como procesada"
                >
                  <IconoProcesada />Marcar procesada
                </button>
              </>
            )}

            {/* Eliminar: solo el dueño real de la transferencia (el backend lo exige), nunca Muelle */}
            {!esMuelle && esPropia && (
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

// ── Agrupación Puerto → Naviera → Marino ──────────────────────────────────────

type MarinoGroup  = { nombre: string; items: Transferencia[] };
type NavieraGroup = { nombre: string; marinos: MarinoGroup[] };
type PuertoGroup  = { id: number | null; nombre: string; navieras: NavieraGroup[] };

function agrupar(activas: Transferencia[]): { grupos: PuertoGroup[]; sinNaviera: Transferencia[] } {
  const puertoMap = new Map<number | null, PuertoGroup>();
  const sinNaviera: Transferencia[] = [];

  for (const t of activas) {
    const navieraNombre = t.naviera?.trim();
    if (!navieraNombre) {
      sinNaviera.push(t);
      continue;
    }
    const puertoId     = t.puerto?.id ?? null;
    const puertoNombre = t.puerto?.nombre ?? "Sin puerto";

    if (!puertoMap.has(puertoId)) {
      puertoMap.set(puertoId, { id: puertoId, nombre: puertoNombre, navieras: [] });
    }
    const puertoGroup = puertoMap.get(puertoId)!;

    let navieraGroup = puertoGroup.navieras.find(n => n.nombre === navieraNombre);
    if (!navieraGroup) {
      navieraGroup = { nombre: navieraNombre, marinos: [] };
      puertoGroup.navieras.push(navieraGroup);
    }

    const marinoNombre = t.marino?.trim() || "Sin marino";
    let marinoGroup = navieraGroup.marinos.find(m => m.nombre === marinoNombre);
    if (!marinoGroup) {
      marinoGroup = { nombre: marinoNombre, items: [] };
      navieraGroup.marinos.push(marinoGroup);
    }
    marinoGroup.items.push(t);
  }

  const grupos = Array.from(puertoMap.values()).sort((a, b) => {
    if (a.id === null) return 1;
    if (b.id === null) return -1;
    return a.nombre.localeCompare(b.nombre);
  });
  for (const pg of grupos) {
    pg.navieras.sort((a, b) => a.nombre.localeCompare(b.nombre));
    for (const ng of pg.navieras) {
      ng.marinos.sort((a, b) => a.nombre.localeCompare(b.nombre));
    }
  }
  return { grupos, sinNaviera };
}

export default function PaginaPanel() {
  const { usuario } = useAutenticacion();
  const { tiene, esAdmin } = usePermisos();
  const confirmar = useConfirmar();
  const { mostrar: mostrarToast } = useNotificacion();

  const puedeProcesarPacifico = tiene("T-PROCESAR-PACIFICO");
  const puedeOperarMuelle     = tiene("T-PROCESAR-MUELLE");
  const vistaColaSP           = puedeProcesarPacifico || esAdmin;
  const vistaJerarquica       = puedeOperarMuelle || esAdmin;

  // Naviera = usuario sin ningún rol operativo → ve sus propias.
  const esNavieraSola = !puedeProcesarPacifico && !puedeOperarMuelle && !esAdmin;

  // ── Estado ─────────────────────────────────────────────────────────────────
  const [transferencias,   setTransferencias]   = useState<Transferencia[]>([]);
  const [cola,             setCola]             = useState<Transferencia[]>([]);
  const [cargando,         setCargando]         = useState(true);
  const [copiado,          setCopiado]          = useState<string | null>(null);
  const [eliminando,       setEliminando]       = useState<Set<string>>(new Set());
  const [error,            setError]            = useState<string | null>(null);
  const [mostrarExpiradas, setMostrarExpiradas] = useState(false);
  const [colaAbierta,      setColaAbierta]      = useState(true);
  const [procesadasAbierta, setProcesadasAbierta] = useState(true);
  const [expandidos,       setExpandidos]       = useState<Set<string>>(new Set());
  const [puertoAbiertos,   setPuertoAbiertos]   = useState<Set<string>>(new Set());
  const [navieraAbiertos,  setNavieraAbiertos]  = useState<Set<string>>(new Set());
  const [marinoAbiertos,   setMarinoAbiertos]   = useState<Set<string>>(new Set());
  const [busqueda]                              = useState("");
  const [verTodaCola,      setVerTodaCola]      = useState(false);
  const [modalDevolverId, setModalDevolverId]   = useState<{ id: number; titulo: string | null } | null>(null);
  const [rangoFecha,       setRangoFecha]       = useState<RangoFechas>({ desde: null, hasta: null });

  // ── Carga inicial de transferencias según rol ─────────────────────────────
  useEffect(() => {
    if (vistaJerarquica) {
      // Admin: ve todas las active. Muelle/Operador: solo su cola filtrada por puertos.
      const promesa = esAdmin
        ? apiTransferencias.listarTodasActivas()
        : apiTransferencias.colaMuelle();
      promesa
        .then(setTransferencias)
        .catch(() => setError("No se pudieron cargar las transferencias."))
        .finally(() => setCargando(false));
    } else if (vistaColaSP) {
      // SP sin admin ni jerarquía: además de su cola de revisión (bloque
      // superior), ve todas las transferencias activas — así las que ya
      // procesó (o procesó cualquier otro SP) no desaparecen sin dejar rastro,
      // quedan agrupadas más abajo en "Procesadas".
      apiTransferencias.listarTodasActivas()
        .then(setTransferencias)
        .catch(() => setError("No se pudieron cargar las transferencias."))
        .finally(() => setCargando(false));
    } else {
      // Naviera → lista simple de propias.
      apiTransferencias.listar()
        .then(setTransferencias)
        .catch(() => setError("No se pudieron cargar las transferencias."))
        .finally(() => setCargando(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vistaJerarquica, vistaColaSP, esAdmin]);

  // Cola de SP: borradores + devueltos por Muelle.
  useEffect(() => {
    if (!vistaColaSP) return;
    apiTransferencias.colaPacifico().then(setCola).catch(() => {});
  }, [vistaColaSP]);

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

  async function marcarProcesadaMuelle(id: number) {
    const ok = await confirmar({
      titulo: "Marcar como procesada",
      mensaje: "Se marcará esta transferencia como procesada. Es el paso final del flujo y no podrá revertirse desde el sistema.",
      textoOk: "Sí, marcar como procesada",
    });
    if (!ok) return;
    try {
      const actualizada = await apiTransferencias.marcarProcesada(id);
      // Sacamos de la lista de la bandeja (queda solo procesadas → no aparece en cola muelle)
      setTransferencias(prev => prev.filter(t => t.id !== id));
      mostrarToast(`"${actualizada.title || "Transferencia"}" marcada como procesada.`, "exito");
    } catch (e: any) {
      mostrarToast(e?.response?.data?.detail ?? "No se pudo marcar como procesada.", "error");
    }
  }

  async function ejecutarDevolucionAlSP(id: number, motivo: string) {
    try {
      const actualizada = await apiTransferencias.devolverMuelle(id, motivo);
      setTransferencias(prev => prev.filter(t => t.id !== id));
      mostrarToast(`"${actualizada.title || "Transferencia"}" devuelta a Sector Pacífico.`, "exito");
      setModalDevolverId(null);
    } catch (e: any) {
      mostrarToast(e?.response?.data?.detail ?? "No se pudo devolver la transferencia.", "error");
    }
  }

  // ── UI helpers ────────────────────────────────────────────────────────────
  function toggleCard(token: string) {
    setExpandidos(prev => { const s = new Set(prev); if (s.has(token)) s.delete(token); else s.add(token); return s; });
  }
  function togglePuerto(k: string) {
    setPuertoAbiertos(prev => { const s = new Set(prev); if (s.has(k)) s.delete(k); else s.add(k); return s; });
  }
  function toggleNaviera(k: string) {
    setNavieraAbiertos(prev => { const s = new Set(prev); if (s.has(k)) s.delete(k); else s.add(k); return s; });
  }
  function toggleMarino(k: string) {
    setMarinoAbiertos(prev => { const s = new Set(prev); if (s.has(k)) s.delete(k); else s.add(k); return s; });
  }

  // ── Datos derivados ───────────────────────────────────────────────────────
  // Filtro por fecha de creación (client-side). Las stats de arriba siguen
  // reflejando el total global; el filtro solo afecta la lista/jerarquía.
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
  const busquedaNorm = busqueda.toLowerCase().trim();
  const activasFiltradas = busquedaNorm
    ? activas.filter(t =>
        (t.title || "").toLowerCase().includes(busquedaNorm) ||
        (t.naviera || "").toLowerCase().includes(busquedaNorm) ||
        (t.marino || "").toLowerCase().includes(busquedaNorm) ||
        (t.puerto?.nombre || "").toLowerCase().includes(busquedaNorm)
      )
    : activas;
  const { grupos, sinNaviera } = agrupar(activasFiltradas);

  const estadisticas = {
    total:          transferencias.length,
    activas:        activas.length,
    totalDescargas: transferencias.reduce((s, t) => s + t.downloads, 0),
  };

  // Modo por defecto para tarjetas en la vista jerárquica
  const modoJerarquia: Modo = puedeOperarMuelle && !esAdmin ? "muelle" : (esAdmin ? "sp" : "muelle");
  const modoNaviera:   Modo = "naviera";
  const modoSP:        Modo = "sp";

  // Subtítulo contextual
  const subtitulo = puedeOperarMuelle && !esAdmin
    ? "Transferencias en operación"
    : vistaColaSP
      ? "Cola de revisión"
      : "Mis transferencias";

  // Mensaje cuando muelle no tiene puertos asignados
  const muelleSinPuertos =
    puedeOperarMuelle && !esAdmin && !cargando && transferencias.length === 0
    && (usuario?.puertos_asignados?.length ?? 0) === 0;

  // Filtro por fecha: se muestra en vistas que suelen listar muchas (Admin,
  // Muelle, Sector Pacífico). No filtra la cola de revisión (siempre pequeña).
  const hayFiltroFecha     = rangoFecha.desde !== null || rangoFecha.hasta !== null;
  const mostrarFiltroFecha = (vistaJerarquica || vistaColaSP) && transferencias.length > 0;
  const sinResultadosFecha = hayFiltroFecha && activas.length === 0 && expiradas.length === 0;

  function cardBase(t: Transferencia, modo: Modo) {
    return {
      t, modo, copiado, eliminando, copiarEnlace, eliminarTransferencia,
      expanded: expandidos.has(t.token),
      onToggle: () => toggleCard(t.token),
      marcarProcesada: marcarProcesadaMuelle,
      devolverAlSP: (id: number, titulo: string | null) => setModalDevolverId({ id, titulo }),
      usuarioActualId: usuario?.id,
    };
  }

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
            <span>{subtitulo}</span>
          </h1>
          <div className={styles.topRowRight}>
            {(tiene("T-CREAR-BASICA") || esAdmin) && (
              <Link to="/new" className={styles.btnNew}>
                <IconoMas />
                Nueva transferencia
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
        ) : muelleSinPuertos ? (
          <div className={styles.empty}>
            <div className={styles.emptyIllustration}><IconoMuelle tamano={40} /></div>
            <h3>Sin puertos asignados</h3>
            <p>Aún no tienes puertos asignados a tu cuenta. Contacta al administrador para que te los asigne.</p>
          </div>
        ) : transferencias.length === 0 && cola.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIllustration}><IconoNube /></div>
            <h3>Sin transferencias aún</h3>
            <p>{vistaColaSP
              ? "No hay transferencias pendientes en la cola de revisión."
              : puedeOperarMuelle
                ? "No hay transferencias listas para operar en tus puertos."
                : esNavieraSola
                  ? "Sube tus primeros archivos para generar un enlace de descarga seguro."
                  : "No hay transferencias que mostrar."}</p>
            {(tiene("T-CREAR-BASICA") || esAdmin) && (
              <Link to="/new" className={styles.btnNew}>
                <IconoMas />
                Crear primera transferencia
              </Link>
            )}
          </div>
        ) : (
          <>
            {/* ── Filtro por fecha (Admin / Muelle / Sector Pacífico) ── */}
            {mostrarFiltroFecha && (
              <FiltroFechas valor={rangoFecha} onCambio={setRangoFecha} />
            )}

            {/* ── Cola de revisión (Sector Pacífico + Admin) ── */}
            {vistaColaSP && cola.length > 0 && (
              <div className={styles.colaSection}>
                <button
                  className={styles.colaToggle}
                  onClick={() => setColaAbierta(v => !v)}
                >
                  <div className={styles.colaIconWrap}><IconoBandeja /></div>
                  <div className={styles.colaTextos}>
                    <div className={styles.colaTitulo}>Cola de revisión</div>
                    <div className={styles.colaSub}>Borradores nuevos y devueltos por el Muelle</div>
                  </div>
                  <span className={styles.colaCount}>{cola.length}</span>
                  <span className={`${styles.colaChevron} ${colaAbierta ? styles.colaChevronOpen : ""}`}>›</span>
                </button>
                {colaAbierta && (
                  <div className={styles.colaList}>
                    {cola.slice(0, verTodaCola ? undefined : 5).map(t => (
                      <div key={t.id} className={styles.colaItem}>
                        <div className={styles.colaItemIcon}><IconoCarpeta tamano={18} /></div>
                        <div className={styles.colaItemMain}>
                          <div className={styles.colaItemTitle}>
                            {t.title || "Sin título"}
                            {t.status === "review" && (
                              <span className={styles.badgeReview} style={{ marginLeft: 8 }}>
                                Devuelto por Muelle
                              </span>
                            )}
                          </div>
                          <div className={styles.colaItemMeta}>
                            <span><IconoArchivo tamano={13} />{t.files.length} archivo{t.files.length !== 1 ? "s" : ""}</span>
                            <span><IconoPeso />{formatBytes(t.total_size)}</span>
                            {t.expires_at && <span><IconoReloj />{formatDate(t.expires_at)}</span>}
                            <span><IconoUsuario tamano={14} />{t.destinatario_original ? `Para: ${t.destinatario_original}` : "Sin destinatario"}</span>
                          </div>
                          {t.status === "review" && t.observaciones && (
                            <div className={styles.motivoBox} style={{ marginTop: 8 }}>
                              <span className={styles.motivoLabel}>Motivo del Muelle:</span>
                              <span className={styles.motivoTexto}>{t.observaciones}</span>
                            </div>
                          )}
                          {t.message && t.status !== "review" && <div className={styles.colaItemMsg}>&ldquo;{t.message}&rdquo;</div>}
                        </div>
                        <Link to={`/transfers/${t.id}/procesar`} className={styles.btnProcesar}>
                          {t.status === "review" ? "Revisar de nuevo" : "Abrir"}
                        </Link>
                      </div>
                    ))}
                    {cola.length > 5 && (
                      <button className={styles.verTodosBtn} onClick={() => setVerTodaCola(v => !v)}>
                        {verTodaCola ? "Mostrar menos" : `Ver todos (${cola.length})`}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {sinResultadosFecha && (
              <div className={styles.empty}>
                <div className={styles.emptyIllustration}><IconoReloj tamano={34} /></div>
                <h3>Sin transferencias en el rango</h3>
                <p>No hay transferencias creadas en las fechas seleccionadas. Ajusta o limpia el filtro de fecha.</p>
              </div>
            )}

            {/* ── Vista jerárquica Puerto → Naviera → Marino (Muelle + Admin) ── */}
            {vistaJerarquica && grupos.map(pg => {
              const puertoKey = String(pg.id ?? "null");
              const isPuertoOpen = puertoAbiertos.has(puertoKey);
              return (
                <div key={puertoKey} className={styles.puertoGroup}>
                  <div
                    className={styles.puertoHeader}
                    onClick={() => togglePuerto(puertoKey)}
                    role="button" tabIndex={0}
                    onKeyDown={e => e.key === "Enter" && togglePuerto(puertoKey)}
                  >
                    <div className={styles.puertoIconWrap}><IconoAncla /></div>
                    <div className={styles.puertoInfo}>
                      <div className={styles.puertoLabel}>Puerto / Muelle</div>
                      <div className={styles.puertoNombre}>{pg.nombre}</div>
                    </div>
                    <span className={styles.puertoCount}>{pg.navieras.reduce((s, n) => s + n.marinos.reduce((ms, m) => ms + m.items.length, 0), 0)}</span>
                    <span className={styles.headerChevron}><IconChevron open={isPuertoOpen} /></span>
                  </div>

                  {isPuertoOpen && pg.navieras.map(ng => {
                    const navieraKey = `${puertoKey}-${ng.nombre}`;
                    const isNavieraOpen = navieraAbiertos.has(navieraKey);
                    return (
                      <div key={navieraKey} className={styles.navieraGroup}>
                        <div
                          className={styles.navieraHeader}
                          onClick={() => toggleNaviera(navieraKey)}
                          role="button" tabIndex={0}
                          onKeyDown={e => e.key === "Enter" && toggleNaviera(navieraKey)}
                        >
                          <div className={styles.navieraInitials}>{ng.nombre[0]}</div>
                          <div className={styles.navieraInfo}>
                            <div className={styles.navieraLabel}>Naviera</div>
                            <div className={styles.navieraNombre}>{ng.nombre}</div>
                          </div>
                          <span className={styles.navieraCount}>{ng.marinos.reduce((s, m) => s + m.items.length, 0)}</span>
                          <span className={styles.headerChevron}><IconChevron open={isNavieraOpen} /></span>
                        </div>

                        {isNavieraOpen && ng.marinos.map(mg => {
                          const marinoKey = `${navieraKey}-${mg.nombre}`;
                          const isMarinoOpen = marinoAbiertos.has(marinoKey);
                          return (
                            <div key={marinoKey} className={styles.marinoGroup}>
                              <div
                                className={styles.marinoHeader}
                                onClick={() => toggleMarino(marinoKey)}
                                role="button" tabIndex={0}
                                onKeyDown={e => e.key === "Enter" && toggleMarino(marinoKey)}
                              >
                                <div className={styles.marinoAvatar}>{mg.nombre[0]}</div>
                                <div className={styles.marinoInfo}>
                                  <div className={styles.marinoLabel}>Marino / Motonave</div>
                                  <div className={styles.marinoNombre}>{mg.nombre}</div>
                                </div>
                                <span className={styles.marinoCount}>{mg.items.length}</span>
                                <span className={styles.headerChevron}><IconChevron open={isMarinoOpen} /></span>
                              </div>
                              {isMarinoOpen && (
                                <div className={styles.list}>
                                  {mg.items.map(t => <TransferCard key={t.token} {...cardBase(t, modoJerarquia)} />)}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              );
            })}

            {/* Sin naviera (solo en vista jerárquica) */}
            {vistaJerarquica && sinNaviera.length > 0 && (
              <div className={styles.list}>
                {sinNaviera.map(t => <TransferCard key={t.token} {...cardBase(t, modoJerarquia)} />)}
              </div>
            )}

            {/* ── Vista Naviera: lista simple de sus propias transferencias ── */}
            {!vistaJerarquica && esNavieraSola && activas.length > 0 && (
              <div className={styles.list}>
                {activas.map(t => (
                  <TransferCard key={t.token} {...cardBase(t, modoNaviera)} />
                ))}
              </div>
            )}

            {/* ── Vista Sector Pacífico (sin jerarquía): ya procesadas ── */}
            {!vistaJerarquica && !esNavieraSola && activas.length > 0 && (
              <div className={styles.colaSection}>
                <button
                  className={styles.colaToggle}
                  onClick={() => setProcesadasAbierta(v => !v)}
                >
                  <div className={styles.colaIconWrap}><IconoProcesada tamano={18} /></div>
                  <div className={styles.colaTextos}>
                    <div className={styles.colaTitulo}>Procesadas</div>
                    <div className={styles.colaSub}>Transferencias activas ya enviadas al destinatario</div>
                  </div>
                  <span className={styles.colaCount}>{activas.length}</span>
                  <span className={`${styles.colaChevron} ${procesadasAbierta ? styles.colaChevronOpen : ""}`}>›</span>
                </button>
                {procesadasAbierta && (
                  <div className={styles.colaList}>
                    {activas.map(t => (
                      <TransferCard key={t.token} {...cardBase(t, modoSP)} />
                    ))}
                  </div>
                )}
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

      {/* Modal para devolver al Sector Pacífico con motivo (Muelle) */}
      <ModalDevolucion
        abierto={modalDevolverId !== null}
        titulo="Devolver al Sector Pacífico"
        descripcion={modalDevolverId?.titulo
          ? `Se devolverá la transferencia "${modalDevolverId.titulo}" a la cola de revisión del Sector Pacífico.`
          : "Se devolverá la transferencia a la cola de revisión del Sector Pacífico."}
        placeholder="Ejemplo: la asignación de puerto no corresponde a la carga real…"
        textoOk="Devolver a SP"
        onCancelar={() => setModalDevolverId(null)}
        onConfirmar={motivo => {
          if (modalDevolverId) ejecutarDevolucionAlSP(modalDevolverId.id, motivo);
        }}
      />

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
