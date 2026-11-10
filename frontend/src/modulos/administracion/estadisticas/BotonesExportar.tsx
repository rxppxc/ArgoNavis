import { useState } from "react";
import { apiSolicitudes, type FormatoExportacion } from "../../../api/solicitudes";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { IconoDescargar } from "../../../components/Iconos";
import { useNotificacion } from "../../../components/Notificaciones";
import { mensajeDeError } from "../../../utils/errores";
import type { Unidad } from "./calculos";
import styles from "./Estadisticas.module.css";

const FORMATOS: { id: FormatoExportacion; etiqueta: string; descripcion: string }[] = [
  { id: "xlsx", etiqueta: "Excel", descripcion: "Una hoja por tabla, con sus gráficos" },
  { id: "pdf",  etiqueta: "PDF",   descripcion: "Informe listo para imprimir o enviar" },
  { id: "csv",  etiqueta: "CSV",   descripcion: "Solo los datos, para otras herramientas" },
];

/** Exportar las estadísticas del periodo elegido (y el uso del sistema) con la
 *  identidad del SNM: los archivos los arma el servidor (core/informe_*.py). La
 *  serie va en la unidad que se ve en pantalla. Azul de contorno: descargar es
 *  consultar (Botones.module.css). */
export default function BotonesExportar({ rango, unidad, sectorId }: { rango: RangoFechas; unidad: Unidad; sectorId: number | null }) {
  const { mostrar } = useNotificacion();
  const [generando, setGenerando] = useState<FormatoExportacion | null>(null);

  async function exportar(formato: FormatoExportacion) {
    setGenerando(formato);
    try {
      const nombre = await apiSolicitudes.exportarEstadisticas(formato, rango.desde, rango.hasta, unidad, sectorId);
      mostrar(`Se descargó «${nombre}».`, "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudieron exportar las estadísticas."), "error");
    } finally {
      setGenerando(null);
    }
  }

  return (
    <div className={styles.exportar} role="group" aria-label="Exportar las estadísticas del periodo">
      <span className={styles.exportarEtiqueta}><IconoDescargar tamano={15} />Exportar</span>
      {FORMATOS.map((f) => (
        <button
          key={f.id}
          type="button"
          className={styles.botonExportar}
          title={f.descripcion}
          aria-busy={generando === f.id}
          // Uno a la vez: mientras se arma un archivo, los otros esperan.
          disabled={generando !== null}
          onClick={() => exportar(f.id)}
        >
          {generando === f.id ? "Generando…" : f.etiqueta}
        </button>
      ))}
    </div>
  );
}
