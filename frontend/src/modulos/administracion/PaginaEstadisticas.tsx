import { useState } from "react";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import type { RangoFechas } from "../../components/FiltroFechas";
import BotonesExportar from "./estadisticas/BotonesExportar";
import { unidadSugerida, type Unidad } from "./estadisticas/calculos";
import SeccionAutorizaciones from "./estadisticas/SeccionAutorizaciones";
import SeccionUsoSistema from "./estadisticas/SeccionUsoSistema";
import styles from "./PaginaEstadisticas.module.css";

const TODO: RangoFechas = { desde: null, hasta: null };

/** Estadísticas: las autorizaciones marítimas del periodo elegido y el uso del
 *  sistema, con la exportación a Excel, PDF y CSV (2026-11-10). El periodo y la
 *  unidad de la serie viven aquí: los usan los gráficos y la exportación. Los
 *  gráficos, en `estadisticas/`. */
export default function PaginaEstadisticas() {
  const [rango, setRango] = useState<RangoFechas>(TODO);
  const [unidad, setUnidad] = useState<Unidad>(() => unidadSugerida(TODO, new Date()));

  function cambiarRango(nuevo: RangoFechas) {
    setRango(nuevo);
    // Otro periodo, otra escala: «Mes pasado» se ve por día; «Este año», por mes.
    setUnidad(unidadSugerida(nuevo, new Date()));
  }

  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.container}>
        <EncabezadoPagina
          titulo="Estadísticas"
          descripcion="Autorizaciones marítimas y uso del sistema."
          acciones={<BotonesExportar rango={rango} unidad={unidad} />}
        />
        <SeccionAutorizaciones rango={rango} onCambioRango={cambiarRango} unidad={unidad} onCambioUnidad={setUnidad} />
        <SeccionUsoSistema />
      </div>
    </MarcoPagina>
  );
}
