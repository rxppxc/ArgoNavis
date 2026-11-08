import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import SeccionAutorizaciones from "./estadisticas/SeccionAutorizaciones";
import SeccionUsoSistema from "./estadisticas/SeccionUsoSistema";
import styles from "./PaginaEstadisticas.module.css";

/** Estadísticas: las autorizaciones marítimas del periodo elegido y el uso del
 *  sistema. Cada sección carga lo suyo; los gráficos viven en `estadisticas/`. */
export default function PaginaEstadisticas() {
  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.container}>
        <EncabezadoPagina titulo="Estadísticas" descripcion="Autorizaciones marítimas y uso general del sistema." />
        <SeccionAutorizaciones />
        <SeccionUsoSistema />
      </div>
    </MarcoPagina>
  );
}
