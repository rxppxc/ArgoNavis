/**
 * Formulario de Solicitud de Autorización Marítima (Formulario 3).
 *
 * Dos modos:
 *  - `/new`: un usuario de la agencia crea la solicitud (a nombre de su agencia).
 *  - `/solicitudes/:id/corregir`: la agencia corrige una solicitud que UCVMM
 *    devolvió. Se precarga todo; los documentos ya cargados se conservan
 *    salvo que se reemplacen o se quiten.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiAutenticacion } from "../../api/auth";
import { apiCatalogos, type Pais, type PuestoMini } from "../../api/catalogos";
import {
  apiSolicitudes, type AsignacionArchivo, type DatosFormularioSolicitud, type DocumentoSolicitud,
  type RangoMarino, type SolicitudDetalle, type TripulanteEntrada,
} from "../../api/solicitudes";
import { apiTramites, type TipoTramite } from "../../api/tramites";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { ModalPreview } from "../../components/ModalPreview";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoAlerta, IconoMas } from "../../components/Iconos";
import type { CatalogoMini } from "../../types";
import { mensajeDeError } from "../../utils/errores";
import { TAMANO_MAX_MB, validarArchivos } from "../../utils/archivos";
import { ChecklistDocumentos } from "./ChecklistDocumentos";
import { claveCasilla, construirCasillas, type CasillaFormulario } from "./checklist";
import { DocumentosAdicionales, MAX_ADICIONALES, type AdicionalNuevo } from "./DocumentosAdicionales";
import { AYUDA_CAMPOS_TRAMITE, formatearFechaHora, hoyISO, normalizarImo, tiempoRestante } from "./presentacion";
import { SelectorTramite } from "./SelectorTramite";
import { TarjetaTripulante } from "./TarjetaTripulante";
import {
  CABECERA_VACIA, fechaReferencia, operacionMaxima, portaLibreta, validarFormulario,
  type CabeceraFormulario, type FichaTripulante,
} from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

let contadorClaves = 0;

function nuevaClave(prefijo: string): string {
  contadorClaves += 1;
  return `${prefijo}${contadorClaves}`;
}

function fichaVacia(rango: RangoMarino = "marino"): FichaTripulante {
  return {
    clave: nuevaClave("n"), nombre: "", apellido: "", fecha_nacimiento: "",
    pais_nacimiento: "", nacionalidad: "", sexo: "", pasaporte: "", pasaporte_expira: "",
    libreta_marino: "", libreta_expira: "", rango, ocupacion: "",
  };
}

const SIN_CASILLAS: CasillaFormulario[] = [];
const SIN_EXISTENTES: Record<string, DocumentoSolicitud[]> = {};

/** Precarga del formulario a partir de una solicitud devuelta. */
function desdeSolicitud(s: SolicitudDetalle): {
  cabecera: CabeceraFormulario;
  tripulantes: FichaTripulante[];
  existentes: Record<string, DocumentoSolicitud[]>;
  adicionales: DocumentoSolicitud[];
} {
  const cabecera: CabeceraFormulario = {
    puesto_control_id: String(s.puesto_control_id),
    fecha_operacion: s.fecha_operacion,
    nombre_buque: s.nombre_buque ?? "",
    imo: s.imo ?? "",
    bandera: s.bandera ?? "",
    nombre_puerto: s.nombre_puerto ?? "",
    puerto_desembarque: s.puerto_desembarque ?? "",
    motivo: s.motivo ?? "",
    clinica_hospital: s.clinica_hospital ?? "",
    observaciones: "",
  };
  const tripulantes: FichaTripulante[] = s.tripulantes.map((t) => ({
    clave: `t${t.id}`, id: t.id,
    nombre: t.nombre, apellido: t.apellido, fecha_nacimiento: t.fecha_nacimiento,
    pais_nacimiento: t.pais_nacimiento, nacionalidad: t.nacionalidad, sexo: t.sexo,
    pasaporte: t.pasaporte, pasaporte_expira: t.pasaporte_expira,
    libreta_marino: t.libreta_marino ?? "", libreta_expira: t.libreta_expira ?? "",
    rango: t.rango, ocupacion: t.ocupacion,
  }));
  const existentes: Record<string, DocumentoSolicitud[]> = {};
  const adicionales: DocumentoSolicitud[] = [];
  for (const d of s.documentos) {
    if (!d.documento_codigo) {
      adicionales.push(d);
      continue;
    }
    const clave = claveCasilla(d.documento_codigo, d.tripulante_id ? `t${d.tripulante_id}` : null);
    (existentes[clave] ??= []).push(d);
  }
  return { cabecera, tripulantes, existentes, adicionales };
}

export default function PaginaSolicitud() {
  const { id } = useParams<{ id: string }>();
  const solicitudId = id ? Number(id) : null;
  const corrigiendo = solicitudId !== null;
  const navegar = useNavigate();
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  const [tipos, setTipos]       = useState<TipoTramite[]>([]);
  const [puestos, setPuestos]   = useState<PuestoMini[]>([]);
  const [paises, setPaises]     = useState<Pais[]>([]);
  const [agencia, setAgencia]   = useState<CatalogoMini | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [intentoEnviar, setIntentoEnviar] = useState(false);

  const [original, setOriginal] = useState<SolicitudDetalle | null>(null);
  const [codigoTramite, setCodigoTramite] = useState("");
  const [cabecera, setCabecera] = useState<CabeceraFormulario>(CABECERA_VACIA);
  const [tripulantes, setTripulantes] = useState<FichaTripulante[]>(() => [fichaVacia()]);
  const [nuevos, setNuevos] = useState<Record<string, File>>({});
  const [existentes, setExistentes] = useState<Record<string, DocumentoSolicitud[]>>({});
  const [adicionalesNuevos, setAdicionalesNuevos] = useState<AdicionalNuevo[]>([]);
  const [adicionalesExistentes, setAdicionalesExistentes] = useState<DocumentoSolicitud[]>([]);
  const [vistaPrevia, setVistaPrevia] = useState<DocumentoSolicitud | null>(null);
  const [contraidas, setContraidas] = useState<Set<string>>(() => new Set());
  // Hora que muestra "Fecha y hora de solicitud" (la que queda es la del servidor al enviar).
  const [ahora, setAhora] = useState(() => new Date().toISOString());

  useEffect(() => {
    const reloj = setInterval(() => setAhora(new Date().toISOString()), 30_000);
    return () => clearInterval(reloj);
  }, []);

  // ── Carga de catálogos, del perfil (agencia) y de la solicitud, si se corrige ──
  useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const [listaPuestos, listaPaises, perfil] = await Promise.all([
          apiCatalogos.listarPuestos(), apiCatalogos.listarPaises(), apiAutenticacion.perfilActual(),
        ]);
        if (cancelado) return;
        setPuestos(listaPuestos);
        setPaises(listaPaises);
        setAgencia(perfil.agencia);

        if (solicitudId !== null) {
          const s = await apiSolicitudes.obtener(solicitudId);
          if (!s.acciones.corregir) {
            setErrorCarga("Esta solicitud no está disponible para corrección (no está devuelta o el plazo ya venció).");
            return;
          }
          const tipo = await apiTramites.obtener(s.tipo_tramite_codigo);
          if (cancelado) return;
          const precarga = desdeSolicitud(s);
          setOriginal(s);
          setTipos([tipo]);
          setCodigoTramite(tipo.codigo);
          setCabecera(precarga.cabecera);
          setTripulantes(precarga.tripulantes.length ? precarga.tripulantes : [fichaVacia()]);
          setExistentes(precarga.existentes);
          setAdicionalesExistentes(precarga.adicionales);
        } else if (!perfil.agencia) {
          setErrorCarga(
            "Tu usuario no tiene una agencia naviera asignada, así que todavía no puedes enviar solicitudes. "
            + "Pide al administrador que te asigne a tu agencia.",
          );
        } else {
          setTipos(await apiTramites.listar());
        }
      } catch (error) {
        if (!cancelado) setErrorCarga(mensajeDeError(error, "No se pudo cargar el formulario."));
      } finally {
        if (!cancelado) setCargando(false);
      }
    })();
    return () => { cancelado = true; };
  }, [solicitudId]);

  const tipo = useMemo(() => tipos.find((t) => t.codigo === codigoTramite) ?? null, [tipos, codigoTramite]);
  const hoy = hoyISO();
  // El Form. No. 6 a los restringidos (hoy solo Desembarque, como en el Form. 3).
  const exigeCustodia = !!tipo?.documentos.some((d) => d.condicion === "nacionalidad_restringida");
  const ayuda = tipo ? AYUDA_CAMPOS_TRAMITE[tipo.codigo] : undefined;

  const paisesPorCodigo = useMemo(() => new Map(paises.map((p) => [p.codigo, p])), [paises]);
  const opcionesPais = useMemo(
    () => paises.map((p) => <option key={p.codigo} value={p.codigo}>{p.nombre}</option>),
    [paises],
  );

  // ── Checklist ──
  const casillas = useMemo(() => {
    if (!tipo) return [];
    return construirCasillas(
      tipo,
      tripulantes.map((t) => ({
        clave: t.clave,
        nombre: `${t.nombre} ${t.apellido}`.trim() || "Tripulante sin nombre",
        es_panameno: t.nacionalidad === "PAN",
        porta_libreta: portaLibreta(t),
        restringida: paisesPorCodigo.get(t.nacionalidad)?.nacionalidad_restringida ?? false,
      })),
    );
  }, [tipo, tripulantes, paisesPorCodigo]);

  const faltantes = useMemo(
    () => casillas.filter((c) => !nuevos[c.clave] && !(existentes[c.clave]?.length)),
    [casillas, nuevos, existentes],
  );

  // Las casillas de cada tripulante van dentro de su tarjeta; las de la
  // solicitud (lista de tripulantes, carta, reporte médico) en su propia sección.
  const casillasSolicitud = useMemo(() => casillas.filter((c) => c.clave_tripulante === null), [casillas]);
  const casillasPorTripulante = useMemo(() => {
    const grupos = new Map<string, CasillaFormulario[]>();
    for (const c of casillas) {
      if (c.clave_tripulante !== null) grupos.set(c.clave_tripulante, [...(grupos.get(c.clave_tripulante) ?? []), c]);
    }
    return grupos;
  }, [casillas]);
  const faltantesPorTripulante = useMemo(() => {
    const conteo = new Map<string, number>();
    for (const c of faltantes) {
      if (c.clave_tripulante !== null) conteo.set(c.clave_tripulante, (conteo.get(c.clave_tripulante) ?? 0) + 1);
    }
    return conteo;
  }, [faltantes]);
  const faltantesSolicitud = faltantes.filter((c) => c.clave_tripulante === null).length;

  const errores = useMemo(
    () => (tipo ? validarFormulario(tipo, cabecera, tripulantes, paisesPorCodigo, hoy) : []),
    [tipo, cabecera, tripulantes, paisesPorCodigo, hoy],
  );

  // ── Edición ──
  const cambiar = useCallback(<K extends keyof CabeceraFormulario>(campo: K, valor: CabeceraFormulario[K]) => {
    setCabecera((prev) => ({ ...prev, [campo]: valor }));
  }, []);

  const cambiarTripulante = useCallback((clave: string, campo: keyof TripulanteEntrada, valor: string) => {
    setTripulantes((prev) => prev.map((t) => (t.clave === clave ? { ...t, [campo]: valor } : t)));
  }, []);

  const alternarTripulante = useCallback((clave: string) => {
    setContraidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(clave)) siguiente.delete(clave); else siguiente.add(clave);
      return siguiente;
    });
  }, []);

  /** Lleva a la tarjeta de un tripulante (la expande si estaba contraída). */
  function irATripulante(clave: string) {
    setContraidas((prev) => {
      const siguiente = new Set(prev);
      siguiente.delete(clave);
      return siguiente;
    });
    requestAnimationFrame(() => {
      document.getElementById(`tripulante-${clave}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  /** Al cambiar de trámite, los tripulantes con un rango que el nuevo no admite
   *  pasan al primero que sí admite (p. ej. el trámite de Técnico). Los archivos
   *  del checklist se quitan (el nuevo pide otros): si ya había, se confirma.
   *  Devuelve si se cambió. */
  async function elegirTramite(codigo: string): Promise<boolean> {
    const adjuntos = Object.keys(nuevos).length;
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
    setNuevos({});
    const rangos = tipos.find((t) => t.codigo === codigo)?.rangos_permitidos;
    if (rangos?.length) {
      setTripulantes((prev) => prev.map((t) => (rangos.includes(t.rango) ? t : { ...t, rango: rangos[0] })));
    }
    return true;
  }

  const quitarTripulante = useCallback((clave: string) => {
    setTripulantes((prev) => prev.filter((t) => t.clave !== clave));
    setNuevos((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !k.endsWith(`|${clave}`))));
  }, []);

  const elegirArchivo = useCallback((clave: string, archivo: File) => {
    const problema = validarArchivos([archivo]);
    if (problema) {
      mostrar(problema, "error");
      return;
    }
    setNuevos((prev) => ({ ...prev, [clave]: archivo }));
  }, [mostrar]);

  const descartarArchivo = useCallback((clave: string) => {
    setNuevos((prev) => {
      const siguiente = { ...prev };
      delete siguiente[clave];
      return siguiente;
    });
  }, []);

  function agregarAdicionales(archivos: File[]) {
    const problema = validarArchivos(archivos);
    if (problema) {
      mostrar(problema, "error");
      return;
    }
    const libres = MAX_ADICIONALES - adicionalesExistentes.length - adicionalesNuevos.length;
    if (archivos.length > libres) {
      mostrar(`Se admiten hasta ${MAX_ADICIONALES} documentos adicionales por solicitud.`, "aviso");
    }
    const aceptados = archivos.slice(0, Math.max(libres, 0)).map((archivo) => ({ clave: nuevaClave("a"), archivo }));
    setAdicionalesNuevos((prev) => [...prev, ...aceptados]);
  }

  // ── Envío ──
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!tipo || enviando) return;
    setIntentoEnviar(true);
    if (errores.length > 0) {
      mostrar("Revisa los datos marcados antes de enviar.", "aviso");
      return;
    }
    if (faltantes.length > 0) {
      mostrar(`${faltantes.length === 1 ? "Falta 1 documento" : `Faltan ${faltantes.length} documentos`} del checklist.`, "aviso");
      return;
    }

    const indicePorClave = new Map(tripulantes.map((t, i) => [t.clave, i]));
    const conArchivoNuevo = casillas.filter((c) => nuevos[c.clave]);
    const imo = cabecera.imo.trim() ? (normalizarImo(cabecera.imo) ?? cabecera.imo.trim()) : null;
    const texto = (v: string) => v.trim() || null;

    const asignaciones: AsignacionArchivo[] = [
      ...conArchivoNuevo.map((c) => ({
        documento_codigo: c.documento_codigo,
        indice_tripulante: c.clave_tripulante === null ? null : indicePorClave.get(c.clave_tripulante) ?? null,
      })),
      ...adicionalesNuevos.map(() => ({ documento_codigo: null, indice_tripulante: null })),
    ];
    const archivos = [...conArchivoNuevo.map((c) => nuevos[c.clave]), ...adicionalesNuevos.map((a) => a.archivo)];

    const datos: DatosFormularioSolicitud = {
      puesto_control_id: cabecera.puesto_control_id ? Number(cabecera.puesto_control_id) : null,
      fecha_operacion: cabecera.fecha_operacion || null,
      nombre_buque: texto(cabecera.nombre_buque),
      imo,
      bandera: cabecera.bandera || null,
      nombre_puerto: texto(cabecera.nombre_puerto),
      puerto_desembarque: texto(cabecera.puerto_desembarque),
      motivo: texto(cabecera.motivo),
      clinica_hospital: texto(cabecera.clinica_hospital),
      observaciones: texto(cabecera.observaciones),
      tripulantes: tripulantes.map((t): TripulanteEntrada => {
        const conLibreta = portaLibreta(t);
        return {
          id: t.id ?? null,
          nombre: t.nombre.trim(),
          apellido: t.apellido.trim(),
          fecha_nacimiento: t.fecha_nacimiento,
          pais_nacimiento: t.pais_nacimiento,
          nacionalidad: t.nacionalidad,
          sexo: t.sexo,
          pasaporte: t.pasaporte.trim(),
          pasaporte_expira: t.pasaporte_expira,
          libreta_marino: conLibreta ? texto(t.libreta_marino ?? "") : null,
          libreta_expira: conLibreta ? (t.libreta_expira || null) : null,
          rango: t.rango,
          ocupacion: t.ocupacion.trim(),
        };
      }),
      asignaciones,
    };

    setEnviando(true);
    try {
      let resultado: SolicitudDetalle;
      if (solicitudId !== null) {
        // Se conservan los documentos de las casillas vigentes que no se
        // reemplazaron y los adicionales que no se quitaron.
        const conservados = [
          ...casillas.filter((c) => !nuevos[c.clave]).flatMap((c) => (existentes[c.clave] ?? []).map((d) => d.id)),
          ...adicionalesExistentes.map((d) => d.id),
        ];
        resultado = await apiSolicitudes.corregir(solicitudId, { ...datos, documentos_conservados: conservados }, archivos);
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
  const volverA = corrigiendo ? `/solicitudes/${solicitudId}` : "/dashboard";

  if (cargando) {
    return <MarcoPagina volverA={volverA}><div className={styles.estadoCarga}>Cargando formulario…</div></MarcoPagina>;
  }
  if (errorCarga) {
    return (
      <MarcoPagina volverA={volverA}>
        <div className={styles.errorCarga}>
          <IconoAlerta /> {errorCarga}
          {corrigiendo && <Link to={volverA} className={styles.enlace}>Ver la solicitud</Link>}
        </div>
      </MarcoPagina>
    );
  }

  return (
    <MarcoPagina volverA={volverA}>
      <EncabezadoPagina
        titulo={corrigiendo ? `Corregir solicitud ${original?.numero ?? ""}` : "Nueva solicitud de autorización"}
        descripcion={corrigiendo
          ? "Corrige lo que indicó UCVMM y reenvía. Los documentos ya cargados se conservan si no los reemplazas."
          : "Formulario No. 3 en línea: elige el trámite y el sistema te indicará exactamente qué datos y documentos debes adjuntar."}
      />

      {corrigiendo && original && (
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
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}><span className={styles.paso}>2</span> Datos del trámite</div>
              <div className={styles.grid}>
                <div className={styles.campo}>
                  <span>Agencia naviera</span>
                  <input type="text" value={original?.agencia_nombre ?? agencia?.nombre ?? ""} readOnly disabled />
                </div>
                <div className={styles.campo}>
                  <span>Fecha y hora de solicitud</span>
                  <input type="text" value={formatearFechaHora(original?.created_at ?? ahora)} readOnly disabled />
                </div>
                <label className={styles.campo}>
                  <span>Puesto de Control Migratorio *</span>
                  <select value={cabecera.puesto_control_id}
                    onChange={(e) => cambiar("puesto_control_id", e.target.value)}>
                    <option value="">{puestos.length ? "Selecciona…" : "No hay puestos configurados"}</option>
                    {puestos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                </label>
                <label className={styles.campo}>
                  <span>Fecha de la operación en puerto *</span>
                  <input type="date" min={hoy} max={operacionMaxima(hoy)} value={cabecera.fecha_operacion}
                    onChange={(e) => cambiar("fecha_operacion", e.target.value)} />
                </label>
                {tipo.requiere_buque && (
                  <>
                    <label className={styles.campo}>
                      <span>Nombre del buque *</span>
                      <input type="text" maxLength={255} placeholder={ayuda?.buque} value={cabecera.nombre_buque}
                        onChange={(e) => cambiar("nombre_buque", e.target.value)} />
                    </label>
                    <label className={styles.campo}>
                      <span>IMO * <em>(7 dígitos)</em></span>
                      <input type="text" maxLength={20} placeholder="IMO 9074729" value={cabecera.imo}
                        onChange={(e) => cambiar("imo", e.target.value)} />
                    </label>
                    <label className={styles.campo}>
                      <span>Bandera *</span>
                      <select value={cabecera.bandera} onChange={(e) => cambiar("bandera", e.target.value)}>
                        <option value="">Selecciona…</option>
                        {opcionesPais}
                      </select>
                    </label>
                  </>
                )}
                {tipo.requiere_puerto && (
                  <label className={styles.campo}>
                    <span>Nombre del puerto *</span>
                    <input type="text" maxLength={255} placeholder={ayuda?.puerto} value={cabecera.nombre_puerto}
                      onChange={(e) => cambiar("nombre_puerto", e.target.value)} />
                  </label>
                )}
                {tipo.requiere_puerto_desembarque && (
                  <label className={styles.campo}>
                    <span>Puerto de desembarque *</span>
                    <input type="text" maxLength={255} value={cabecera.puerto_desembarque}
                      onChange={(e) => cambiar("puerto_desembarque", e.target.value)} />
                  </label>
                )}
                {tipo.requiere_clinica && (
                  <label className={styles.campo}>
                    <span>Clínica u hospital *</span>
                    <input type="text" maxLength={255} placeholder="Donde será llevado el tripulante"
                      value={cabecera.clinica_hospital}
                      onChange={(e) => cambiar("clinica_hospital", e.target.value)} />
                  </label>
                )}
                {tipo.requiere_motivo && (
                  <label className={styles.campo}>
                    <span>Motivo * <em>(Tribunal ACP, compras, otros)</em></span>
                    <input type="text" maxLength={2000} value={cabecera.motivo}
                      onChange={(e) => cambiar("motivo", e.target.value)} />
                  </label>
                )}
              </div>
            </section>

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
                  casillas={casillasPorTripulante.get(t.clave) ?? SIN_CASILLAS}
                  nuevos={nuevos}
                  existentes={corrigiendo ? existentes : SIN_EXISTENTES}
                  contraida={contraidas.has(t.clave)}
                  onCambiar={cambiarTripulante}
                  onQuitar={quitarTripulante}
                  onAlternar={alternarTripulante}
                  onElegir={elegirArchivo}
                  onDescartar={descartarArchivo}
                  onVer={setVistaPrevia}
                />
              ))}
              <button type="button" className={styles.btnAgregar}
                onClick={() => setTripulantes((prev) => [...prev, fichaVacia(tipo.rangos_permitidos?.[0])])}>
                <IconoMas /> Agregar tripulante
              </button>
            </section>

            {/* ── 4. Documentos de la solicitud + estado por tripulante ── */}
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}>
                <span className={styles.paso}>4</span> Documentos de la solicitud
                <span className={faltantes.length === 0 ? styles.contadorOk : styles.contadorFalta}>
                  {casillas.length - faltantes.length} / {casillas.length} en total
                </span>
              </div>
              <p className={styles.ayudaSeccion}>PDF, Word o Excel, de hasta {TAMANO_MAX_MB} MB cada uno.</p>
              {tripulantes.some((t) => casillasPorTripulante.has(t.clave)) && (
                <div className={styles.resumenTripulantes}>
                  {tripulantes.map((t, i) => {
                    const total = casillasPorTripulante.get(t.clave)?.length ?? 0;
                    if (!total) return null;
                    const faltan = faltantesPorTripulante.get(t.clave) ?? 0;
                    return (
                      <button key={t.clave} type="button" className={styles.resumenTripulante}
                        onClick={() => irATripulante(t.clave)} title="Ir a la tarjeta del tripulante">
                        {i + 1}. {`${t.nombre} ${t.apellido}`.trim() || "Tripulante sin nombre"}
                        {faltan === 0
                          ? <span className={styles.resumenOk}>✓ completo</span>
                          : <span className={styles.resumenFalta}>faltan {faltan}</span>}
                      </button>
                    );
                  })}
                </div>
              )}
              {casillasSolicitud.length > 0 ? (
                <ChecklistDocumentos
                  casillas={casillasSolicitud}
                  nuevos={nuevos}
                  existentes={corrigiendo ? existentes : SIN_EXISTENTES}
                  onElegir={elegirArchivo}
                  onDescartar={descartarArchivo}
                  onVer={setVistaPrevia}
                />
              ) : (
                <div className={styles.sinDocs}>
                  Este trámite no pide documentos de la solicitud: solo los de cada tripulante, en su tarjeta.
                </div>
              )}
              {faltantesSolicitud > 0 && casillasSolicitud.length > 0 && (
                <p className={styles.ayudaSeccion}>
                  {faltantesSolicitud === 1 ? "Falta 1 documento" : `Faltan ${faltantesSolicitud} documentos`} de la solicitud.
                </p>
              )}
            </section>

            {/* ── 5. Documentos adicionales ── */}
            <section className={styles.bloque}>
              <div className={styles.bloqueTitulo}>
                <span className={styles.paso}>5</span> Documentos adicionales (opcional)
                <span className={styles.contador}>{adicionalesExistentes.length + adicionalesNuevos.length}</span>
              </div>
              <DocumentosAdicionales
                existentes={adicionalesExistentes}
                nuevos={adicionalesNuevos}
                onAgregar={agregarAdicionales}
                onQuitarNuevo={(clave) => setAdicionalesNuevos((prev) => prev.filter((a) => a.clave !== clave))}
                onQuitarExistente={(id) => setAdicionalesExistentes((prev) => prev.filter((d) => d.id !== id))}
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
                <div className={styles.avisoFaltan}>
                  {faltantes.length === 1 ? "Falta 1 documento" : `Faltan ${faltantes.length} documentos`} por adjuntar
                </div>
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
    </MarcoPagina>
  );
}
