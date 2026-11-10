/**
 * Estadísticas de Autorizaciones Marítimas.
 *
 * Forma, de arriba abajo (revisión del 2026-11-10, pedido del usuario: «hay
 * mucho texto, siento que hasta enreda»): el periodo; la cifra que encabeza
 * (recibidas) junto al estado actual en una barra; cinco cifras sueltas; las
 * columnas por día, mes o año; las barras por trámite y por puesto; y el mapa
 * de horas de las aprobaciones de UCVMM. Sin párrafos: lo que antes se contaba
 * en frases está en las cifras, y el detalle de cada marca, en su globo y en
 * «Ver tabla». El periodo y la unidad los lleva la página (los usa también la
 * exportación).
 */
import { useEffect, useState } from "react";
import { apiSolicitudes, type EstadisticasSolicitudes } from "../../../api/solicitudes";
import { EstadoCarga } from "../../../components/EstadoCarga";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { mensajeDeError } from "../../../utils/errores";
import type { Unidad } from "./calculos";
import GraficoPuestos from "./GraficoPuestos";
import GraficoTiempo from "./GraficoTiempo";
import GraficoTramites from "./GraficoTramites";
import MapaHoras from "./MapaHoras";
import ResumenPeriodo from "./ResumenPeriodo";
import SelectorPeriodo from "./SelectorPeriodo";
import styles from "./Estadisticas.module.css";

interface Props {
  rango: RangoFechas;
  onCambioRango: (r: RangoFechas) => void;
  unidad: Unidad;
  onCambioUnidad: (u: Unidad) => void;
}

export default function SeccionAutorizaciones({ rango, onCambioRango, unidad, onCambioUnidad }: Props) {
  // Las cifras junto con el periodo al que corresponden: mientras llega uno nuevo,
  // lo de pantalla sigue diciendo de qué periodo es (atenuado, sin saltos).
  const [resultado, setResultado] = useState<{ datos: EstadisticasSolicitudes; rango: RangoFechas } | null>(null);
  const [fallo, setFallo] = useState<{ rango: RangoFechas; mensaje: string } | null>(null);

  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.estadisticas(rango.desde, rango.hasta)
      .then((datos) => { if (!cancelado) { setResultado({ datos, rango }); setFallo(null); } })
      .catch((e) => {
        if (!cancelado) setFallo({ rango, mensaje: mensajeDeError(e, "No se pudieron cargar las estadísticas de autorizaciones.") });
      });
    return () => { cancelado = true; };
  }, [rango]);

  const error = fallo?.rango === rango ? fallo.mensaje : null;
  const actualizando = resultado?.rango !== rango && !error;

  return (
    <section className={styles.seccion} aria-labelledby="titulo-autorizaciones" aria-busy={actualizando}>
      <div className={styles.cabeceraSeccion}>
        <h2 id="titulo-autorizaciones">Autorizaciones marítimas</h2>
      </div>
      <SelectorPeriodo valor={rango} onCambio={onCambioRango} />

      {error && <div className={styles.error} role="alert">{error}</div>}

      {!resultado ? (
        !error && <EstadoCarga texto="Cargando estadísticas…" />
      ) : (
        <div className={`${styles.contenido} ${actualizando ? styles.atenuado : ""}`}>
          <ResumenPeriodo datos={resultado.datos} rango={resultado.rango} />
          <div className={styles.grilla}>
            <GraficoTiempo datos={resultado.datos} rango={resultado.rango} unidad={unidad} onUnidad={onCambioUnidad} />
            <GraficoTramites tramites={resultado.datos.por_tipo} />
            <GraficoPuestos puestos={resultado.datos.por_puesto} />
            <MapaHoras datos={resultado.datos} />
          </div>
        </div>
      )}
    </section>
  );
}
