/**
 * Expediente de una solicitud de Autorización Marítima.
 *
 * Lo ven los usuarios de la agencia que la envió, UCVMM, el admin y —desde
 * que se aprueba— el puesto de control asignado. Las acciones disponibles
 * las decide el backend (`acciones`) según el rol y el estado.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  apiSolicitudes, type DocumentoSolicitud, type SolicitudDetalle, type TripulanteSolicitud,
} from "../../api/solicitudes";
import { EstadoCarga } from "../../components/EstadoCarga";
import { MarcoPagina } from "../../components/MarcoPagina";
import { ModalPreview } from "../../components/ModalPreview";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoAlerta, IconoDescargar, IconoEditar, IconoReloj, IconoX } from "../../components/Iconos";
import { useAtraparFoco } from "../../hooks/useAtraparFoco";
import { usePendientes } from "../../hooks/usePendientes";
import { useTituloDocumento } from "../../hooks/useTituloDocumento";
import { mensajeDeError } from "../../utils/errores";
import { destinoDeVolver } from "../../utils/volver";
import { DocumentosSolicitud } from "./DocumentosSolicitud";
import { HistorialSolicitud } from "./HistorialSolicitud";
import { InsigniaEstado } from "./InsigniaEstado";
import { PanelPuerto } from "./PanelPuerto";
import { PanelRevision } from "./PanelRevision";
import {
  formatearFecha, formatearFechaHora, puestoAutorizado, TEXTO_HORARIO_LABORAL, textoPuestos, tiempoRestante,
} from "./presentacion";
import { SeccionTripulantes } from "./SeccionTripulantes";
import { useVerificacionImpedimentos } from "./useVerificacionImpedimentos";
import styles from "./DetalleSolicitud.module.css";

/** Aprobada fuera del horario laboral: el aviso y el costo migratorio, también
 *  para la agencia (2026-11-11). Lo mismo dicen el correo de aprobación y el PDF. */
function AvisoFueraDeHorario({ s }: { s: SolicitudDetalle }) {
  if (!s.fuera_de_horario) return null;
  return (
    <div className={styles.avisoHorario}>
      <IconoReloj tamano={14} />
      <span>
        Aprobada fuera del horario laboral ({TEXTO_HORARIO_LABORAL}).
        {s.costo_fuera_de_horario && <> Costo migratorio: <strong>{s.costo_fuera_de_horario}</strong>.</>}
      </span>
    </div>
  );
}

function BannerEstado({ s }: { s: SolicitudDetalle }) {
  switch (s.estado) {
    case "review":
      return (
        <div className={`${styles.banner} ${styles.bannerRevision}`}>
          {/* Neutro: lo ve también la agencia, que no trabaja con las unidades internas (2026-11-11). */}
          En revisión por el Servicio Nacional de Migración — enviada el {formatearFechaHora(s.enviada_en)}
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
            {plazo.vencido ? " (vencido)" : ` (${plazo.frase})`}
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
            Aprobada el {formatearFechaHora(s.aprobada_en)} por {s.aprobada_por ?? "el Servicio Nacional de Migración"}. Vigente hasta el{" "}
            {formatearFechaHora(s.vigente_hasta)}: el puesto de control debe finalizarla antes de esa fecha.
          </div>
          {s.observacion_aprobacion && <div className={styles.bannerPie}>Observación interna: {s.observacion_aprobacion}</div>}
          <AvisoFueraDeHorario s={s} />
          {/* Al puesto que la finaliza se lo dice su panel. */}
          {!s.acciones.finalizar && (
            <div className={styles.bannerPie}>
              {s.puesto_destino_nombre && <>Con cambio de puerto: de {s.puesto_nombre} a {s.puesto_destino_nombre}. </>}
              Vale solo para {puestoAutorizado(s)}: si la operación se realiza en otro puesto, la agencia debe presentar
              una nueva solicitud.
            </div>
          )}
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
          <div className={styles.bannerTitulo}>Finalizada en {s.puesto_finalizacion_nombre ?? puestoAutorizado(s)}</div>
          <div className={styles.bannerTexto}>
            {formatearFechaHora(s.finalizada_en)}
            {s.comentario_finalizacion && <> — {s.finalizada_por ?? "Puesto de control"}: {s.comentario_finalizacion}</>}
          </div>
          {s.puesto_destino_nombre && (
            <div className={styles.bannerPie}>Con cambio de puerto: de {s.puesto_nombre} a {s.puesto_destino_nombre}.</div>
          )}
          {/* Las finalizadas en otro puesto antes del 30/10/2026. */}
          {s.puesto_finalizacion_nombre && s.puesto_finalizacion_nombre !== puestoAutorizado(s) && (
            <div className={styles.bannerPie}>La autorización era para {puestoAutorizado(s)}.</div>
          )}
          <AvisoFueraDeHorario s={s} />
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

/** Documentos de un tripulante. Como los demás modales: el foco queda adentro
 *  (y vuelve al botón que lo abrió) y Escape lo cierra, salvo que encima esté
 *  abierta la vista previa, que se cierra primero. */
function ModalDocumentacion({ tripulante, tapado, onCerrar, children }: {
  tripulante: TripulanteSolicitud; tapado: boolean; onCerrar: () => void; children: React.ReactNode;
}) {
  const refModal = useAtraparFoco(!tapado);
  useEffect(() => {
    if (tapado) return;
    function alTeclear(e: KeyboardEvent) {
      if (e.key === "Escape") onCerrar();
    }
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [tapado, onCerrar]);

  return (
    <div className={styles.modalFondo} onClick={onCerrar}>
      <div ref={refModal} className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="titulo-documentacion"
        onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalCabecera}>
          <h2 id="titulo-documentacion" className={styles.panelTitulo}>Documentación de {tripulante.nombre_completo}</h2>
          <button type="button" className={styles.btnIcono} onClick={onCerrar} aria-label="Cerrar" data-focus-inicial>
            <IconoX tamano={14} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Las verificaciones de impedimentos ya registradas: la de UCVMM y la del
 *  puesto de control. Solo le llegan al personal del SNM (el backend no las
 *  envía a la agencia); quien está verificando ve la suya en la tabla. */
function ResumenImpedimentos({ s }: { s: SolicitudDetalle }) {
  const etapas: {
    titulo: string; verificada: boolean; por: string | null; en: string; comentario: string | null;
    con: TripulanteSolicitud[];
  }[] = [];
  if (!s.acciones.revisar && s.impedimentos_verificados_en) {
    etapas.push({
      titulo: "UCVMM", verificada: s.impedimentos_verificados, por: s.impedimentos_verificados_por,
      en: s.impedimentos_verificados_en, comentario: s.comentario_impedimentos,
      con: s.tripulantes.filter((t) => t.con_impedimento),
    });
  }
  if (!s.acciones.finalizar && s.impedimentos_puesto_en) {
    etapas.push({
      titulo: "Puesto de control", verificada: s.impedimentos_puesto_verificados, por: s.impedimentos_puesto_por,
      en: s.impedimentos_puesto_en, comentario: s.comentario_impedimentos_puesto,
      con: s.tripulantes.filter((t) => t.con_impedimento_puesto),
    });
  }
  if (!etapas.length) return null;

  return (
    <section className={styles.panel}>
      <h2 className={styles.panelTitulo}>Impedimentos</h2>
      {etapas.map((e) => (
        <div key={e.titulo} className={styles.etapaImpedimentos}>
          <p className={styles.ayuda}>
            <strong>{e.titulo}:</strong> {e.verificada ? "verificación realizada" : "verificación pendiente"}
            {e.por && ` — ${e.por}`}
            {e.en && `, ${formatearFechaHora(e.en)}`}
          </p>
          {e.con.length > 0 && (
            <p className={styles.ayuda}>Con impedimento: {e.con.map((t) => t.nombre_completo).join(", ")}.</p>
          )}
          {e.comentario && <div className={styles.observaciones}>{e.comentario}</div>}
        </div>
      ))}
    </section>
  );
}

/** Las dos líneas de lectura mecánica del pie del expediente, como las de un
 *  pasaporte: mayúsculas sin tildes, campos separados por «<<» y 44 caracteres. */
function lineasMecanicas(s: SolicitudDetalle): string[] {
  const linea = (...campos: (string | number | null | undefined)[]) => {
    const texto = campos
      .map((c) => String(c ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase()
        .replace(/[^A-Z0-9]+/g, "<").replace(/^<|<$/g, ""))
      .filter(Boolean).join("<<");
    return (texto + "<".repeat(44)).slice(0, 44);
  };
  const operacion = (s.fecha_operacion ?? "").split("-").reverse().join("");
  return [
    linea("AM", (s.numero ?? String(s.id)).replace(/^AM-/, "").replace(/-/g, ""), s.tipo_tramite_nombre, s.puesto_nombre),
    linea(s.agencia_nombre, operacion, s.tripulantes.length),
  ];
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
  // «Volver» regresa a donde se abrió el expediente (la consulta histórica con sus filtros,
  // las estadísticas, la pestaña de la bandeja); sin origen, al inicio.
  const volverA = destinoDeVolver(useLocation().state);
  const [solicitud, setSolicitud] = useState<SolicitudDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  useTituloDocumento(solicitud ? `${solicitud.numero ?? `Solicitud ${solicitud.id}`} · ${solicitud.tipo_tramite_nombre}` : "Expediente");
  // Tras aprobar, devolver o finalizar, la campana se pone al día sin esperar su próxima consulta.
  const { refrescar } = usePendientes();
  const actualizar = useCallback((s: SolicitudDetalle) => {
    setSolicitud(s);
    refrescar();
  }, [refrescar]);

  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.obtener(solicitudId)
      .then((s) => { if (!cancelado) setSolicitud(s); })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudo cargar la solicitud.")); });
    return () => { cancelado = true; };
  }, [solicitudId]);

  if (error) {
    return (
      <MarcoPagina volverA={volverA}>
        <div className={styles.error} role="alert"><IconoAlerta /> {error}</div>
      </MarcoPagina>
    );
  }
  if (!solicitud) {
    return <MarcoPagina volverA={volverA}><EstadoCarga texto="Cargando expediente…" pagina /></MarcoPagina>;
  }
  // key: al pasar a otro expediente se descarta lo que se estaba marcando o viendo en el anterior.
  return <Expediente key={solicitud.id} s={solicitud} onActualizada={actualizar} volverA={volverA} />;
}

function Expediente({ s, onActualizada, volverA }: {
  s: SolicitudDetalle; onActualizada: (s: SolicitudDetalle) => void; volverA: string;
}) {
  const { mostrar } = useNotificacion();
  // La verificación de impedimentos se marca en la tabla de tripulantes y la
  // resume el panel de decisión (UCVMM) o el del puesto: el estado vive aquí,
  // compartido por los dos. Una por etapa, para que quien aprueba y luego
  // finaliza (el Administrador) no arrastre lo marcado de una a la otra.
  const verificacion = useVerificacionImpedimentos(s, onActualizada, "ucvmm");
  const verificacionPuesto = useVerificacionImpedimentos(s, onActualizada, "puesto");
  const verificacionTabla = s.acciones.revisar ? verificacion : s.acciones.finalizar ? verificacionPuesto : null;
  const [vistaPrevia, setVistaPrevia] = useState<DocumentoSolicitud | null>(null);
  const [documentacionDe, setDocumentacionDe] = useState<TripulanteSolicitud | null>(null);
  const [descargando, setDescargando] = useState(false);

  async function descargarPdf() {
    setDescargando(true);
    try {
      await apiSolicitudes.descargarAutorizacion(s.id, s.numero);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo descargar la autorización."), "error");
    } finally {
      setDescargando(false);
    }
  }

  const buque = [s.nombre_buque, s.imo && `IMO ${s.imo}`].filter(Boolean).join(" · ");
  // Los de cada tripulante se abren desde su fila; abajo solo va lo que no es de nadie.
  const hayDocumentosDeLaSolicitud = s.checklist.some((c) => c.tripulante_id === null)
    || s.documentos.some((d) => d.tripulante_id === null);

  return (
    <MarcoPagina volverA={volverA} ancho="amplio">
      {/* La cabeza del documento (identidad «pase oficial», 2026-11-11): la franja
          amarilla, el rótulo, el trámite, el número y el sello del estado. */}
      <header className={styles.encabezado}>
        <div className={styles.encabezadoTexto}>
          <p className={styles.antetitulo}>Autorización marítima · Formulario No. 3</p>
          <h1>{s.tipo_tramite_nombre}</h1>
          <p className={styles.numero}><small>N.º</small>{s.numero ?? `Solicitud ${s.id}`}</p>
          <div className={styles.subtitulo}>
            {[buque, textoPuestos(s), `Operación: ${formatearFecha(s.fecha_operacion)}`]
              .filter(Boolean).join(" — ")}
          </div>
          {s.fuera_de_horario && (
            <span className={styles.chipHorario}>
              <IconoReloj tamano={12} /> Aprobada fuera del horario
              {s.costo_fuera_de_horario && <> · {s.costo_fuera_de_horario}</>}
            </span>
          )}
        </div>
        <div className={styles.sello}><InsigniaEstado estado={s.estado} grande /></div>
        {(s.acciones.corregir || s.acciones.descargar_autorizacion) && (
        <div className={styles.encabezadoAcciones}>
          {s.acciones.corregir && (
            <Link to={`/solicitudes/${s.id}/corregir`} className={styles.btnPrimario}>
              <IconoEditar tamano={15} /> Corregir solicitud
            </Link>
          )}
          {s.acciones.descargar_autorizacion && (
            // Para el puesto de control la acción principal es finalizar (en su panel): la descarga queda secundaria.
            <button type="button" className={s.acciones.finalizar ? styles.btnConsultar : styles.btnPrimario}
              onClick={descargarPdf} disabled={descargando}>
              <IconoDescargar tamano={15} /> {descargando ? "Generando…" : "Descargar autorización (PDF)"}
            </button>
          )}
        </div>
        )}
      </header>

      <BannerEstado s={s} />

      <div className={`${styles.columnas} ${verificacionTabla ? styles.columnasRevision : ""}`}>
        <div className={styles.principal}>
          <section className={styles.panel}>
            <h2 className={styles.panelTitulo}>Datos del trámite</h2>
            <dl className={styles.datos}>
              <Dato etiqueta="Agencia naviera" valor={s.agencia_nombre} />
              <Dato etiqueta="Creada por" valor={s.creada_por} />
              <Dato etiqueta="Fecha de solicitud" valor={formatearFechaHora(s.created_at)} />
              <Dato etiqueta="Puesto de Control Migratorio" valor={s.puesto_nombre} />
              {/* Cambio de puerto (2026-11-13): el nuevo puesto, que la finaliza. */}
              <Dato etiqueta="Cambio de puerto a" valor={s.puesto_destino_nombre} />
              {/* El sector de UCVMM (2026-11-10): solo le llega al SNM. */}
              {s.sector_nombre && <Dato etiqueta="Sector" valor={s.sector_nombre} />}
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

          <SeccionTripulantes solicitud={s} verificacion={verificacionTabla} onVerDocumentacion={setDocumentacionDe} />

          {hayDocumentosDeLaSolicitud && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitulo}>Documentos de la solicitud</h2>
              <DocumentosSolicitud solicitud={s} onVer={setVistaPrevia} />
            </section>
          )}
          {/* El pie del documento: una línea de lectura mecánica, como la de un pasaporte (decorativa). */}
          <p className={styles.mrz} aria-hidden="true">{lineasMecanicas(s).join("\n")}</p>
        </div>

        {/* Para UCVMM y el puesto la columna queda fija al bajar por la tabla: la decisión siempre a la vista. */}
        <aside className={`${styles.lateral} ${verificacionTabla ? styles.lateralFijo : ""}`}>
          {s.acciones.revisar && <PanelRevision solicitud={s} verificacion={verificacion} onActualizada={onActualizada} />}
          {s.acciones.conflicto_revision && (
            <section className={styles.panel}>
              <h2 className={styles.panelTitulo}>Revisión UCVMM</h2>
              <p className={styles.ayuda}>
                No puedes revisar esta solicitud porque la creaste tú o es de tu agencia. La debe revisar otro
                funcionario de UCVMM.
              </p>
            </section>
          )}
          {s.acciones.finalizar && (
            <PanelPuerto solicitud={s} verificacion={verificacionPuesto} onActualizada={onActualizada} />
          )}
          <ResumenImpedimentos s={s} />

          <HistorialSolicitud eventos={s.eventos} puestoFinalizacion={s.puesto_finalizacion_nombre} />
        </aside>
      </div>

      {documentacionDe && (
        <ModalDocumentacion tripulante={documentacionDe} onCerrar={() => setDocumentacionDe(null)}
          tapado={vistaPrevia !== null}>
          <DocumentosSolicitud solicitud={s} onVer={setVistaPrevia} tripulanteId={documentacionDe.id} />
        </ModalDocumentacion>
      )}
      {vistaPrevia && (
        <ModalPreview solicitudId={s.id} documento={vistaPrevia} onCerrar={() => setVistaPrevia(null)} />
      )}
    </MarcoPagina>
  );
}
