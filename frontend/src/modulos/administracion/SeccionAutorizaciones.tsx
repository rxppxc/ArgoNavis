/**
 * Estadísticas de Autorizaciones Marítimas: aprobadas, denegadas y expiradas.
 *
 * Forma elegida: totales como fila de indicadores (no hace falta gráfico) y
 * desgloses como tablas — son muchas clases (hasta 18 trámites) — con una
 * barra de magnitud de un solo tono en la columna principal. El filtro de
 * fechas va arriba y acota todo lo que hay debajo, incluida la serie mensual.
 */
import { useEffect, useState } from "react";
import { apiSolicitudes, type EstadisticasSolicitudes } from "../../api/solicitudes";
import BarraProgreso from "../../components/BarraProgreso";
import FiltroFechas, { type RangoFechas } from "../../components/FiltroFechas";
import {
  IconoActividad, IconoExito, IconoProcesada, IconoReloj, IconoXCirculo, IconoBandeja,
} from "../../components/Iconos";
import { mensajeDeError } from "../../utils/errores";
import styles from "./SeccionAutorizaciones.module.css";

function nombreMes(mes: string): string {
  const [anio, numero] = mes.split("-").map(Number);
  return new Date(anio, numero - 1, 1).toLocaleDateString("es-PA", { month: "short", year: "numeric" });
}

function duracion(horas: number | null): string {
  if (horas === null) return "—";
  if (horas < 48) return `${horas.toLocaleString("es-PA", { maximumFractionDigits: 1 })} h`;
  return `${(horas / 24).toLocaleString("es-PA", { maximumFractionDigits: 1 })} días`;
}

export default function SeccionAutorizaciones() {
  const [rango, setRango] = useState<RangoFechas>({ desde: null, hasta: null });
  const [datos, setDatos] = useState<EstadisticasSolicitudes | null>(null);
  const [actualizando, setActualizando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    // Se conserva el render anterior (atenuado) mientras llega el nuevo: sin saltos.
    apiSolicitudes.estadisticas(rango.desde, rango.hasta)
      .then((d) => { if (!cancelado) { setDatos(d); setError(null); } })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudieron cargar las estadísticas de autorizaciones.")); })
      .finally(() => { if (!cancelado) setActualizando(false); });
    return () => { cancelado = true; };
  }, [rango]);

  function cambiarRango(r: RangoFechas) {
    setActualizando(true);
    setRango(r);
  }

  const maxTipo   = Math.max(1, ...(datos?.por_tipo.map((f) => f.recibidas) ?? [0]));
  const maxMes    = Math.max(1, ...(datos?.por_mes.map((f) => f.recibidas) ?? [0]));
  const maxPuesto = Math.max(1, ...(datos?.por_puesto.map((f) => f.aprobadas) ?? [0]));
  const porEstado = datos?.por_estado ?? {};

  return (
    <section className={styles.seccion} aria-busy={actualizando}>
      <div className={styles.cabecera}>
        <div>
          <h2>Autorizaciones marítimas</h2>
          <p>Solicitudes recibidas en el periodo y lo que pasó con ellas.</p>
        </div>
        <FiltroFechas valor={rango} onCambio={cambiarRango} />
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!datos ? (
        !error && <div className={styles.cargando}>Cargando estadísticas…</div>
      ) : (
        <div className={actualizando ? styles.atenuado : undefined}>
          <div className={styles.indicadores}>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.neutro}`}><IconoBandeja tamano={18} /></span>
              <span className={styles.etiqueta}>Recibidas</span>
              <span className={styles.valor}>{datos.recibidas.toLocaleString("es-PA")}</span>
            </div>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.bien}`}><IconoExito tamano={18} /></span>
              <span className={styles.etiqueta}>Aprobadas</span>
              <span className={styles.valor}>{datos.aprobadas.toLocaleString("es-PA")}</span>
            </div>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.critico}`}><IconoXCirculo tamano={18} /></span>
              <span className={styles.etiqueta}>Denegadas</span>
              <span className={styles.valor}>{datos.negadas.toLocaleString("es-PA")}</span>
            </div>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.aviso}`}><IconoReloj tamano={18} /></span>
              <span className={styles.etiqueta}>Expiradas</span>
              <span className={styles.valor}>{datos.expiradas.toLocaleString("es-PA")}</span>
            </div>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.neutro}`}><IconoProcesada tamano={18} /></span>
              <span className={styles.etiqueta}>Finalizadas en puerto</span>
              <span className={styles.valor}>{datos.finalizadas.toLocaleString("es-PA")}</span>
            </div>
            <div className={styles.indicador}>
              <span className={`${styles.icono} ${styles.neutro}`}><IconoActividad tamano={18} /></span>
              <span className={styles.etiqueta}>Tiempo medio de resolución</span>
              <span className={styles.valor}>{duracion(datos.horas_promedio_resolucion)}</span>
            </div>
          </div>

          <div className={styles.estadoActual}>
            <span>Estado actual:</span>
            <span><strong>{porEstado.review ?? 0}</strong> en revisión</span>
            <span><strong>{porEstado.returned ?? 0}</strong> en corrección</span>
            <span><strong>{porEstado.approved ?? 0}</strong> pendientes de finalizar</span>
          </div>

          <div className={styles.paneles}>
            <div className={`${styles.panel} ${styles.panelAncho}`}>
              <h3>Por tipo de trámite</h3>
              {datos.por_tipo.length === 0 ? <p className={styles.vacio}>Sin solicitudes en el periodo.</p> : (
                <table className={styles.tabla}>
                  <thead>
                    <tr><th>Trámite</th><th className={styles.columnaBarra}>Recibidas</th><th>Aprobadas</th><th>Denegadas</th><th>Expiradas</th></tr>
                  </thead>
                  <tbody>
                    {datos.por_tipo.map((f) => (
                      <tr key={f.codigo}>
                        <td>{f.nombre}</td>
                        <td className={styles.columnaBarra}>
                          <div className={styles.barraCelda}>
                            <BarraProgreso valor={f.recibidas} max={maxTipo} color="gold" />
                            <span className={styles.numero}>{f.recibidas}</span>
                          </div>
                        </td>
                        <td className={styles.numero}>{f.aprobadas}</td>
                        <td className={styles.numero}>{f.negadas}</td>
                        <td className={styles.numero}>{f.expiradas}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className={styles.panel}>
              <h3>Últimos 6 meses</h3>
              <table className={styles.tabla}>
                <thead>
                  <tr><th>Mes</th><th className={styles.columnaBarra}>Recibidas</th><th>Aprobadas</th><th>Denegadas</th><th>Expiradas</th></tr>
                </thead>
                <tbody>
                  {datos.por_mes.map((f) => (
                    <tr key={f.mes}>
                      <td className={styles.mes}>{nombreMes(f.mes)}</td>
                      <td className={styles.columnaBarra}>
                        <div className={styles.barraCelda}>
                          <BarraProgreso valor={f.recibidas} max={maxMes} color="gold" />
                          <span className={styles.numero}>{f.recibidas}</span>
                        </div>
                      </td>
                      <td className={styles.numero}>{f.aprobadas}</td>
                      <td className={styles.numero}>{f.negadas}</td>
                      <td className={styles.numero}>{f.expiradas}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.panel}>
              <h3>Por puesto de control</h3>
              {datos.por_puesto.length === 0 ? <p className={styles.vacio}>Sin autorizaciones aprobadas en el periodo.</p> : (
                <table className={styles.tabla}>
                  <thead>
                    <tr><th>Puesto</th><th className={styles.columnaBarra}>Aprobadas</th><th>Finalizadas</th><th>Expiradas</th></tr>
                  </thead>
                  <tbody>
                    {datos.por_puesto.map((f) => (
                      <tr key={f.puesto}>
                        <td>{f.puesto}</td>
                        <td className={styles.columnaBarra}>
                          <div className={styles.barraCelda}>
                            <BarraProgreso valor={f.aprobadas} max={maxPuesto} color="gold" />
                            <span className={styles.numero}>{f.aprobadas}</span>
                          </div>
                        </td>
                        <td className={styles.numero}>{f.finalizadas}</td>
                        <td className={styles.numero}>{f.expiradas}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
