import { useState, useEffect, useCallback } from "react";
import { apiAdmin, type StatsAdmin } from "../../api/admin";
import { formatBytes } from "../../utils/format";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import BarraProgreso from "../../components/BarraProgreso";
import RankingBarras from "../../components/RankingBarras";
import {
  IconoUsuario, IconoGrafico, IconoActividad, IconoDescargar,
  IconoDisco, IconoAncla, IconoReloj, IconoTrofeo,
} from "../../components/Iconos";
import styles from "./PaginaEstadisticas.module.css";

export default function PaginaEstadisticas() {
  const [stats,    setStats]    = useState<StatsAdmin | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error,    setError]    = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const { data } = await apiAdmin.obtenerStats();
      setStats(data);
    } catch {
      setError("No se pudieron cargar las estadísticas.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

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
          <div className={styles.headerRight}>
            <MenuCabecera />
          </div>
        </div>
      </header>

      <main className={styles.body}>
        <div className={styles.container}>
          <div className={styles.pageTitle}>
            <span className={styles.titleIcon}><IconoGrafico tamano={22} /></span>
            <div>
              <h1>Estadísticas</h1>
              <p>Métricas globales de uso de FileDrop.</p>
            </div>
          </div>

          {error && <div className={styles.errorMsg}>{error}</div>}

          {cargando ? (
            <div className={styles.loading}><span className={styles.spinner} /> Cargando estadísticas…</div>
          ) : stats && (() => {
            const maxSubidores = Math.max(...stats.top_uploaders.map(u => u.total), 1);
            const puertosActivos = stats.puertos
              .map(p => ({ id: p.id, nombre: p.nombre, valor: p.total }))
              .sort((a, b) => b.valor - a.valor);

            return (
              <>
                {/* ── Métricas ── */}
                <div className={styles.statGrid}>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.yellow}`}><IconoGrafico /></div>
                    <div className={styles.statNum}>{stats.transferencias}</div>
                    <div className={styles.statLabel}>Transferencias totales</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.green}`}><IconoActividad tamano={22} /></div>
                    <div className={styles.statNum}>{stats.activas}</div>
                    <div className={styles.statLabel}>Activas</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.gray}`}><IconoReloj tamano={22} /></div>
                    <div className={styles.statNum}>{stats.expiradas}</div>
                    <div className={styles.statLabel}>Transferencias expiradas</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.blue}`}><IconoDescargar tamano={22} /></div>
                    <div className={styles.statNum}>{stats.total_descargas}</div>
                    <div className={styles.statLabel}>Descargas totales</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.purple}`}><IconoDisco /></div>
                    <div className={styles.statNum}>{formatBytes(stats.storage_bytes)}</div>
                    <div className={styles.statLabel}>Almacenamiento usado</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.orange}`}><IconoAncla tamano={16} /></div>
                    <div className={styles.statNum}>{stats.puertos.length}</div>
                    <div className={styles.statLabel}>Puertos</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={`${styles.statIcon} ${styles.gray}`}><IconoUsuario /></div>
                    <div className={styles.statNum}>{stats.usuarios}</div>
                    <div className={styles.statLabel}>Usuarios registrados</div>
                  </div>
                </div>

                <div className={styles.panelesStack}>
                  {/* ── Top subidores ── */}
                  <section className={styles.panel}>
                    <div className={styles.panelHeader}>
                      <IconoTrofeo />
                      Top subidores
                    </div>
                    <div className={styles.panelBody}>
                      {stats.top_uploaders.length === 0 ? (
                        <p className={styles.empty}>Sin datos aún.</p>
                      ) : (
                        <div className={styles.uploaderList}>
                          {stats.top_uploaders.map((u, i) => (
                            <div key={u.id} className={styles.uploaderRow}>
                              <div className={`${styles.rankBadge} ${i === 0 ? styles.rankGold : i === 1 ? styles.rankSilver : i === 2 ? styles.rankBronze : ""}`}>
                                {i + 1}
                              </div>
                              <div className={styles.uploaderAvatar}>
                                {(u.full_name?.[0] ?? "?").toUpperCase()}
                              </div>
                              <div className={styles.uploaderInfo}>
                                <div className={styles.uploaderName}>{u.full_name}</div>
                                <div className={styles.uploaderBarWrap}>
                                  <BarraProgreso valor={u.total} max={maxSubidores} color="gold" />
                                </div>
                              </div>
                              <div className={styles.uploaderCount}>
                                <span className={styles.uploaderNum}>{u.total}</span>
                                <span className={styles.uploaderLabel}>transfer{u.total !== 1 ? "encias" : "encia"}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </section>

                  {/* ── Puertos más activos ── */}
                  <section className={styles.panel}>
                    <div className={styles.panelHeader}>
                      <IconoAncla />
                      Puertos más activos
                    </div>
                    <div className={styles.panelBody}>
                      {puertosActivos.length === 0 ? (
                        <p className={styles.empty}>Sin datos aún.</p>
                      ) : (
                        <RankingBarras items={puertosActivos} color="blue" sufijo="" />
                      )}
                    </div>
                  </section>
                </div>
              </>
            );
          })()}
        </div>
      </main>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
