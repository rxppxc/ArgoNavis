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
import { useEffect, useMemo, useState } from "react";
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
  /** null = los sectores que ve quien consulta (todos, o el suyo). */
  sectorId: number | null;
  onCambioSector: (id: number | null) => void;
}

export default function SeccionAutorizaciones({ rango, onCambioRango, unidad, onCambioUnidad, sectorId, onCambioSector }: Props) {
  // Lo pedido (periodo y sector) y, con las cifras, a qué pedido corresponden:
  // mientras llega uno nuevo, lo de pantalla sigue diciendo de qué es (atenuado).
  const consulta = useMemo(() => ({ rango, sectorId }), [rango, sectorId]);
  const [resultado, setResultado] = useState<{ datos: EstadisticasSolicitudes; consulta: typeof consulta } | null>(null);
  const [fallo, setFallo] = useState<{ consulta: typeof consulta; mensaje: string } | null>(null);

  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.estadisticas(consulta.rango.desde, consulta.rango.hasta, consulta.sectorId)
      .then((datos) => { if (!cancelado) { setResultado({ datos, consulta }); setFallo(null); } })
      .catch((e) => {
        if (!cancelado) setFallo({ consulta, mensaje: mensajeDeError(e, "No se pudieron cargar las estadísticas de autorizaciones.") });
      });
    return () => { cancelado = true; };
  }, [consulta]);

  const error = fallo?.consulta === consulta ? fallo.mensaje : null;
  const actualizando = resultado?.consulta !== consulta && !error;
  const sectores = resultado?.datos.sectores ?? [];

  return (
    <section className={styles.seccion} aria-labelledby="titulo-autorizaciones" aria-busy={actualizando}>
      <div className={styles.cabeceraSeccion}>
        <h2 id="titulo-autorizaciones">Autorizaciones marítimas</h2>
        {/* De qué sector son las cifras: un sector, el nombre; varios, para elegir. */}
        {sectores.length === 1 && <span className={styles.alcance}>{sectores[0].nombre}</span>}
        {sectores.length > 1 && (
          <div className={styles.chips} role="group" aria-label="Sector">
            {[{ id: null, nombre: "Todos" }, ...sectores].map((x) => (
              <button key={x.id ?? "todos"} type="button" className={styles.chip} aria-pressed={sectorId === x.id}
                onClick={() => onCambioSector(x.id)}>
                {x.nombre}
              </button>
            ))}
          </div>
        )}
      </div>
      <SelectorPeriodo valor={rango} onCambio={onCambioRango} />

      {error && <div className={styles.error} role="alert">{error}</div>}

      {!resultado ? (
        !error && <EstadoCarga texto="Cargando estadísticas…" />
      ) : (
        <div className={`${styles.contenido} ${actualizando ? styles.atenuado : ""}`}>
          <ResumenPeriodo datos={resultado.datos} rango={resultado.consulta.rango} />
          <div className={styles.grilla}>
            <GraficoTiempo datos={resultado.datos} rango={resultado.consulta.rango} unidad={unidad} onUnidad={onCambioUnidad} />
            <GraficoTramites tramites={resultado.datos.por_tipo} />
            <GraficoPuestos puestos={resultado.datos.por_puesto} />
            <MapaHoras datos={resultado.datos} />
          </div>
        </div>
      )}
    </section>
  );
}
