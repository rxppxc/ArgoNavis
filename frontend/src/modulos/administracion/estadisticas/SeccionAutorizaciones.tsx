/**
 * Estadísticas de Autorizaciones Marítimas (rediseño del 2026-11-02, pedido del
 * usuario: «más interesante, interactivo, que cualquiera lo entienda»).
 *
 * Forma elegida, de arriba abajo: la cifra que encabeza (recibidas) con lo que
 * pasó contado en palabras; la barra «¿En qué van?», que reparte el 100 % entre
 * los estados; cuatro cifras sueltas; columnas por día, mes o año (2026-11-06);
 * barras por trámite y por puesto; y el mapa de horas de las aprobaciones de
 * UCVMM con el horario laboral recuadrado. Cada gráfico tiene su tabla. El
 * periodo va arriba y acota todo.
 */
import { useEffect, useState } from "react";
import { apiSolicitudes, type EstadisticasSolicitudes } from "../../../api/solicitudes";
import { EstadoCarga } from "../../../components/EstadoCarga";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { mensajeDeError } from "../../../utils/errores";
import GraficoPuestos from "./GraficoPuestos";
import GraficoTiempo from "./GraficoTiempo";
import GraficoTramites from "./GraficoTramites";
import MapaHoras from "./MapaHoras";
import ResumenPeriodo from "./ResumenPeriodo";
import SelectorPeriodo from "./SelectorPeriodo";
import styles from "./Estadisticas.module.css";

export default function SeccionAutorizaciones() {
  const [rango, setRango] = useState<RangoFechas>({ desde: null, hasta: null });
  // Las cifras junto con el periodo al que corresponden: mientras llega uno nuevo,
  // lo de pantalla sigue diciendo de qué periodo es.
  const [resultado, setResultado] = useState<{ datos: EstadisticasSolicitudes; rango: RangoFechas } | null>(null);
  const [actualizando, setActualizando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    // Se conserva lo anterior (atenuado) mientras llega lo nuevo: sin saltos ni parpadeo.
    apiSolicitudes.estadisticas(rango.desde, rango.hasta)
      .then((datos) => { if (!cancelado) { setResultado({ datos, rango }); setError(null); } })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudieron cargar las estadísticas de autorizaciones.")); })
      .finally(() => { if (!cancelado) setActualizando(false); });
    return () => { cancelado = true; };
  }, [rango]);

  function cambiarRango(r: RangoFechas) {
    setActualizando(true);
    setRango(r);
  }

  return (
    <section className={styles.seccion} aria-labelledby="titulo-autorizaciones" aria-busy={actualizando}>
      <div className={styles.cabeceraSeccion}>
        <h2 id="titulo-autorizaciones">Autorizaciones marítimas</h2>
        <p>Las solicitudes que llegaron en el periodo y lo que pasó con ellas. Pasa el mouse (o el dedo) por los gráficos para ver el detalle.</p>
      </div>
      <SelectorPeriodo valor={rango} onCambio={cambiarRango} />

      {error && <div className={styles.error} role="alert">{error}</div>}

      {!resultado ? (
        !error && <EstadoCarga texto="Cargando estadísticas…" />
      ) : (
        <div className={`${styles.contenido} ${actualizando ? styles.atenuado : ""}`}>
          <ResumenPeriodo datos={resultado.datos} rango={resultado.rango} />
          <div className={styles.grilla}>
            <GraficoTiempo datos={resultado.datos} />
            <GraficoTramites tramites={resultado.datos.por_tipo} />
            <GraficoPuestos puestos={resultado.datos.por_puesto} />
            <MapaHoras datos={resultado.datos} />
          </div>
        </div>
      )}
    </section>
  );
}
