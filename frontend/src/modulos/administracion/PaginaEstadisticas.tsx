import { useState } from "react";
import { usePermisos } from "../../hooks/usePermisos";
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
 *  sistema, con la exportación a Excel, PDF y CSV (2026-11-10). El periodo, el
 *  sector y la unidad de la serie viven aquí: los usan los gráficos y la
 *  exportación. Los gráficos, en `estadisticas/`.
 *
 *  Sectores (2026-11-10): UCVMM y el supervisor de sector ven las de su sector;
 *  el Administrador y el supervisor general, las de los dos, y pueden elegir uno.
 *  El uso del sistema (totales de todo), solo ellos. */
export default function PaginaEstadisticas() {
  const { tiene, esAdmin } = usePermisos();
  const [rango, setRango] = useState<RangoFechas>(TODO);
  const [sectorId, setSectorId] = useState<number | null>(null);
  const [unidad, setUnidad] = useState<Unidad>(() => unidadSugerida(TODO, new Date()));
  const veUsoDelSistema = esAdmin || tiene("T-SUPERVISAR-TODO");

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
          descripcion={veUsoDelSistema ? "Autorizaciones marítimas y uso del sistema." : "Autorizaciones marítimas de tu sector."}
          acciones={<BotonesExportar rango={rango} unidad={unidad} sectorId={sectorId} />}
        />
        <SeccionAutorizaciones rango={rango} onCambioRango={cambiarRango} unidad={unidad} onCambioUnidad={setUnidad}
          sectorId={sectorId} onCambioSector={setSectorId} />
        {veUsoDelSistema && <SeccionUsoSistema />}
      </div>
    </MarcoPagina>
  );
}
