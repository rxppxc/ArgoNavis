/**
 * El historial completo de la solicitud (2026-11-22), para el SNM que la revisa: lo que la
 * agencia había enviado antes de cada corrección, qué cambió, y todos los archivos con su
 * huella (también los retirados y las autorizaciones emitidas). Se pide al abrirlo: no pesa
 * en cada expediente.
 */
import { useEffect, useState } from "react";
import {
  apiSolicitudes, type ArchivoVisible, type ParRotulado, type RegistroSolicitud, type SolicitudDetalle,
  type VersionSolicitud,
} from "../../../api/solicitudes";
import { EstadoCarga } from "../../../components/EstadoCarga";
import { IconoAlerta, IconoDescargar, IconoOjo } from "../../../components/Iconos";
import { useNotificacion } from "../../../components/Notificaciones";
import { mensajeDeError } from "../../../utils/errores";
import { formatBytes } from "../../../utils/format";
import { formatearFechaHora } from "../presentacion";
import { archivoVisible, estadoArchivo, pasosDeLaVersion, textoSinVersion } from "./registro";
import styles from "./DetalleSolicitud.module.css";

function Pares({ pares }: { pares: ParRotulado[] }) {
  return (
    <dl className={styles.datos}>
      {pares.map(([rotulo, valor]) => (
        <div key={rotulo} className={styles.dato}><dt>{rotulo}</dt><dd>{valor}</dd></div>
      ))}
    </dl>
  );
}

/** Una versión, plegada: los pasos, qué cambió la agencia al corregirla y, entero, lo que había enviado. */
function Version({ v, onVer }: { v: VersionSolicitud; onVer: (a: ArchivoVisible) => void }) {
  return (
    <details className={styles.version}>
      <summary>Versión {v.numero}</summary>
      <ul className={styles.listaCorta}>
        {pasosDeLaVersion(v).map((p) => <li key={p}>{p}</li>)}
        {v.motivo && <li className={styles.textoLibre}>Motivo de la devolución: {v.motivo}</li>}
      </ul>

      <h4 className={styles.grupoTitulo}>Qué cambió al corregirla</h4>
      {v.cambios.length > 0 ? (
        <ul className={styles.listaCorta}>
          {v.cambios.map((c) => <li key={c} className={styles.textoLibre}>{c}</li>)}
        </ul>
      ) : <p className={styles.vacio}>La agencia la reenvió sin cambios.</p>}

      <h4 className={styles.grupoTitulo}>Lo que había enviado</h4>
      <Pares pares={v.datos} />
      {v.tripulantes.map((t) => (
        <div key={t.id} className={styles.tripulanteVersion}>
          <p className={styles.celdaPrincipal}>{t.nombre}</p>
          <Pares pares={t.datos} />
        </div>
      ))}
      <div className={styles.grupoDocs}>
        {v.documentos.map((d) => (
          <div key={d.id} className={styles.archivo}>
            <span className={styles.archivoNombre} title={d.nombre}>
              {d.documento ?? "Documento adicional"}{d.tripulante && <> · {d.tripulante}</>} · {d.nombre}
            </span>
            <button type="button" className={styles.btnIconoVer} title="Ver documento"
              aria-label={`Ver ${d.nombre}, de la versión ${v.numero}`}
              onClick={() => onVer({ id: d.id, nombre_original: d.nombre, tipo_mime: null })}>
              <IconoOjo tamano={13} />
            </button>
          </div>
        ))}
      </div>
    </details>
  );
}

function Archivos({ solicitudId, registro, onVer }: {
  solicitudId: number; registro: RegistroSolicitud; onVer: (a: ArchivoVisible) => void;
}) {
  const { mostrar } = useNotificacion();
  const [descargando, setDescargando] = useState<string | null>(null);

  async function descargar(a: ArchivoVisible, clave: string) {
    setDescargando(clave);
    try {
      await apiSolicitudes.descargarArchivo(solicitudId, a);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar el archivo."), "error");
    } finally {
      setDescargando(null);
    }
  }

  if (registro.archivos.length === 0) return <p className={styles.vacio}>Sin archivos.</p>;
  return (
    <div className={styles.tablaScroll}>
      <table className={styles.tabla}>
        <caption className="sr-only">Archivos de la solicitud y su huella</caption>
        <thead>
          <tr>
            <th scope="col">Archivo</th>
            <th scope="col">Fecha</th>
            <th scope="col">Estado</th>
            <th scope="col">Huella (SHA-256)</th>
            <th scope="col"><span className="sr-only">Ver o descargar</span></th>
          </tr>
        </thead>
        <tbody>
          {registro.archivos.map((a) => {
            const clave = `${a.clase}-${a.id}`;
            const visible = archivoVisible(a);
            return (
              <tr key={clave}>
                <td data-etiqueta="Archivo">
                  <div className={styles.celdaPrincipal}>{a.documento}</div>
                  <div className={`${styles.celdaSecundaria} ${styles.textoLibre}`}>
                    {a.tripulante && <>{a.tripulante} · </>}{a.nombre} · {formatBytes(a.tamano)}
                  </div>
                </td>
                <td data-etiqueta="Fecha">
                  {formatearFechaHora(a.fecha)}
                  {a.por && <div className={styles.celdaSecundaria}>{a.por}</div>}
                </td>
                <td data-etiqueta="Estado">{estadoArchivo(a)}</td>
                <td data-etiqueta="Huella (SHA-256)" className={styles.huella}>{a.sha256 ?? "Se está calculando"}</td>
                <td className={styles.celdaAncha}>
                  <div className={styles.filaIconos}>
                    <button type="button" className={styles.btnIconoVer} onClick={() => onVer(visible)}
                      title="Ver archivo" aria-label={`Ver ${a.nombre}, ${estadoArchivo(a).toLowerCase()}`}>
                      <IconoOjo tamano={13} />
                    </button>
                    <button type="button" className={styles.btnIconoVer} onClick={() => descargar(visible, clave)}
                      disabled={descargando === clave} title="Descargar archivo"
                      aria-label={`Descargar ${a.nombre}, ${estadoArchivo(a).toLowerCase()}`}>
                      <IconoDescargar tamano={13} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function RegistroExpediente({ s, onVer }: { s: SolicitudDetalle; onVer: (a: ArchivoVisible) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [registro, setRegistro] = useState<RegistroSolicitud | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Al abrirlo, y otra vez si la solicitud cambia de estado (aprobarla o finalizarla emite otra autorización).
  useEffect(() => {
    if (!abierto) return;
    let cancelado = false;
    apiSolicitudes.registro(s.id)
      .then((r) => { if (!cancelado) { setRegistro(r); setError(null); } })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudo cargar el historial completo.")); });
    return () => { cancelado = true; };
  }, [abierto, s.id, s.estado]);

  const sinVersion = registro && textoSinVersion(registro.sin_version);
  return (
    <section className={styles.panel} aria-labelledby="titulo-registro">
      <h2 id="titulo-registro" className={styles.panelTitulo}>Historial completo</h2>
      <p className={styles.ayuda}>
        Lo que la agencia había enviado antes de cada corrección, los documentos que reemplazó y la huella de cada
        archivo: si alguien lo cambia, deja de coincidir y el sistema no lo muestra. La agencia no lo ve.
      </p>
      <button type="button" className={styles.btnConsultar} aria-expanded={abierto} aria-controls="registro-expediente"
        onClick={() => setAbierto((v) => !v)}>
        {abierto ? "Ocultar el historial completo" : "Ver el historial completo"}
      </button>
      <div id="registro-expediente" className={styles.registro} hidden={!abierto}>
        {error && <p className={styles.error} role="alert"><IconoAlerta tamano={15} /> {error}</p>}
        {!registro && !error && <EstadoCarga texto="Cargando el historial…" />}
        {registro && (
          <>
            <h3 className={styles.registroTitulo}>Versiones anteriores</h3>
            {registro.versiones.map((v) => <Version key={v.numero} v={v} onVer={onVer} />)}
            {registro.versiones.length === 0 && !sinVersion && (
              <p className={styles.vacio}>La agencia no la ha corregido: es como la envió.</p>
            )}
            {sinVersion && <p className={styles.ayuda}>{sinVersion}</p>}
            <h3 className={styles.registroTitulo}>Archivos</h3>
            <Archivos solicitudId={s.id} registro={registro} onVer={onVer} />
          </>
        )}
      </div>
    </section>
  );
}
