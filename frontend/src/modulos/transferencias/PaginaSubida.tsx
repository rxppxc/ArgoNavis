import { useState, useRef } from "react";
import type * as React from "react";
import { useNavigate } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import { formatBytes } from "../../utils/format";
import { TIPOS_ACEPTADOS, validarArchivos } from "../../utils/archivos";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import { usePermisos } from "../../hooks/usePermisos";
import {
  IconoSubir, IconoArchivo, IconoX, IconoAlerta, IconoEnviar, IconoAjustes,
} from "../../components/Iconos";
import styles from "./PaginaSubida.module.css";


export default function PaginaSubida() {
  const navegar = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const { tiene, esAdmin } = usePermisos();
  const puedeSubir = esAdmin || tiene("T-CREAR-BASICA");

  const [archivos,     setArchivos]     = useState<File[]>([]);
  const [arrastrando,  setArrastrando]  = useState(false);
  const [titulo,       setTitulo]       = useState("");
  const [mensaje,      setMensaje]      = useState("");
  const [destinatario, setDestinatario] = useState("");
  const [enviando,     setEnviando]     = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  function agregarArchivos(lista: FileList | null) {
    if (!lista) return;
    const nuevos = Array.from(lista);

    // Se valida en ambos modos: el atributo `accept` del input no cubre el
    // arrastrar-y-soltar, y el tamaño nunca lo filtra el navegador.
    const errorValidacion = validarArchivos(nuevos);
    if (errorValidacion) {
      setError(errorValidacion);
      return;
    }

    setError(null);
    setArchivos((prev) => {
      const existentes = new Set(prev.map((a) => a.name + a.size));
      return [...prev, ...nuevos.filter((a) => !existentes.has(a.name + a.size))];
    });
  }

  function onSoltar(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastrando(false);
    agregarArchivos(e.dataTransfer.files);
  }

  async function alEnviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!archivos.length) return;
    if (!mensaje.trim()) {
      setError("Debes ingresar un mensaje.");
      return;
    }
    setError(null);
    setEnviando(true);
    try {
      const fd = new FormData();
      archivos.forEach((a) => fd.append("files", a));
      fd.append("title", titulo);
      fd.append("message", mensaje);
      if (destinatario.trim()) fd.append("recipient", destinatario.trim());
      const transferencia = await apiTransferencias.crear(fd);
      navegar(`/t/${transferencia.token}?new=1`);
    } catch (err: any) {
      const detalle = err?.response?.data?.detail;
      setError(
        typeof detalle === "string"
          ? detalle
          : Array.isArray(detalle)
            ? detalle.map((d: any) => d.msg).join(" · ")
            : "Error al crear la transferencia. Inténtalo de nuevo.",
      );
    } finally {
      setEnviando(false);
    }
  }

  // Sin permiso: bloquea acceso
  if (!puedeSubir) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.headerInner}>
            <BotonVolver to="/dashboard" />
            <div className={styles.brand}>
              <img src="/images/logo-snm.png" alt="SNM" />
              <div className={styles.brandText}>
                <div className={styles.org}>Servicio Nacional de Migración</div>
                <div className={styles.app}>FileDrop - SNM</div>
              </div>
            </div>
            <div className={styles.headerRight}>
              <MenuCabecera />
            </div>
          </div>
        </header>
        <main className={styles.main}>
          <div className={styles.error}>
            <IconoAlerta />
            No tienes permiso para subir archivos. Contacta al administrador.
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <BotonVolver to="/dashboard" />
          <div className={styles.brand}>
            <img src="/images/logo-snm.png" alt="SNM" />
            <div className={styles.brandText}>
              <div className={styles.org}>Servicio Nacional de Migración</div>
              <div className={styles.app}>FileDrop - SNM</div>
            </div>
          </div>
          <div className={styles.headerRight}>
            <MenuCabecera />
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.pageHead}>
          <h1 className={styles.pageTitle}>Subir archivos</h1>
          <p className={styles.pageSub}>
            Adjunte los documentos y complete los datos del envío. Quedarán disponibles de
            inmediato con un enlace para que el Sector Pacífico los descargue.
          </p>
        </div>

        {error && (
          <div className={styles.error}>
            <IconoAlerta />
            {error}
          </div>
        )}

        <form onSubmit={alEnviar}>
          <div className={styles.grid}>
            {/* Archivos */}
            <div className={styles.panel}>
              <div className={styles.panelHead}>
                <IconoArchivo tamano={16} />
                <h2>Archivos {archivos.length > 0 && `(${archivos.length})`}</h2>
                <span className={styles.reqBadge}>Obligatorio</span>
              </div>
              <p className={styles.panelHint}><strong>Obligatorio.</strong> Adjunte los documentos en PDF, Word, Excel o imágenes. Máximo 50 MB por archivo.</p>
              <div className={styles.panelBody}>
                <div
                  className={`${styles.dropZone} ${arrastrando ? styles.dragging : ""}`}
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
                  onDragLeave={() => setArrastrando(false)}
                  onDrop={onSoltar}
                >
                  <div className={styles.dropIconWrap}><IconoSubir tamano={22} /></div>
                  <p className={styles.dropTitle}>Arrastra archivos aquí o <strong>haz clic</strong></p>
                  <p className={styles.dropHint}>Máx. 50 MB por archivo</p>
                  <input
                    ref={inputRef}
                    type="file"
                    multiple
                    hidden
                    accept={TIPOS_ACEPTADOS}
                    onChange={(e) => agregarArchivos(e.target.files)}
                  />
                </div>

                {archivos.length > 0 && (
                  <ul className={styles.fileList}>
                    {archivos.map((a, i) => (
                      <li key={i} className={styles.fileItem}>
                        <span className={styles.fileItemIcon}><IconoArchivo tamano={16} /></span>
                        <span className={styles.fileName}>{a.name}</span>
                        <span className={styles.fileSize}>{formatBytes(a.size)}</span>
                        <button
                          type="button"
                          className={styles.removeBtn}
                          aria-label={`Quitar ${a.name}`}
                          onClick={() => setArchivos((p) => p.filter((_, j) => j !== i))}
                        >
                          <IconoX />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Opciones */}
            <div className={styles.options}>
              <div className={styles.optPanel}>
                <div className={styles.optHead}><IconoAjustes />Detalles</div>
                <div className={styles.optBody}>
                  <div className={styles.field}>
                    <label className={styles.label}>Título <span className={styles.req}>*</span></label>
                    <p className={styles.fieldHint}><strong>Obligatorio.</strong> Nombre que identifica este envío, por ejemplo: nombre de la motonave, tipo de documento o fecha de arribo.</p>
                    <input
                      className={styles.input}
                      type="text"
                      value={titulo}
                      onChange={(e) => setTitulo(e.target.value)}
                      placeholder="Ej: Nombre de la motonave — tipo de documentos"
                      maxLength={255}
                      required
                    />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.label}>Mensaje <span className={styles.req}>*</span></label>
                    <p className={styles.fieldHint}><strong>Obligatorio.</strong> Describa brevemente el contenido del envío e indique cualquier observación relevante.</p>
                    <textarea
                      className={styles.textarea}
                      value={mensaje}
                      rows={3}
                      onChange={(e) => setMensaje(e.target.value)}
                      placeholder="Ej: Se adjuntan los documentos solicitados para revisión."
                      maxLength={2000}
                      required
                    />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.label}>
                      Destinatario <span className={styles.opt}>(opcional)</span>
                    </label>
                    <p className={styles.fieldHint}><strong>Opcional.</strong> Si conoce el correo de alguien a quien avisar puede ingresarlo — se le enviará un correo con el enlace. De lo contrario, déjelo vacío.</p>
                    <input
                      className={styles.input}
                      type="email"
                      value={destinatario}
                      onChange={(e) => setDestinatario(e.target.value)}
                      placeholder="correo@ejemplo.com"
                    />
                  </div>
                </div>
              </div>

              <button type="submit" className={styles.submitBtn} disabled={enviando || archivos.length === 0}>
                {enviando ? (
                  <><span className={styles.spinner} />Subiendo archivos…</>
                ) : (
                  <><IconoEnviar tamano={16} />Subir archivos</>
                )}
              </button>
            </div>
          </div>
        </form>
      </main>

      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
