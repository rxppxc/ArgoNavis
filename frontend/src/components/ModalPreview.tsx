/**
 * Modal de previsualización de un archivo de una transferencia.
 *
 * - Imágenes y PDF se muestran inline (img / iframe) contra el endpoint
 *   público `/transfers/preview/{token}/{fileId}`.
 * - Word (.docx) y Excel (.xlsx/.xls) se renderizan inline en el navegador
 *   con `docx-preview` / `exceljs` — sin subir el archivo a ningún servicio
 *   externo (el servidor es de red interna, no hay forma de usar visores
 *   tipo Office Online).
 * - Lo que no se puede renderizar (.doc legado, ppt, zip, etc., o si el
 *   render falla) muestra un fallback con botón para abrir/descargar ese
 *   archivo individual — sin obligar a bajar el ZIP completo.
 */
import { useEffect, useRef, useState } from "react";
import { apiTransferencias } from "../api/transfers";
import { infoTipo } from "../utils/tipoArchivo";
import { useAtraparFoco } from "../hooks/useAtraparFoco";
import { IconoX, IconoDescargar, IconoArchivo } from "./Iconos";
import styles from "./ModalPreview.module.css";

interface Props {
  token:    string;
  archivo:  { id: number; original_name: string; mime_type: string | null };
  onCerrar: () => void;
}

const MAX_FILAS_EXCEL = 300;

// Las celdas de exceljs pueden traer string, número, fecha, fórmula
// ({result}) o texto enriquecido ({richText}) — nunca HTML, así que se
// vuelca como texto plano y React lo escapa solo al renderizarlo.
function celdaTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  if (valor instanceof Date) return valor.toLocaleDateString();
  if (typeof valor === "object") {
    const v = valor as { result?: unknown; text?: unknown; richText?: { text?: string }[] };
    if (Array.isArray(v.richText)) return v.richText.map(r => r.text ?? "").join("");
    if (v.result !== undefined) return celdaTexto(v.result);
    if (v.text !== undefined) return celdaTexto(v.text);
    return "";
  }
  return String(valor);
}

export function ModalPreview({ token, archivo, onCerrar }: Props) {
  const refModal = useAtraparFoco(true);
  const refDocx  = useRef<HTMLDivElement>(null);
  const { categoria } = infoTipo(archivo.mime_type, archivo.original_name);
  const url = apiTransferencias.urlPreview(token, archivo.id);

  const necesitaRender = categoria === "word" || categoria === "excel";
  const [cargando, setCargando] = useState(necesitaRender);
  const [fallo,    setFallo]    = useState(false);
  const [filas,    setFilas]    = useState<string[][] | null>(null);
  const [truncado, setTruncado] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCerrar();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCerrar]);

  useEffect(() => {
    if (!necesitaRender) return;
    let cancelado = false;

    async function render() {
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error("No se pudo descargar el archivo.");

        if (categoria === "word") {
          const [{ renderAsync }, blob] = await Promise.all([import("docx-preview"), resp.blob()]);
          if (cancelado || !refDocx.current) return;
          await renderAsync(blob, refDocx.current, undefined, {
            ignoreWidth: true, ignoreHeight: true, className: "docxDoc",
          });
        } else {
          const [{ default: ExcelJS }, buffer] = await Promise.all([import("exceljs"), resp.arrayBuffer()]);
          const libro = new ExcelJS.Workbook();
          await libro.xlsx.load(buffer);
          const hoja = libro.worksheets[0];
          if (!hoja) throw new Error("El libro no tiene hojas.");
          const valores = hoja.getSheetValues(); // sparse, índice 1-based
          const todasFilas = valores.slice(1).map(fila =>
            Array.isArray(fila) ? fila.slice(1).map(celdaTexto) : [],
          );
          if (cancelado) return;
          setTruncado(todasFilas.length > MAX_FILAS_EXCEL);
          setFilas(todasFilas.slice(0, MAX_FILAS_EXCEL));
        }
      } catch {
        if (!cancelado) setFallo(true);
      } finally {
        if (!cancelado) setCargando(false);
      }
    }

    render();
    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoria, url]);

  const colMax = filas ? Math.max(0, ...filas.map(f => f.length)) : 0;

  return (
    <div className={styles.backdrop} onClick={onCerrar}>
      <div
        ref={refModal}
        className={styles.box}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Previsualización de ${archivo.original_name}`}
      >
        <div className={styles.header}>
          <span className={styles.titulo}>{archivo.original_name}</span>
          <button className={styles.cerrar} onClick={onCerrar} aria-label="Cerrar" data-focus-inicial>
            <IconoX tamano={16} />
          </button>
        </div>
        <div className={styles.body}>
          {categoria === "imagen" ? (
            <img src={url} alt={archivo.original_name} className={styles.img} />
          ) : categoria === "pdf" ? (
            <iframe src={url} title={archivo.original_name} className={styles.pdf} />
          ) : categoria === "word" && !fallo ? (
            <div className={styles.officeWrap}>
              {cargando && <div className={styles.cargando}>Cargando documento…</div>}
              <div ref={refDocx} className={styles.docxWrap} />
            </div>
          ) : categoria === "excel" && !fallo ? (
            cargando ? (
              <div className={styles.cargando}>Cargando hoja de cálculo…</div>
            ) : (
              <div className={styles.officeWrap}>
                <table className={styles.tablaExcel}>
                  <tbody>
                    {filas?.map((fila, i) => (
                      <tr key={i}>
                        {Array.from({ length: colMax }, (_, j) => (
                          <td key={j}>{fila[j] ?? ""}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {truncado && (
                  <div className={styles.notaTruncado}>
                    Mostrando las primeras {MAX_FILAS_EXCEL} filas — descargá el archivo para verlo completo.
                  </div>
                )}
              </div>
            )
          ) : (
            <div className={styles.fallback}>
              <div className={styles.fallbackIcono}><IconoArchivo tamano={30} /></div>
              <div className={styles.fallbackTexto}>
                El archivo <span className={styles.fallbackNombre}>{archivo.original_name}</span> no
                se puede previsualizar en el navegador. Ábrelo o descárgalo para revisarlo.
              </div>
              <a className={styles.btnDescargar} href={url} target="_blank" rel="noopener noreferrer">
                <IconoDescargar tamano={16} />
                Abrir archivo
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
