import { useState, useEffect } from "react";
import { apiAdmin, type UsoSistema } from "../../api/admin";
import { formatBytes } from "../../utils/format";
import { mensajeDeError } from "../../utils/errores";
import { MarcoPagina } from "../../components/MarcoPagina";
import BarraProgreso from "../../components/BarraProgreso";
import SeccionAutorizaciones from "./SeccionAutorizaciones";
import {
  IconoUsuario, IconoUsuarios, IconoGrafico, IconoArchivo, IconoDisco, IconoBarco, IconoTrofeo,
} from "../../components/Iconos";
import styles from "./PaginaEstadisticas.module.css";

export default function PaginaEstadisticas() {
  // Resultado único: "cargando" se deriva de que aún no hay respuesta.
  const [resultado, setResultado] = useState<{ uso: UsoSistema | null; error: string | null } | null>(null);

  useEffect(() => {
    let cancelado = false;
    apiAdmin.obtenerUso()
      .then((uso) => { if (!cancelado) setResultado({ uso, error: null }); })
      .catch((e) => {
        if (!cancelado) setResultado({ uso: null, error: mensajeDeError(e, "No se pudieron cargar las estadísticas.") });
      });
    return () => { cancelado = true; };
  }, []);

  const uso = resultado?.uso ?? null;
  const maxAgencia = uso ? Math.max(...uso.top_agencias.map(a => a.total), 1) : 1;
  // "2.50 KB" → cifra en grande y la unidad en la etiqueta (como las otras tarjetas).
  const [espacio, unidad] = uso ? formatBytes(uso.almacenamiento_bytes).split(" ") : ["0", "B"];

  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.container}>
        <div className={styles.pageTitle}>
          <span className={styles.titleIcon}><IconoGrafico tamano={22} /></span>
          <div>
            <h1>Estadísticas</h1>
            <p>Autorizaciones marítimas y uso general del sistema.</p>
          </div>
        </div>

        <SeccionAutorizaciones />

        <h2 className={styles.subtituloSeccion}>Uso del sistema</h2>

        {resultado?.error && <div className={styles.errorMsg}>{resultado.error}</div>}

        {!resultado ? (
          <div className={styles.loading}><span className={styles.spinner} /> Cargando estadísticas…</div>
        ) : uso && (
          <>
            <div className={styles.statGrid}>
              <div className={styles.statCard}>
                <div className={`${styles.statIcon} ${styles.gray}`}><IconoUsuarios /></div>
                <div className={styles.statNum}>{uso.usuarios}</div>
                <div className={styles.statLabel}>Usuarios registrados</div>
              </div>
              <div className={styles.statCard}>
                <div className={`${styles.statIcon} ${styles.green}`}><IconoUsuario /></div>
                <div className={styles.statNum}>{uso.usuarios_activos}</div>
                <div className={styles.statLabel}>Usuarios activos</div>
              </div>
              <div className={styles.statCard}>
                <div className={`${styles.statIcon} ${styles.blue}`}><IconoBarco tamano={22} /></div>
                <div className={styles.statNum}>{uso.agencias}</div>
                <div className={styles.statLabel}>Agencias navieras</div>
              </div>
              <div className={styles.statCard}>
                <div className={`${styles.statIcon} ${styles.yellow}`}><IconoArchivo /></div>
                <div className={styles.statNum}>{uso.documentos}</div>
                <div className={styles.statLabel}>Documentos en expedientes</div>
              </div>
              <div className={styles.statCard}>
                <div className={`${styles.statIcon} ${styles.purple}`}><IconoDisco /></div>
                <div className={styles.statNum}>{espacio}</div>
                <div className={styles.statLabel}>{unidad} almacenados</div>
              </div>
            </div>

            <div className={styles.panelesStack}>
              <section className={styles.panel}>
                <div className={styles.panelHeader}>
                  <IconoTrofeo />
                  Agencias con más solicitudes
                </div>
                <div className={styles.panelBody}>
                  {uso.top_agencias.length === 0 ? (
                    <p className={styles.empty}>Sin solicitudes aún.</p>
                  ) : (
                    <div className={styles.uploaderList}>
                      {uso.top_agencias.map((a, i) => (
                        <div key={a.agencia_id} className={styles.uploaderRow}>
                          <div className={`${styles.rankBadge} ${i === 0 ? styles.rankGold : i === 1 ? styles.rankSilver : i === 2 ? styles.rankBronze : ""}`}>
                            {i + 1}
                          </div>
                          <div className={styles.uploaderAvatar}>{(a.nombre[0] ?? "?").toUpperCase()}</div>
                          <div className={styles.uploaderInfo}>
                            <div className={styles.uploaderName}>{a.nombre}</div>
                            <div className={styles.uploaderBarWrap}>
                              <BarraProgreso valor={a.total} max={maxAgencia} color="gold" />
                            </div>
                          </div>
                          <div className={styles.uploaderCount}>
                            <span className={styles.uploaderNum}>{a.total}</span>
                            <span className={styles.uploaderLabel}>solicitud{a.total === 1 ? "" : "es"}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>
          </>
        )}
      </div>
    </MarcoPagina>
  );
}
