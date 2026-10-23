/**
 * Modal de previsualización de un documento del expediente.
 *
 * El archivo se pide con la sesión (`/solicitudes/{id}/documentos/{doc}`,
 * con la cabecera Authorization) y se muestra desde un blob local: no hay
 * enlaces públicos, y cada vista previa queda en la bitácora.
 *
 * - Imágenes y PDF se muestran inline (img / iframe sobre una URL blob:).
 * - Word (.docx) y Excel (.xlsx) se renderizan en el navegador con
 *   `docx-preview` / `exceljs` — sin subir el archivo a ningún servicio
 *   externo (el servidor es de red interna, no hay visores tipo Office Online).
 * - El Word lo sube una agencia (fuente no confiable): se muestra en un marco
 *   aislado, sin scripts ni acceso a la sesión, sin enlaces activos, sin el
 *   HTML que pueda traer incrustado (altChunk) y sin cargar nada externo.
 *   Sin esto, un enlace `javascript:` dentro del .docx corría en ARGO NAVIS al
 *   hacerle clic y podía robar la sesión de quien revisa.
 * - Lo que no se puede renderizar (.doc y .xls del formato binario viejo, o si
 *   el render falla) muestra un botón para descargar el archivo.
 */
import { useEffect, useState } from "react";
import { apiSolicitudes } from "../api/solicitudes";
import { infoTipo } from "../utils/tipoArchivo";
import { useAtraparFoco } from "../hooks/useAtraparFoco";
import { mensajeDeError } from "../utils/errores";
import { EstadoCarga } from "./EstadoCarga";
import { useNotificacion } from "./Notificaciones";
import { IconoX, IconoDescargar, IconoArchivo } from "./Iconos";
import styles from "./ModalPreview.module.css";

interface Props {
  solicitudId: number;
  documento:   { id: number; nombre_original: string; tipo_mime: string | null };
  onCerrar:    () => void;
}

interface Carga {
  url:      string | null;          // blob: para imagen / PDF
  html:     string | null;          // Word: documento ya aislado para el marco
  filas:    string[][] | null;      // hoja de cálculo
  truncado: boolean;
  fallo:    boolean;
}

const VACIA: Carga = { url: null, html: null, filas: null, truncado: false, fallo: false };

/** Política del marco del Word: nada de scripts, ni conexiones, ni recursos
 *  externos; solo los estilos e imágenes (data:) que trae el propio documento. */
const CSP_WORD = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:";

/** Documento HTML para el marco aislado, a partir de lo que armó docx-preview.
 *  Se quitan por si acaso elementos activos, manejadores on* y enlaces. */
function documentoAislado(estilos: HTMLElement, cuerpo: HTMLElement): string {
  for (const raiz of [estilos, cuerpo]) {
    raiz.querySelectorAll("script, iframe, frame, object, embed, link, meta, base, form").forEach((n) => n.remove());
    raiz.querySelectorAll("*").forEach((n) => {
      for (const { name } of [...n.attributes]) {
        if (name.toLowerCase().startsWith("on")) n.removeAttribute(name);
      }
    });
    raiz.querySelectorAll("a[href]").forEach((a) => a.removeAttribute("href"));
  }
  return `<!doctype html><html><head><meta charset="utf-8">`
    + `<meta http-equiv="Content-Security-Policy" content="${CSP_WORD}">`
    + `<style>body{margin:0;background:#e8e8e8}</style>${estilos.innerHTML}</head>`
    + `<body>${cuerpo.innerHTML}</body></html>`;
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

export function ModalPreview({ solicitudId, documento, onCerrar }: Props) {
  const refModal = useAtraparFoco(true);
  const { mostrar } = useNotificacion();
  const { categoria } = infoTipo(documento.tipo_mime, documento.nombre_original);
  const previsualizable = ["imagen", "pdf", "word", "excel"].includes(categoria);

  const [carga, setCarga] = useState<Carga | null>(null);
  const [descargando, setDescargando] = useState(false);
  const cargando = previsualizable && carga === null;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCerrar();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCerrar]);

  useEffect(() => {
    if (!previsualizable) return;
    let cancelado = false;
    let urlCreada: string | null = null;

    (async () => {
      try {
        const blob = await apiSolicitudes.obtenerDocumento(solicitudId, documento.id);
        if (cancelado) return;
        if (categoria === "imagen" || categoria === "pdf") {
          urlCreada = URL.createObjectURL(blob);
          setCarga({ ...VACIA, url: urlCreada });
        } else if (categoria === "word") {
          const { renderAsync } = await import("docx-preview");
          // Se arma fuera de la página y se pasa al marco aislado como HTML.
          const cuerpo = document.createElement("div");
          const estilos = document.createElement("div");
          await renderAsync(blob, cuerpo, estilos, {
            ignoreWidth: true, ignoreHeight: true, className: "docxDoc",
            useBase64URL: true,       // imágenes como data: (el marco no ve los blob: de la página)
            renderAltChunks: false,   // un altChunk es HTML del autor del documento: nunca se incrusta
          });
          if (!cancelado) setCarga({ ...VACIA, html: documentoAislado(estilos, cuerpo) });
        } else {
          const [{ default: ExcelJS }, buffer] = await Promise.all([import("exceljs"), blob.arrayBuffer()]);
          const libro = new ExcelJS.Workbook();
          await libro.xlsx.load(buffer);
          const hoja = libro.worksheets[0];
          if (!hoja) throw new Error("El libro no tiene hojas.");
          const valores = hoja.getSheetValues(); // sparse, índice 1-based
          const todasFilas = valores.slice(1).map(fila =>
            Array.isArray(fila) ? fila.slice(1).map(celdaTexto) : [],
          );
          if (!cancelado) {
            setCarga({
              ...VACIA, filas: todasFilas.slice(0, MAX_FILAS_EXCEL),
              truncado: todasFilas.length > MAX_FILAS_EXCEL,
            });
          }
        }
      } catch {
        if (!cancelado) setCarga({ ...VACIA, fallo: true });
      }
    })();

    return () => {
      cancelado = true;
      if (urlCreada) URL.revokeObjectURL(urlCreada);
    };
  }, [solicitudId, documento.id, categoria, previsualizable]);

  async function descargar() {
    setDescargando(true);
    try {
      await apiSolicitudes.descargarDocumento(solicitudId, documento);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar el documento."), "error");
    } finally {
      setDescargando(false);
    }
  }

  const fallo = carga?.fallo ?? false;
  const filas = carga?.filas ?? null;
  const colMax = filas ? Math.max(0, ...filas.map(f => f.length)) : 0;

  return (
    <div className={styles.backdrop} onClick={onCerrar}>
      <div
        ref={refModal}
        className={styles.box}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Previsualización de ${documento.nombre_original}`}
      >
        <div className={styles.header}>
          <span className={styles.titulo}>{documento.nombre_original}</span>
          <button className={styles.cerrar} onClick={descargar} disabled={descargando}
            aria-label="Descargar" title="Descargar">
            <IconoDescargar tamano={16} />
          </button>
          <button className={styles.cerrar} onClick={onCerrar} aria-label="Cerrar" data-focus-inicial>
            <IconoX tamano={16} />
          </button>
        </div>
        <div className={styles.body}>
          {!previsualizable || fallo ? (
            <div className={styles.fallback}>
              <div className={styles.fallbackIcono}><IconoArchivo tamano={30} /></div>
              <div className={styles.fallbackTexto}>
                El archivo <span className={styles.fallbackNombre}>{documento.nombre_original}</span> no
                se puede previsualizar en el navegador. Descárgalo para revisarlo.
              </div>
              <button type="button" className={styles.btnDescargar} onClick={descargar} disabled={descargando}>
                <IconoDescargar tamano={16} />
                {descargando ? "Descargando…" : "Descargar archivo"}
              </button>
            </div>
          ) : categoria === "word" ? (
            cargando ? <EstadoCarga texto="Cargando documento…" pagina /> : (
              // sandbox vacío: sin scripts, sin origen propio, sin formularios ni ventanas.
              <iframe sandbox="" srcDoc={carga?.html ?? ""} title={documento.nombre_original} className={styles.pdf} />
            )
          ) : cargando ? (
            <EstadoCarga texto="Cargando documento…" pagina />
          ) : categoria === "imagen" && carga?.url ? (
            <img src={carga.url} alt={documento.nombre_original} className={styles.img} />
          ) : categoria === "pdf" && carga?.url ? (
            <iframe src={carga.url} title={documento.nombre_original} className={styles.pdf} />
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
              {carga?.truncado && (
                <div className={styles.notaTruncado}>
                  Mostrando las primeras {MAX_FILAS_EXCEL} filas — descarga el archivo para verlo completo.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
