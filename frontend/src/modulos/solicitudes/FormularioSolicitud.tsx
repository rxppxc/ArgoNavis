/**
 * Formulario de Solicitud de Autorización Marítima (Formulario 3), ya con lo
 * que carga PaginaSolicitud. Nueva, o corrección de una devuelta: se precarga
 * todo y los documentos ya cargados se conservan salvo que se reemplacen o se
 * quiten. El estado de los tripulantes y de los documentos va en sus hooks;
 * lo que se envía lo arma `armarEnvio` (envioSolicitud.ts).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiSolicitudes, type DocumentoSolicitud, type SolicitudDetalle } from "../../api/solicitudes";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { IconoAlerta, IconoMas } from "../../components/Iconos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { ModalPreview } from "../../components/ModalPreview";
import { useNotificacion } from "../../components/Notificaciones";
import { TAMANO_MAX_MB } from "../../utils/archivos";
import { mensajeDeError } from "../../utils/errores";
import type { CasillaFormulario } from "./checklist";
import { ChecklistSolicitud } from "./ChecklistSolicitud";
import { DatosTramite } from "./DatosTramite";
import { DocumentosAdicionales } from "./DocumentosAdicionales";
import { armarEnvio, desdeSolicitud } from "./envioSolicitud";
import { formatearFechaHora, hoyISO, tiempoRestante } from "./presentacion";
import { SelectorTramite } from "./SelectorTramite";
import { TarjetaTripulante } from "./TarjetaTripulante";
import type { DatosFormulario } from "./useCargaFormulario";
import { useDocumentosFormulario } from "./useDocumentosFormulario";
import { useTripulantesFormulario } from "./useTripulantesFormulario";
import { CABECERA_VACIA, fechaReferencia, validarFormulario, type CabeceraFormulario } from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

const SIN_CASILLAS: CasillaFormulario[] = [];

const faltanDocumentos = (n: number) => (n === 1 ? "Falta 1 documento" : `Faltan ${n} documentos`);

export function FormularioSolicitud({ tipos, puestos, paises, agencia, original }: DatosFormulario) {
  const corrigiendo = original !== null;
  const navegar = useNavigate();
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  // La solicitud devuelta solo da el estado inicial: PaginaSolicitud monta un
  // formulario nuevo para cada solicitud.
  const [precarga] = useState(() => (original ? desdeSolicitud(original) : null));
  const [codigoTramite, setCodigoTramite] = useState(original?.tipo_tramite_codigo ?? "");
  const [cabecera, setCabecera] = useState<CabeceraFormulario>(precarga?.cabecera ?? CABECERA_VACIA);
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
  const opcionesPais = useMemo(
    () => paises.map((p) => <option key={p.codigo} value={p.codigo}>{p.nombre}</option>),
    [paises],
  );
  const fichas = useTripulantesFormulario(precarga?.tripulantes);
  const { tripulantes } = fichas;
  const documentos = useDocumentosFormulario(tipo, tripulantes, paisesPorCodigo, precarga);
  const { faltantes } = documentos;

  const hoy = hoyISO();
  // El Form. No. 6 a los restringidos (hoy solo Desembarque, como en el Form. 3).
  const exigeCustodia = !!tipo?.documentos.some((d) => d.condicion === "nacionalidad_restringida");
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
    documentos.descartarTodos();
    fichas.ajustarRangos(tipos.find((t) => t.codigo === codigo)?.rangos_permitidos ?? null);
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
        mostrar(`Solicitud ${resultado.numero} corregida y reenviada a revisión.`, "exito");
      } else {
        resultado = await apiSolicitudes.crear({ ...datos, codigo_tramite: tipo.codigo }, archivos);
        mostrar(`Solicitud ${resultado.numero} enviada a revisión.`, "exito");
      }
      navegar(`/solicitudes/${resultado.id}`);
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo enviar la solicitud."), "error", 8000);
    } finally {
      setEnviando(false);
    }
  }

  const referenciaVigencia = fechaReferencia(cabecera.fecha_operacion, hoy);
  const plazo = tiempoRestante(original?.plazo_correccion);

  return (
    <>
      <EncabezadoPagina
        titulo={corrigiendo ? `Corregir solicitud ${original.numero ?? ""}` : "Nueva solicitud de autorización"}
        tituloDocumento={corrigiendo ? `Corregir ${original.numero ?? "solicitud"}` : "Nueva solicitud"}
        descripcion={corrigiendo
          ? "Corrige lo que indicó UCVMM y reenvía. Los documentos ya cargados se conservan si no los reemplazas."
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

      <form onSubmit={enviar} className={styles.form} noValidate>
        {/* ── 1. Tipo de trámite ── */}
        <section className={styles.bloque}>
          <div className={styles.bloqueTitulo}><span className={styles.paso}>1</span> Tipo de trámite</div>
          <SelectorTramite tipos={tipos} elegido={tipo} fijo={corrigiendo} onElegir={elegirTramite}>
            {tipo?.nota && <div className={styles.nota}>{tipo.nota}</div>}
            {tipo?.valida_vigencia && (
              <div className={styles.nota}>
                Este trámite exige pasaporte y seamanbook <strong>vigentes</strong> a la fecha de la operación.
              </div>
            )}
          </SelectorTramite>
        </section>

        {tipo && (
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
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}>
                <span className={styles.paso}>3</span> Tripulantes
                <span className={styles.contador}>{tripulantes.length}</span>
              </div>
              <p className={styles.ayudaSeccion}>
                Escribe nombres, apellidos y números de pasaporte y de libreta tal como aparecen en esos
                documentos. Los documentos de cada tripulante se adjuntan en su propia tarjeta (PDF, Word o
                Excel, de hasta {TAMANO_MAX_MB} MB cada uno).
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
                  exigeCustodia={exigeCustodia}
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
              <button type="button" className={styles.btnAgregar}
                onClick={() => fichas.agregar(tipo.rangos_permitidos?.[0])}>
                <IconoMas /> Agregar tripulante
              </button>
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
              <div className={styles.bloqueTitulo}><span className={styles.paso}>6</span> Observaciones para UCVMM (opcional)</div>
              <label className={styles.campo}>
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
