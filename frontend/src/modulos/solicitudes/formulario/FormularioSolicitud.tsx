/**
 * Formulario de Solicitud de Autorización Marítima (Formulario 3), ya con lo
 * que carga PaginaSolicitud. Nueva, o corrección de una devuelta: se precarga
 * todo y los documentos ya cargados se conservan salvo que se reemplacen o se
 * quiten. El estado de los tripulantes y de los documentos va en sus hooks;
 * lo que se envía lo arma `armarEnvio` (envioSolicitud.ts).
 *
 * Una nueva se guarda como borrador en este equipo mientras se llena, y se recupera al
 * volver (24 horas desde el último cambio, borradorSolicitud.ts). Con un trámite elegido,
 * «Volver» regresa a los trámites; desde ahí, al inicio (2026-11-23).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiSolicitudes, type DocumentoSolicitud, type SolicitudDetalle } from "../../../api/solicitudes";
import { EncabezadoPagina } from "../../../components/EncabezadoPagina";
import { IconoAlerta, IconoMas, IconoReloj } from "../../../components/Iconos";
import { useConfirmar } from "../../../components/ModalConfirmacion";
import { ModalPreview } from "../../../components/ModalPreview";
import { useNotificacion } from "../../../components/Notificaciones";
import { TAMANO_MAX_MB } from "../../../utils/archivos";
import type { OpcionBuscable } from "../../../utils/busqueda";
import { mensajeDeError } from "../../../utils/errores";
import { conCartaSubirYBajar, type CasillaFormulario } from "../checklist";
import { ChecklistSolicitud } from "./ChecklistSolicitud";
import { DatosTramite } from "./DatosTramite";
import { DocumentosAdicionales, MAX_ADICIONALES } from "./DocumentosAdicionales";
import { armarEnvio, desdeSolicitud } from "./envioSolicitud";
import { HORAS_BORRADOR, cuandoSeGuardo, restaurar } from "./borradorSolicitud";
import { useBorradorSolicitud } from "./useBorradorSolicitud";
import { avanceFormulario } from "./pasosDelFormulario";
import { AvanceFormulario } from "./AvanceFormulario";
import { fechaISOLocal } from "../../../utils/fechas";
import { formatearFechaHora, tiempoRestante } from "../presentacion";
import { SelectorTramite } from "./SelectorTramite";
import { TarjetaTripulante } from "./TarjetaTripulante";
import type { DatosFormulario } from "./useCargaFormulario";
import { useDocumentosFormulario } from "./useDocumentosFormulario";
import { useTripulantesFormulario } from "./useTripulantesFormulario";
import {
  CABECERA_VACIA, MAX_TRIPULANTES, MESES_VIGENCIA_PASAPORTE, fechaReferencia, validarFormulario, type CabeceraFormulario,
} from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

const SIN_CASILLAS: CasillaFormulario[] = [];

const faltanDocumentos = (n: number) => (n === 1 ? "Falta 1 documento" : `Faltan ${n} documentos`);

interface Props extends DatosFormulario {
  /** La página le pide al formulario qué hace «Volver»: con un trámite elegido, vuelve a los
   *  trámites (devuelve true); si no, la página va al inicio. */
  registrarVolver?: (volver: (() => boolean) | null) => void;
  /** «Empezar de nuevo»: la página borra el borrador y monta el formulario vacío. */
  onEmpezarDeNuevo?: () => void;
}

export function FormularioSolicitud({
  tipos, puestos, paises, agencia, original, claveBorrador, borrador, registrarVolver, onEmpezarDeNuevo,
}: Props) {
  const corrigiendo = original !== null;
  const navegar = useNavigate();
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  // La solicitud devuelta solo da el estado inicial: PaginaSolicitud monta un
  // formulario nuevo para cada solicitud.
  const [precarga] = useState(() => (original ? desdeSolicitud(original) : null));
  // El borrador recuperado, con claves nuevas para esta página, y cuándo se había guardado.
  const [inicio] = useState(() => (borrador ? restaurar(borrador.datos, borrador.archivos) : null));
  const [recuperado] = useState(() => (borrador ? cuandoSeGuardo(borrador.guardadoEn, new Date()) : null));
  const [codigoTramite, setCodigoTramite] = useState(original?.tipo_tramite_codigo ?? inicio?.datos.codigoTramite ?? "");
  const [cabecera, setCabecera] = useState<CabeceraFormulario>(precarga?.cabecera ?? inicio?.datos.cabecera ?? CABECERA_VACIA);
  // Los trámites a la vista para elegir otro («Cambiar» o «Volver»): el resto del formulario se oculta.
  const [eligiendo, setEligiendo] = useState(false);
  const [vistaPrevia, setVistaPrevia] = useState<DocumentoSolicitud | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [intentoEnviar, setIntentoEnviar] = useState(false);
  // Hora que muestra "Fecha y hora de solicitud" (la que queda es la del servidor al enviar).
  const [ahora, setAhora] = useState(() => new Date().toISOString());

  useEffect(() => {
    const reloj = setInterval(() => setAhora(new Date().toISOString()), 30_000);
    return () => clearInterval(reloj);
  }, []);

  const tipo = useMemo(() => tipos.find((t) => t.codigo === codigoTramite) ?? null, [tipos, codigoTramite]);
  const paisesPorCodigo = useMemo(() => new Map(paises.map((p) => [p.codigo, p])), [paises]);
  // Para los selectores con buscador de bandera, país de nacimiento y nacionalidad.
  const opcionesPais = useMemo<OpcionBuscable[]>(
    () => paises.map((p) => ({ valor: p.codigo, texto: p.nombre })),
    [paises],
  );
  const fichas = useTripulantesFormulario(precarga?.tripulantes ?? inicio?.datos.tripulantes);
  const { tripulantes } = fichas;
  // «Subir y bajar» (la operación de Técnico desde el 2026-11-18): la Carta de Responsabilidad de cada tripulante.
  const subirYBajar = !!tipo && conCartaSubirYBajar(tipo, cabecera.subir_y_bajar, cabecera.operacion);
  // La operación de Técnico decide la carta de garantía o el contrato (2026-11-18).
  const operacion = tipo?.pide_operacion ? cabecera.operacion : "";
  const documentos = useDocumentosFormulario(
    tipo, tripulantes, paisesPorCodigo, precarga, subirYBajar, operacion, inicio?.archivos ?? null);
  const { faltantes } = documentos;

  // El borrador en este equipo (solo una nueva: al corregir, `claveBorrador` es null).
  const datosBorrador = useMemo(() => ({ codigoTramite, cabecera, tripulantes }), [codigoTramite, cabecera, tripulantes]);
  const archivosBorrador = useMemo(
    () => ({ nuevos: documentos.nuevos, adicionales: documentos.adicionalesNuevos }),
    [documentos.nuevos, documentos.adicionalesNuevos],
  );
  const { guardado, descartar } = useBorradorSolicitud(claveBorrador, datosBorrador, archivosBorrador, !!borrador);

  // «Volver»: con un trámite elegido, a los trámites (lo escrito queda); si no, la página va al inicio.
  useEffect(() => {
    if (!registrarVolver) return;
    registrarVolver(() => {
      if (corrigiendo || !tipo || eligiendo) return false;
      setEligiendo(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
      return true;
    });
    return () => registrarVolver(null);
  }, [registrarVolver, corrigiendo, tipo, eligiendo]);

  const hoy = fechaISOLocal();
  const errores = useMemo(
    () => (tipo ? validarFormulario(tipo, cabecera, tripulantes, paisesPorCodigo, hoy) : []),
    [tipo, cabecera, tripulantes, paisesPorCodigo, hoy],
  );

  const cambiar = useCallback((campo: keyof CabeceraFormulario, valor: string) => {
    setCabecera((prev) => ({ ...prev, [campo]: valor }));
  }, []);

  // Al quitar un tripulante se descartan también los archivos que se le adjuntaron.
  const { quitar: quitarFicha } = fichas;
  const { descartarDeTripulante } = documentos;
  const quitarTripulante = useCallback((clave: string) => {
    quitarFicha(clave);
    descartarDeTripulante(clave);
  }, [quitarFicha, descartarDeTripulante]);

  /** Al cambiar de trámite, los tripulantes con un rango que el nuevo no admite
   *  pasan al primero que sí admite (p. ej. el trámite de Técnico). Los archivos
   *  del checklist se quitan (el nuevo pide otros): si ya había, se confirma.
   *  Devuelve si se cambió. */
  async function elegirTramite(codigo: string): Promise<boolean> {
    const adjuntos = Object.keys(documentos.nuevos).length;
    if (adjuntos > 0) {
      const cuales = adjuntos === 1 ? "se quitará el documento" : `se quitarán los ${adjuntos} documentos`;
      const ok = await confirmar({
        titulo: "Cambiar de trámite",
        mensaje: `Cada trámite pide sus propios documentos: ${cuales} que adjuntaste en el checklist. `
          + "Los datos, los tripulantes y los documentos adicionales se conservan.",
        textoOk: "Cambiar de trámite",
        peligroso: true,
      });
      if (!ok) return false;
    }
    setCodigoTramite(codigo);
    // Un trámite sin cambio de puerto (o sin «¿Subir y bajar?», o sin operación) no se queda con lo del anterior.
    const nuevo = tipos.find((t) => t.codigo === codigo);
    if (!nuevo?.permite_cambio_puerto) {
      setCabecera((prev) => ({ ...prev, cambio_puerto: "no", puesto_destino_id: "" }));
    }
    if (!nuevo?.permite_subir_y_bajar) {
      setCabecera((prev) => ({ ...prev, subir_y_bajar: "no" }));
    }
    if (!nuevo?.pide_operacion) {
      setCabecera((prev) => ({ ...prev, operacion: "" }));
    }
    if (!nuevo?.pide_dias_sellado) {
      setCabecera((prev) => ({ ...prev, dias_sellado: "" }));
    }
    documentos.descartarTodos();
    fichas.ajustarRangos(nuevo?.rangos_permitidos ?? null);
    return true;
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!tipo || enviando) return;
    setIntentoEnviar(true);
    if (errores.length > 0) {
      mostrar("Revisa los datos marcados antes de enviar.", "aviso");
      return;
    }
    if (faltantes.length > 0) {
      mostrar(`${faltanDocumentos(faltantes.length)} del checklist.`, "aviso");
      return;
    }

    const { datos, archivos, conservados } = armarEnvio(cabecera, tripulantes, documentos);
    setEnviando(true);
    try {
      let resultado: SolicitudDetalle;
      if (original) {
        resultado = await apiSolicitudes.corregir(original.id, { ...datos, documentos_conservados: conservados }, archivos);
        mostrar(`Solicitud ${resultado.numero} corregida y reenviada a revisión.`, "exito", { sello: "reenviada" });
      } else {
        resultado = await apiSolicitudes.crear({ ...datos, codigo_tramite: tipo.codigo }, archivos);
        // Enviada, el borrador sobra.
        await descartar();
        mostrar(`Solicitud ${resultado.numero} enviada a revisión.`, "exito", { sello: "enviada" });
      }
      navegar(`/solicitudes/${resultado.id}`);
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo enviar la solicitud."), "error", 8000);
    } finally {
      setEnviando(false);
    }
  }

  async function empezarDeNuevo() {
    const ok = await confirmar({
      titulo: "Empezar de nuevo",
      mensaje: "Se borra lo que llenaste en esta solicitud, también los archivos adjuntos.",
      textoOk: "Empezar de nuevo",
      peligroso: true,
    });
    if (!ok) return;
    await descartar();
    onEmpezarDeNuevo?.();
  }

  const referenciaVigencia = fechaReferencia(cabecera.fecha_operacion, hoy);
  const plazo = tiempoRestante(original?.plazo_correccion);

  return (
    <>
      <EncabezadoPagina
        titulo={corrigiendo ? `Corregir solicitud ${original.numero ?? ""}` : "Nueva solicitud de autorización"}
        tituloDocumento={corrigiendo ? `Corregir ${original.numero ?? "solicitud"}` : "Nueva solicitud"}
        descripcion={corrigiendo
          ? "Corrige lo indicado en la devolución y reenvía. Los documentos ya cargados se conservan si no los reemplazas."
          : "Formulario No. 3 en línea: elige el trámite y el sistema te indicará exactamente qué datos y documentos debes adjuntar."}
      />

      {original && (
        <div className={styles.bannerDevolucion}>
          <div className={styles.bannerTitulo}><IconoAlerta tamano={15} /> Motivo de la devolución</div>
          <div className={styles.bannerTexto}>{original.motivo_devolucion}</div>
          <div className={styles.bannerPlazo}>
            Plazo para corregir: hasta el {formatearFechaHora(original.plazo_correccion)}
            {!plazo.vencido && <> ({plazo.frase})</>}
          </div>
        </div>
      )}

      {recuperado && (
        <div className={styles.avisoBorrador} role="status">
          <IconoReloj tamano={16} />
          <div className={styles.avisoBorradorTexto}>
            <strong>Recuperamos la solicitud que dejaste sin enviar</strong> (guardada {recuperado}). Se guarda sola
            en este equipo mientras la llenas; si pasan {HORAS_BORRADOR} horas sin cambios, se borra.
          </div>
          <button type="button" className={styles.btnTexto} onClick={empezarDeNuevo}>Empezar de nuevo</button>
        </div>
      )}

      <form onSubmit={enviar} className={styles.form} noValidate>
        {/* El avance de los cuatro pasos obligatorios (rediseño del 2026-11-17): cuánto falta y dónde. */}
        <AvanceFormulario pasos={avanceFormulario({ tipoElegido: !!tipo && !eligiendo, errores, faltantes: faltantes.length })} />

        {/* ── 1. Tipo de trámite ── */}
        <section className={styles.bloque} id="paso-tramite">
          <div className={styles.bloqueTitulo}><span className={styles.paso}>1</span> Tipo de trámite</div>
          <SelectorTramite tipos={tipos} elegido={tipo} fijo={corrigiendo} onElegir={elegirTramite}
            cambiando={eligiendo} onCambiando={setEligiendo}>
            {tipo?.nota && <div className={styles.nota}>{tipo.nota}</div>}
            {tipo?.valida_vigencia && (
              <div className={styles.nota}>
                Este trámite exige pasaporte con <strong>al menos {MESES_VIGENCIA_PASAPORTE} meses de vigencia</strong> a
                partir de la fecha de la operación. Si el seamanbook está vencido, se puede enviar igual: queda señalado.
              </div>
            )}
          </SelectorTramite>
        </section>

        {tipo && !eligiendo && (
          <>
            {/* ── 2. Datos del trámite ── */}
            <DatosTramite
              tipo={tipo}
              cabecera={cabecera}
              agencia={original?.agencia_nombre ?? agencia?.nombre ?? ""}
              fechaSolicitud={original?.created_at ?? ahora}
              puestos={puestos}
              opcionesPais={opcionesPais}
              hoy={hoy}
              onCambiar={cambiar}
            />

            {/* ── 3. Tripulantes ── */}
            <section className={styles.bloque} id="paso-tripulantes">
              <div className={styles.bloqueTitulo}>
                <span className={styles.paso}>3</span> Tripulantes
                <span className={styles.contador}>{tripulantes.length}</span>
              </div>
              <p className={styles.ayudaSeccion}>
                Escribe nombres, apellidos y números de pasaporte y de libreta tal como aparecen en esos
                documentos. Los documentos de cada tripulante se adjuntan en su propia tarjeta: PDF, Word o
                Excel, con un máximo permitido de {TAMANO_MAX_MB} MB por archivo.
              </p>
              {tripulantes.map((t, i) => (
                <TarjetaTripulante
                  key={t.clave}
                  ficha={t}
                  indice={i}
                  puedeQuitar={tripulantes.length > 1}
                  opcionesPais={opcionesPais}
                  paises={paisesPorCodigo}
                  validaVigencia={tipo.valida_vigencia}
                  fechaReferencia={referenciaVigencia}
                  rangosPermitidos={tipo.rangos_permitidos}
                  avisoCustodia={tipo.aviso_custodia}
                  casillas={documentos.casillasPorTripulante.get(t.clave) ?? SIN_CASILLAS}
                  nuevos={documentos.nuevos}
                  existentes={documentos.existentes}
                  contraida={fichas.contraidas.has(t.clave)}
                  onCambiar={fichas.cambiar}
                  onQuitar={quitarTripulante}
                  onAlternar={fichas.alternar}
                  onElegir={documentos.elegir}
                  onDescartar={documentos.descartar}
                  onVer={setVistaPrevia}
                />
              ))}
              {tripulantes.length < MAX_TRIPULANTES ? (
                <button type="button" className={styles.btnAgregar}
                  onClick={() => fichas.agregar(tipo.rangos_permitidos?.[0])}>
                  <IconoMas /> Agregar tripulante
                </button>
              ) : (
                <p className={styles.ayudaSeccion}>
                  Llegaste al máximo de {MAX_TRIPULANTES} tripulantes por solicitud. Si son más, preséntalos en otra
                  solicitud.
                </p>
              )}
            </section>

            {/* ── 4. Documentos de la solicitud + estado por tripulante ── */}
            <ChecklistSolicitud
              documentos={documentos}
              tripulantes={tripulantes}
              onIrATripulante={fichas.irA}
              onVer={setVistaPrevia}
            />

            {/* ── 5. Documentos adicionales ── */}
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}>
                <span className={styles.paso}>5</span> Documentos adicionales (opcional)
                <span className={styles.contador}>
                  {documentos.adicionalesExistentes.length + documentos.adicionalesNuevos.length}
                </span>
              </div>
              <p className={styles.ayudaSeccion}>
                Cartas, oficios u otros soportes, hasta {MAX_ADICIONALES}. PDF, Word o Excel. Máximo permitido:
                {" "}{TAMANO_MAX_MB} MB por archivo.
              </p>
              <DocumentosAdicionales
                existentes={documentos.adicionalesExistentes}
                nuevos={documentos.adicionalesNuevos}
                onAgregar={documentos.agregarAdicionales}
                onQuitarNuevo={documentos.quitarAdicionalNuevo}
                onQuitarExistente={documentos.quitarAdicionalExistente}
                onVer={setVistaPrevia}
              />
            </section>

            {/* ── 6. Observaciones ── */}
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}><span className={styles.paso}>6</span> Observaciones (opcional)</div>
              <label className={styles.campo}>
                {/* El título de la sección no está asociado al campo: este lo nombra para el lector de pantalla. */}
                <span className="sr-only">Observaciones</span>
                <textarea rows={3} maxLength={2000} value={cabecera.observaciones}
                  placeholder={corrigiendo ? "Explica qué corregiste" : "Información adicional para la revisión"}
                  onChange={(e) => cambiar("observaciones", e.target.value)} />
              </label>
            </section>

            {intentoEnviar && errores.length > 0 && (
              <div className={styles.panelErrores} role="alert">
                <div className={styles.panelErroresTitulo}><IconoAlerta tamano={15} /> Revisa antes de enviar</div>
                <ul>{errores.map((e) => <li key={e}>{e}</li>)}</ul>
              </div>
            )}

            <div className={styles.acciones}>
              {guardado && (
                <div className={styles.guardadoBorrador}>Borrador guardado en este equipo {guardado}.</div>
              )}
              {faltantes.length > 0 && (
                <div className={styles.avisoFaltan}>{faltanDocumentos(faltantes.length)} por adjuntar</div>
              )}
              <button type="submit" className={styles.btnEnviar} disabled={enviando}>
                {enviando ? "Enviando…" : corrigiendo ? "Reenviar a revisión" : "Enviar solicitud"}
              </button>
            </div>
          </>
        )}
      </form>

      {vistaPrevia && original && (
        <ModalPreview solicitudId={original.id} documento={vistaPrevia} onCerrar={() => setVistaPrevia(null)} />
      )}
    </>
  );
}
