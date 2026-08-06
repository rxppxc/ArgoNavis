import { useState, useRef, useEffect } from "react";
import type * as React from "react";
import { useNavigate } from "react-router-dom";
import { apiTransferencias } from "../../api/transfers";
import { formatBytes } from "../../utils/format";
import { TIPOS_ACEPTADOS, validarArchivos } from "../../utils/archivos";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import { usePermisos } from "../../hooks/usePermisos";
import {
  IconoSubir, IconoArchivo, IconoX, IconoAlerta, IconoEnviar,
  IconoAjustes, IconoBarco, IconoAncla, IconoUsuario, IconoReloj,
} from "../../components/Iconos";
import styles from "./PaginaSubida.module.css";

const DIAS_EXPIRACION_DEFECTO = 7;

const TIPOS_PDF = ".pdf";


export default function PaginaSubida() {
  const navegar = useNavigate();
  const inputRef                  = useRef<HTMLInputElement>(null);
  const { tiene } = usePermisos();

  // Flujo: Si tiene T-CREAR-COMPLETA usa el form completo. Si no tiene completa
  // pero sí T-CREAR-BASICA, usa el form simplificado (queda en borrador).
  // Admin legacy entra al modo completo automáticamente.
  const modoCompleto = tiene("T-CREAR-COMPLETA");
  const modoBasico   = !modoCompleto && tiene("T-CREAR-BASICA");

  const [archivos,       setArchivos]       = useState<File[]>([]);
  const [arrastrando,    setArrastrando]    = useState(false);
  const [titulo,         setTitulo]         = useState("");
  const [mensaje,        setMensaje]        = useState("");
  const [destinatario,   setDestinatario]   = useState("");
  const [enviando,       setEnviando]       = useState(false);
  const [error,          setError]          = useState<string | null>(null);

  const [puertos,       setPuertos]       = useState<{ id: number; nombre: string }[]>([]);
  const [puertoId,      setPuertoId]      = useState<number | "">("");
  const [naviera,       setNaviera]       = useState("");
  const [marino,        setMarino]        = useState("");

  useEffect(() => {
    if (!modoCompleto) return;
    apiTransferencias.listarPuertos().then(setPuertos).catch(() => {});
  }, [modoCompleto]);

  function agregarArchivos(lista: FileList | null) {
    if (!lista) return;
    const nuevos = Array.from(lista);

    // Se valida en ambos modos: el atributo `accept` del input no cubre el
    // arrastrar-y-soltar, y el tamaño nunca lo filtra el navegador.
    const errorValidacion = validarArchivos(nuevos, { soloPdf: modoBasico });
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
    if (modoCompleto) {
      if (!naviera.trim()) {
        setError("Debes ingresar el nombre de la naviera.");
        return;
      }
      if (!marino.trim()) {
        setError("Debes ingresar el nombre del marino.");
        return;
      }
    }
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
      // La expiración ya no es configurable: el backend siempre usa
      // TRANSFER_EXPIRY_DAYS (7 días) para toda transferencia nueva.

      if (modoCompleto) {
        fd.append("recipient", destinatario);
        if (puertoId !== "") fd.append("puerto_id", String(puertoId));
        fd.append("marino", marino.trim());
        fd.append("naviera", naviera.trim());
        const transferencia = await apiTransferencias.crear(fd);
        navegar(`/t/${transferencia.token}?new=1`);
      } else {
        // Modo básico: destinatario opcional, queda en borrador
        if (destinatario.trim()) fd.append("recipient", destinatario.trim());
        await apiTransferencias.crearBorrador(fd);
        navegar(`/dashboard?borrador=1`);
      }
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
  if (!modoCompleto && !modoBasico) {
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
            No tienes permiso para crear transferencias. Contacta al administrador.
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
          <h1 className={styles.pageTitle}>
            {modoBasico ? "Envío de documentación" : "Nueva Transferencia"}
          </h1>
          <p className={styles.pageSub}>
            {modoBasico
              ? "Adjunte los documentos de la Nave / Marinos y complete los datos del envío. El personal del Servicio Nacional de Migración validará la información antes de procesarla."
              : "Sube tus archivos y obtén un enlace seguro para compartir"}
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
              {modoBasico && (
                <p className={styles.panelHint}><strong>Obligatorio.</strong> Adjunte los documentos en formato PDF. Máximo 50 MB por archivo.</p>
              )}
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
                  <p className={styles.dropHint}>{modoBasico ? "Solo PDF · Máx. 50 MB por archivo" : "Máx. 50 MB por archivo"}</p>
                  <input
                    ref={inputRef}
                    type="file"
                    multiple
                    hidden
                    accept={modoBasico ? TIPOS_PDF : TIPOS_ACEPTADOS}
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
                    {modoBasico && (
                      <p className={styles.fieldHint}><strong>Obligatorio.</strong> Nombre que identifica este envío, por ejemplo: nombre de la motonave, tipo de documento o fecha de arribo.</p>
                    )}
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
                    {modoBasico && (
                      <p className={styles.fieldHint}><strong>Obligatorio.</strong> Describa brevemente el contenido del envío e indique cualquier observación relevante.</p>
                    )}
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
                      Destinatario {modoCompleto
                        ? <span className={styles.req}>*</span>
                        : <span className={styles.opt}>(opcional)</span>}
                    </label>
                    {modoBasico && (
                      <p className={styles.fieldHint}><strong>Opcional.</strong> Si conoce el correo del receptor puede ingresarlo. De lo contrario, déjelo vacío — el personal de Migración lo completará.</p>
                    )}
                    <input
                      className={styles.input}
                      type="email"
                      value={destinatario}
                      onChange={(e) => setDestinatario(e.target.value)}
                      placeholder="correo@ejemplo.com"
                      required={modoCompleto}
                    />
                  </div>

                  {/* Puerto */}
                  {modoCompleto && puertos.length > 0 && (
                    <div className={styles.field}>
                      <label className={styles.label}><IconoAncla tamano={14} /> Puerto / Muelle <span className={styles.req}>*</span></label>
                      <select
                        className={styles.select}
                        value={puertoId}
                        onChange={e => setPuertoId(e.target.value === "" ? "" : Number(e.target.value))}
                        required
                      >
                        <option value="">— Selecciona un puerto / muelle —</option>
                        {puertos.map(p => (
                          <option key={p.id} value={p.id}>{p.nombre}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Naviera */}
                  {modoCompleto && (
                    <div className={styles.field}>
                      <label className={styles.label}><IconoBarco /> Naviera <span className={styles.req}>*</span></label>
                      <input
                        className={styles.input}
                        type="text"
                        value={naviera}
                        onChange={(e) => setNaviera(e.target.value)}
                        placeholder="Ej: Naviera del Pacífico S.A."
                        maxLength={255}
                        required
                      />
                    </div>
                  )}

                  {/* Marino */}
                  {modoCompleto && (
                    <div className={styles.field}>
                      <label className={styles.label}><IconoUsuario tamano={14} /> Marino <span className={styles.req}>*</span></label>
                      <input
                        className={styles.input}
                        type="text"
                        value={marino}
                        onChange={(e) => setMarino(e.target.value)}
                        placeholder="Ej: Víctor Pérez"
                        maxLength={255}
                        required
                      />
                    </div>
                  )}
                </div>
              </div>

              {modoCompleto && (
                <div className={styles.optPanel}>
                  <div className={styles.optHead}>Expiración</div>
                  <div className={styles.optBody}>
                    <p className={styles.expiryNota}>
                      <IconoReloj tamano={15} />
                      Esta transferencia expirará automáticamente a los <strong>{DIAS_EXPIRACION_DEFECTO} días</strong> de su creación.
                    </p>
                  </div>
                </div>
              )}

              <button type="submit" className={styles.submitBtn} disabled={enviando || archivos.length === 0}>
                {enviando ? (
                  <><span className={styles.spinner} />Subiendo archivos…</>
                ) : (
                  <><IconoEnviar tamano={16} />{modoBasico ? "Enviar documentación" : "Crear transferencia"}</>
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
