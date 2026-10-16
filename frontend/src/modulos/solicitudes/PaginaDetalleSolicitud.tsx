/**
 * Expediente de una solicitud de Autorización Marítima.
 *
 * Lo ven los usuarios de la agencia que la envió, UCVMM, el admin y —desde
 * que se aprueba— el puesto de control asignado. Las acciones disponibles
 * las decide el backend (`acciones`) según el rol y el estado.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  apiSolicitudes, type DocumentoSolicitud, type SolicitudDetalle, type TripulanteSolicitud,
} from "../../api/solicitudes";
import { MarcoPagina } from "../../components/MarcoPagina";
import { ModalPreview } from "../../components/ModalPreview";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoAlerta, IconoArchivo, IconoDescargar, IconoEditar, IconoX } from "../../components/Iconos";
import { mensajeDeError } from "../../utils/errores";
import { DocumentosSolicitud } from "./DocumentosSolicitud";
import { HistorialSolicitud } from "./HistorialSolicitud";
import { InsigniaEstado } from "./InsigniaEstado";
import { PanelPuerto } from "./PanelPuerto";
import { PanelRevision } from "./PanelRevision";
import {
  ETIQUETA_RANGO, ETIQUETA_SEXO, formatearFecha, formatearFechaHora, tiempoRestante,
} from "./presentacion";
import styles from "./DetalleSolicitud.module.css";

function BannerEstado({ s }: { s: SolicitudDetalle }) {
  switch (s.estado) {
    case "review":
      return (
        <div className={`${styles.banner} ${styles.bannerRevision}`}>
          En revisión por UCVMM — enviada el {formatearFechaHora(s.enviada_en)}
          {s.veces_devuelta > 0 && <> · corregida {s.veces_devuelta} {s.veces_devuelta === 1 ? "vez" : "veces"}</>}
        </div>
      );
    case "returned": {
      const plazo = tiempoRestante(s.plazo_correccion);
      return (
        <div className={`${styles.banner} ${styles.bannerCorreccion}`}>
          <div className={styles.bannerTitulo}><IconoAlerta tamano={15} /> Devuelta a corrección</div>
          <div className={styles.bannerTexto}>{s.motivo_devolucion}</div>
          <div className={styles.bannerPie}>
            Plazo para corregir: hasta el {formatearFechaHora(s.plazo_correccion)}
            {plazo.vencido ? " (vencido)" : ` (quedan ${plazo.texto})`}
          </div>
        </div>
      );
    }
    case "approved": {
      // Solo en los trámites cuyo proceso pide avisar la custodia al aprobar.
      const restringidos = s.tipo_tramite_aviso_custodia
        ? s.tripulantes.filter((t) => t.nacionalidad_restringida).map((t) => t.nombre_completo)
        : [];
      return (
        <div className={`${styles.banner} ${styles.bannerAprobada}`}>
          <div className={styles.bannerTitulo}>Autorización aprobada</div>
          <div className={styles.bannerTexto}>
            Aprobada el {formatearFechaHora(s.aprobada_en)} por {s.aprobada_por ?? "UCVMM"}. Vigente hasta el{" "}
            {formatearFechaHora(s.vigente_hasta)}: el puesto de control debe finalizarla antes de esa fecha.
          </div>
          {s.observacion_aprobacion && <div className={styles.bannerPie}>Observación interna: {s.observacion_aprobacion}</div>}
          {restringidos.length > 0 && (
            <div className={styles.bannerPie}>
              Nacionalidad restringida: {restringidos.join(", ")}. La agencia debe realizar el trámite de
              solicitud de custodia.
            </div>
          )}
        </div>
      );
    }
    case "finalized":
      return (
        <div className={`${styles.banner} ${styles.bannerFinalizada}`}>
          <div className={styles.bannerTitulo}>Finalizada en {s.puesto_finalizacion_nombre ?? s.puesto_nombre}</div>
          <div className={styles.bannerTexto}>
            {formatearFechaHora(s.finalizada_en)}
            {s.comentario_finalizacion && <> — {s.finalizada_por ?? "Puesto de control"}: {s.comentario_finalizacion}</>}
          </div>
          {s.puesto_finalizacion_nombre && s.puesto_finalizacion_nombre !== s.puesto_nombre && (
            <div className={styles.bannerPie}>La autorización era para {s.puesto_nombre}.</div>
          )}
        </div>
      );
    case "denied":
      return (
        <div className={`${styles.banner} ${styles.bannerNegada}`}>
          <div className={styles.bannerTitulo}>Solicitud denegada</div>
          <div className={styles.bannerTexto}>{s.motivo_negacion}</div>
          <div className={styles.bannerPie}>{formatearFechaHora(s.negada_en)}</div>
        </div>
      );
    case "expired":
      return (
        <div className={`${styles.banner} ${styles.bannerExpirada}`}>
          <div className={styles.bannerTitulo}>Expirada</div>
          <div className={styles.bannerTexto}>
            {s.aprobada_en
              ? "La autorización no se finalizó en el puesto de control dentro del plazo."
              : "La agencia no corrigió la solicitud dentro del plazo."}
          </div>
          <div className={styles.bannerPie}>{formatearFechaHora(s.expirada_en)}</div>
        </div>
      );
    default:
      return null;
  }
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string | null | undefined }) {
  if (!valor) return null;
  return (
    <div className={styles.dato}>
      <dt>{etiqueta}</dt>
      <dd>{valor}</dd>
    </div>
  );
}

export default function PaginaDetalleSolicitud() {
  const { id = "" } = useParams<{ id: string }>();
  const solicitudId = Number(id);
  const { mostrar } = useNotificacion();
  const [solicitud, setSolicitud] = useState<SolicitudDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vistaPrevia, setVistaPrevia] = useState<DocumentoSolicitud | null>(null);
  const [documentacionDe, setDocumentacionDe] = useState<TripulanteSolicitud | null>(null);
  const [descargando, setDescargando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.obtener(solicitudId)
      .then((s) => { if (!cancelado) setSolicitud(s); })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudo cargar la solicitud.")); });
    return () => { cancelado = true; };
  }, [solicitudId]);

  async function descargarPdf() {
    if (!solicitud) return;
    setDescargando(true);
    try {
      await apiSolicitudes.descargarAutorizacion(solicitud.id, solicitud.numero);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar la autorización."), "error");
    } finally {
      setDescargando(false);
    }
  }

  if (error) {
    return (
      <MarcoPagina volverA="/dashboard">
        <div className={styles.error}><IconoAlerta /> {error}</div>
      </MarcoPagina>
    );
  }
  if (!solicitud) {
    return <MarcoPagina volverA="/dashboard"><div className={styles.cargando}>Cargando expediente…</div></MarcoPagina>;
  }

  const s = solicitud;
  const buque = [s.nombre_buque, s.imo && `IMO ${s.imo}`].filter(Boolean).join(" · ");
  // Los de cada tripulante se abren desde su fila; abajo solo va lo que no es de nadie.
  const hayDocumentosDeLaSolicitud = s.checklist.some((c) => c.tripulante_id === null)
    || s.documentos.some((d) => d.tripulante_id === null);

  return (
    <MarcoPagina volverA="/dashboard" ancho="amplio">
      <header className={styles.encabezado}>
        <div className={styles.encabezadoTexto}>
          <div className={styles.numero}>
            <span>{s.numero ?? `Solicitud ${s.id}`}</span>
            <InsigniaEstado estado={s.estado} grande />
          </div>
          <h1>{s.tipo_tramite_nombre}</h1>
          <div className={styles.subtitulo}>
            {[buque, s.puesto_nombre, `Operación: ${formatearFecha(s.fecha_operacion)}`]
              .filter(Boolean).join(" — ")}
          </div>
        </div>
        <div className={styles.encabezadoAcciones}>
          {s.acciones.corregir && (
            <Link to={`/solicitudes/${s.id}/corregir`} className={styles.btnPrimario}>
              <IconoEditar tamano={15} /> Corregir solicitud
            </Link>
          )}
          {s.acciones.descargar_autorizacion && (
            <button type="button" className={styles.btnPrimario} onClick={descargarPdf} disabled={descargando}>
              <IconoDescargar tamano={15} /> {descargando ? "Generando…" : "Descargar autorización (PDF)"}
            </button>
          )}
        </div>
      </header>

      <BannerEstado s={s} />

      <div className={styles.columnas}>
        <div className={styles.principal}>
          <section className={styles.panel}>
            <h2 className={styles.panelTitulo}>Datos del trámite</h2>
            <dl className={styles.datos}>
              <Dato etiqueta="Agencia naviera" valor={s.agencia_nombre} />
              <Dato etiqueta="Creada por" valor={s.creada_por} />
              <Dato etiqueta="Fecha de solicitud" valor={formatearFechaHora(s.created_at)} />
              <Dato etiqueta="Puesto de Control Migratorio" valor={s.puesto_nombre} />
              <Dato etiqueta="Fecha de la operación" valor={formatearFecha(s.fecha_operacion)} />
              <Dato etiqueta="Buque" valor={s.nombre_buque} />
              <Dato etiqueta="IMO" valor={s.imo} />
              <Dato etiqueta="Bandera" valor={s.bandera_nombre} />
              <Dato etiqueta="Puerto" valor={s.nombre_puerto} />
              <Dato etiqueta="Puerto de desembarque" valor={s.puerto_desembarque} />
              <Dato etiqueta="Clínica u hospital" valor={s.clinica_hospital} />
              <Dato etiqueta="Motivo" valor={s.motivo} />
            </dl>
            {s.tipo_tramite_nota && <div className={styles.nota}>{s.tipo_tramite_nota}</div>}
            {s.observaciones && (
              <div className={styles.observaciones}>
                <span>Observaciones de la agencia</span>
                {s.observaciones}
              </div>
            )}
          </section>

          <section className={styles.panel}>
            <h2 className={styles.panelTitulo}>
              Tripulantes <span className={styles.contador}>{s.tripulantes.length}</span>
            </h2>
            {s.valida_vigencia && (
              <p className={styles.ayuda}>Este trámite exige pasaporte y seamanbook vigentes a la fecha de la operación.</p>
            )}
            <div className={styles.tablaScroll}>
              <table className={styles.tabla}>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tripulante</th>
                    <th>Nacionalidad</th>
                    <th>Pasaporte</th>
                    <th>Seamanbook</th>
                    <th>Rango / ocupación</th>
                    <th>Documentos</th>
                  </tr>
                </thead>
                <tbody>
                  {s.tripulantes.map((m, i) => {
                    const faltan = s.checklist.filter((c) => c.tripulante_id === m.id && !c.cubierta).length;
                    return (
                      <tr key={m.id}>
                        <td>{i + 1}</td>
                        <td>
                          <div className={styles.celdaPrincipal}>{m.nombre_completo}</div>
                          <div className={styles.celdaSecundaria}>
                            {ETIQUETA_SEXO[m.sexo]} · Nac. {formatearFecha(m.fecha_nacimiento)}
                            {m.pais_nacimiento_nombre && <> · {m.pais_nacimiento_nombre}</>}
                          </div>
                          {/* Solo llega al personal del SNM: a la agencia el backend le manda null */}
                          {m.con_impedimento && <span className={styles.chipImpedimento}>Con impedimento</span>}
                        </td>
                        <td>
                          {m.nacionalidad_nombre ?? m.nacionalidad}
                          {m.nacionalidad_restringida && s.tipo_tramite_aviso_custodia && (
                            <div className={styles.chipRestringida}>Restringida</div>
                          )}
                        </td>
                        <td>
                          <div className={styles.celdaPrincipal}>{m.pasaporte}</div>
                          <div className={m.pasaporte_vencido ? styles.vencido : styles.celdaSecundaria}>
                            Vence {formatearFecha(m.pasaporte_expira)}{m.pasaporte_vencido && " — vencido"}
                          </div>
                        </td>
                        <td>
                          {m.porta_libreta ? (
                            <>
                              <div className={styles.celdaPrincipal}>{m.libreta_marino ?? "—"}</div>
                              <div className={m.libreta_vencida ? styles.vencido : styles.celdaSecundaria}>
                                Vence {formatearFecha(m.libreta_expira)}{m.libreta_vencida && " — vencido"}
                              </div>
                            </>
                          ) : (
                            <span className={styles.celdaSecundaria}>No aplica</span>
                          )}
                        </td>
                        <td>
                          <div className={styles.celdaPrincipal}>{ETIQUETA_RANGO[m.rango]}</div>
                          <div className={styles.celdaSecundaria}>{m.ocupacion}</div>
                        </td>
                        <td>
                          <button type="button" className={styles.btnDocumentacion} onClick={() => setDocumentacionDe(m)}
                            aria-label={`Ver documentación de ${m.nombre_completo}`}>
                            <IconoArchivo tamano={13} />
                            {s.documentos.filter((d) => d.tripulante_id === m.id).length}
                            <span>Ver documentación</span>
                          </button>
                          {faltan > 0 && (
                            <div className={styles.textoFalta}>
                              {faltan === 1 ? "Falta 1 documento" : `Faltan ${faltan} documentos`}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {hayDocumentosDeLaSolicitud && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitulo}>Documentos de la solicitud</h2>
              <DocumentosSolicitud solicitud={s} onVer={setVistaPrevia} />
            </section>
          )}
        </div>

        <aside className={styles.lateral}>
          {s.acciones.revisar && <PanelRevision solicitud={s} onActualizada={setSolicitud} />}
          {s.acciones.conflicto_revision && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitulo}>Revisión UCVMM</h2>
              <p className={styles.ayuda}>
                No puedes revisar esta solicitud porque la creaste tú o es de tu agencia. La debe revisar otro
                funcionario de UCVMM.
              </p>
            </section>
          )}
          {s.acciones.finalizar && <PanelPuerto solicitud={s} onActualizada={setSolicitud} />}
          {/* Solo llega al personal del SNM: el backend no lo envía a la agencia */}
          {!s.acciones.revisar && s.impedimentos_verificados_en && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitulo}>Impedimentos</h2>
              <p className={styles.ayuda}>
                {s.impedimentos_verificados ? "Verificación realizada" : "Verificación pendiente"}
                {s.impedimentos_verificados_por && ` — ${s.impedimentos_verificados_por}`}
                {s.impedimentos_verificados_en && `, ${formatearFechaHora(s.impedimentos_verificados_en)}`}
              </p>
              {s.tripulantes.some((t) => t.con_impedimento) && (
                <p className={styles.ayuda}>
                  Con impedimento: {s.tripulantes.filter((t) => t.con_impedimento).map((t) => t.nombre_completo).join(", ")}.
                </p>
              )}
              {s.comentario_impedimentos && <div className={styles.observaciones}>{s.comentario_impedimentos}</div>}
            </section>
          )}
          <HistorialSolicitud eventos={s.eventos} puestoFinalizacion={s.puesto_finalizacion_nombre} />
        </aside>
      </div>

      {documentacionDe && (
        <div className={styles.modalFondo} onClick={() => setDocumentacionDe(null)}>
          <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="titulo-documentacion"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => { if (e.key === "Escape") setDocumentacionDe(null); }}>
            <div className={styles.modalCabecera}>
              <h2 id="titulo-documentacion" className={styles.panelTitulo}>Documentación de {documentacionDe.nombre_completo}</h2>
              <button type="button" className={styles.btnIcono} onClick={() => setDocumentacionDe(null)}
                aria-label="Cerrar" autoFocus>
                <IconoX tamano={14} />
              </button>
            </div>
            <DocumentosSolicitud solicitud={s} onVer={setVistaPrevia} tripulanteId={documentacionDe.id} />
          </div>
        </div>
      )}
      {vistaPrevia && (
        <ModalPreview solicitudId={s.id} documento={vistaPrevia} onCerrar={() => setVistaPrevia(null)} />
      )}
    </MarcoPagina>
  );
}
