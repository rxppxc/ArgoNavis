import { useState, useEffect } from "react";
import { apiAdmin, type UsoSistema } from "../../api/admin";
import { formatBytes } from "../../utils/format";
import { mensajeDeError } from "../../utils/errores";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { EstadoCarga } from "../../components/EstadoCarga";
import BarraProgreso from "../../components/BarraProgreso";
import SeccionAutorizaciones from "./SeccionAutorizaciones";
import {
  IconoUsuario, IconoUsuarios, IconoArchivo, IconoDisco, IconoBarco, IconoTrofeo,
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
  // Misma forma que los indicadores de autorizaciones: ícono, etiqueta y cifra.
  const tarjetas = uso ? [
    { icono: <IconoUsuarios />, etiqueta: "Usuarios registrados", valor: uso.usuarios.toLocaleString("es-PA") },
    { icono: <IconoUsuario />, etiqueta: "Usuarios activos", valor: uso.usuarios_activos.toLocaleString("es-PA") },
    { icono: <IconoBarco tamano={20} />, etiqueta: "Agencias navieras", valor: uso.agencias.toLocaleString("es-PA") },
    { icono: <IconoArchivo />, etiqueta: "Documentos en expedientes", valor: uso.documentos.toLocaleString("es-PA") },
    { icono: <IconoDisco />, etiqueta: "Almacenamiento usado", valor: formatBytes(uso.almacenamiento_bytes) },
  ] : [];

  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.container}>
        <EncabezadoPagina titulo="Estadísticas" descripcion="Autorizaciones marítimas y uso general del sistema." />

        <SeccionAutorizaciones />

        <h2 className={styles.subtituloSeccion}>Uso del sistema</h2>

        {resultado?.error && <div className={styles.errorMsg} role="alert">{resultado.error}</div>}

        {!resultado ? (
          <EstadoCarga texto="Cargando el uso del sistema…" />
        ) : uso && (
          <>
            <div className={styles.statGrid}>
              {tarjetas.map((t) => (
                <div key={t.etiqueta} className={styles.statCard}>
                  <span className={styles.statIcon}>{t.icono}</span>
                  <span className={styles.statLabel}>{t.etiqueta}</span>
                  <span className={styles.statNum}>{t.valor}</span>
                </div>
              ))}
            </div>

            <div className={styles.panelesStack}>
              <section className={styles.panel}>
                <h3 className={styles.panelHeader}>
                  <IconoTrofeo />
                  Agencias con más solicitudes
                </h3>
                <div className={styles.panelBody}>
                  {uso.top_agencias.length === 0 ? (
                    <p className={styles.empty}>Sin solicitudes aún.</p>
                  ) : (
                    <div className={styles.uploaderList}>
                      {uso.top_agencias.map((a, i) => (
                        <div key={a.agencia_id} className={styles.uploaderRow}>
                          <div className={styles.rankBadge}>{i + 1}</div>
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
