import { clienteApi, guardarComoArchivo } from "./client";

export type EstadoSolicitud = "review" | "returned" | "approved" | "denied" | "finalized" | "expired";
export type RangoMarino = "marino" | "militar" | "tecnico" | "supernumerario" | "superintendente";
export type Sexo = "M" | "F" | "X";
export type Bandeja = "agencia" | "revision" | "puerto";

/** Ficha del tripulante tal como se envía (formulario de registro del marino). */
export interface TripulanteEntrada {
  id?: number | null;            // solo al corregir: tripulante ya registrado
  nombre: string;
  apellido: string;
  fecha_nacimiento: string;
  pais_nacimiento: string;
  nacionalidad: string;
  sexo: Sexo | "";
  pasaporte: string;
  pasaporte_expira: string;
  libreta_marino: string | null;  // seamanbook
  libreta_expira: string | null;
  rango: RangoMarino;
  ocupacion: string;
}

/** A qué documento corresponde cada archivo enviado (en el mismo orden).
 *  Sin código = documento adicional, fuera del checklist. */
export interface AsignacionArchivo {
  documento_codigo: string | null;
  indice_tripulante: number | null;
}

export interface DatosFormularioSolicitud {
  puesto_control_id: number | null;
  fecha_operacion: string | null;
  nombre_buque: string | null;
  imo: string | null;
  bandera: string | null;
  nombre_puerto: string | null;
  puerto_desembarque: string | null;
  motivo: string | null;
  clinica_hospital: string | null;
  observaciones: string | null;
  tripulantes: TripulanteEntrada[];
  asignaciones: AsignacionArchivo[];
}

export interface DatosCrearSolicitud extends DatosFormularioSolicitud {
  codigo_tramite: string;
}

export interface DatosCorregirSolicitud extends DatosFormularioSolicitud {
  documentos_conservados: number[];
}

export interface SolicitudResumen {
  id: number;
  numero: string | null;
  titulo: string;
  estado: EstadoSolicitud;
  tipo_tramite_codigo: string;
  tipo_tramite_nombre: string;
  agencia_id: number;
  agencia_nombre: string;
  puesto_nombre: string;
  nombre_buque: string | null;
  imo: string | null;
  fecha_operacion: string;
  cantidad_tripulantes: number;
  creada_por: string | null;
  created_at: string;
  enviada_en: string;
  plazo_correccion: string | null;
  vigente_hasta: string | null;
  aprobada_en: string | null;
  negada_en: string | null;
  finalizada_en: string | null;
  expirada_en: string | null;
  veces_devuelta: number;
  tripulantes_con_alerta: number;
  tiene_nacionalidad_restringida: boolean;
  /** Aprobada por UCVMM fuera del horario laboral (solo personal SNM: a la agencia le llega null). */
  fuera_de_horario: boolean | null;
}

export interface PaginaSolicitudes {
  total: number;
  pagina: number;
  por_pagina: number;
  /** Cantidad por estado con los mismos filtros, sin el de estado. */
  conteos: Partial<Record<EstadoSolicitud, number>>;
  items: SolicitudResumen[];
}

export interface ConsultaBandeja {
  estado?: EstadoSolicitud;
  texto?: string;
  desde?: string;
  hasta?: string;
  pagina?: number;
  por_pagina?: number;
}

export interface TripulanteSolicitud {
  id: number;
  nombre: string;
  apellido: string;
  nombre_completo: string;
  fecha_nacimiento: string;
  pais_nacimiento: string;
  pais_nacimiento_nombre: string | null;
  nacionalidad: string;
  nacionalidad_nombre: string | null;
  sexo: Sexo;
  pasaporte: string;
  pasaporte_expira: string;
  libreta_marino: string | null;
  libreta_expira: string | null;
  rango: RangoMarino;
  ocupacion: string;
  es_panameno: boolean;
  nacionalidad_restringida: boolean;
  /** Verificación de impedimentos de la persona (solo personal SNM; null = sin verificar):
   *  la de UCVMM y la del puesto de control antes de finalizar. */
  con_impedimento: boolean | null;
  con_impedimento_puesto: boolean | null;
  porta_libreta: boolean;
  orden: number;
  pasaporte_vencido: boolean;
  libreta_vencida: boolean;
}

export interface DocumentoSolicitud {
  id: number;
  nombre_original: string;
  tamano: number;
  tipo_mime: string | null;
  documento_id: number | null;       // nulo = documento adicional
  documento_codigo: string | null;
  documento_nombre: string | null;
  tripulante_id: number | null;
  created_at: string;
}

export interface CasillaSolicitud {
  documento_id: number;
  documento_codigo: string;
  documento_nombre: string;
  alcance: "solicitud" | "marino";
  tripulante_id: number | null;
  tripulante_nombre: string | null;
  documento_ids: number[];
  cubierta: boolean;
}

export interface EventoSolicitud {
  id: number;
  tipo: "creada" | "corregida" | "impedimentos" | "impedimentos_corregidos"
    | "impedimentos_puesto" | "impedimentos_puesto_corregidos" | "devuelta" | "aprobada" | "negada"
    | "comentario" | "finalizada" | "expirada";
  estado_anterior: EstadoSolicitud | null;
  estado_nuevo: EstadoSolicitud | null;
  comentario: string | null;
  usuario_nombre: string | null;
  creado_en: string;
}

export interface AccionesSolicitud {
  corregir: boolean;
  revisar: boolean;
  finalizar: boolean;
  descargar_autorizacion: boolean;
  /** Podría revisar, pero la creó o es de su agencia (separación de funciones). */
  conflicto_revision: boolean;
}

export interface SolicitudDetalle extends SolicitudResumen {
  tipo_tramite_nota: string | null;
  /** Al aprobar se avisa que se debe tramitar la custodia de los restringidos. */
  tipo_tramite_aviso_custodia: boolean;
  requiere_buque: boolean;
  requiere_puerto: boolean;
  requiere_puerto_desembarque: boolean;
  requiere_motivo: boolean;
  requiere_clinica: boolean;
  valida_vigencia: boolean;
  puesto_control_id: number;
  bandera: string | null;
  bandera_nombre: string | null;
  nombre_puerto: string | null;
  puerto_desembarque: string | null;
  motivo: string | null;
  clinica_hospital: string | null;
  observaciones: string | null;
  impedimentos_verificados: boolean;
  comentario_impedimentos: string | null;
  impedimentos_verificados_en: string | null;
  impedimentos_verificados_por: string | null;
  /** La del puesto de control, aparte de la de UCVMM: se exige antes de finalizar. */
  impedimentos_puesto_verificados: boolean;
  comentario_impedimentos_puesto: string | null;
  impedimentos_puesto_en: string | null;
  impedimentos_puesto_por: string | null;
  motivo_devolucion: string | null;
  observacion_aprobacion: string | null;
  aprobada_por: string | null;
  motivo_negacion: string | null;
  comentario_finalizacion: string | null;
  finalizada_por: string | null;
  /** Dónde se finalizó: el autorizado (antes del 30/10/2026 podía ser otro). */
  puesto_finalizacion_id: number | null;
  puesto_finalizacion_nombre: string | null;
  tripulantes: TripulanteSolicitud[];
  documentos: DocumentoSolicitud[];
  checklist: CasillaSolicitud[];
  eventos: EventoSolicitud[];
  acciones: AccionesSolicitud;
}

export interface ResultadoImpedimento {
  tripulante_id: number;
  con_impedimento: boolean;
}

export interface VerificacionAutorizacion {
  valida: boolean;
  estado: EstadoSolicitud;
  numero: string | null;
  tipo_tramite: string | null;
  agencia_nombre: string | null;
  nombre_buque: string | null;
  imo: string | null;
  bandera: string | null;
  puesto_nombre: string | null;
  fecha_operacion: string | null;
  aprobada_en: string | null;
  vigente_hasta: string | null;
  finalizada_en: string | null;
  puesto_finalizacion_nombre: string | null;
  tripulantes: { nombre_completo: string; nacionalidad: string | null; pasaporte: string | null; rango: RangoMarino | null }[];
}

/** Una autorización aprobada por UCVMM fuera del horario laboral (estadísticas). */
export interface OperacionFueraHorario {
  id: number;
  numero: string | null;
  tipo_tramite: string;
  puesto: string;
  aprobada_en: string;
  aprobada_por: string | null;
}

/** Lo que pasó en un día ("2026-10-05"), un mes ("2026-10") o un año ("2026"):
 *  cada cifra cuenta cuando ocurrió. */
export interface FilaSerie {
  periodo: string;
  recibidas: number;
  aprobadas: number;
  negadas: number;
  expiradas: number;
  finalizadas: number;
  /** Aprobadas fuera del horario laboral. */
  fuera_horario: number;
}

export interface EstadisticasSolicitudes {
  recibidas: number;
  por_estado: Partial<Record<EstadoSolicitud, number>>;
  aprobadas: number;
  negadas: number;
  expiradas: number;
  finalizadas: number;
  horas_promedio_resolucion: number | null;
  /** Aprobadas por UCVMM fuera del horario laboral. */
  aprobadas_fuera_horario: number;
  /** El horario laboral, en palabras ("lunes a viernes, de 07:00 a 15:00"). */
  horario_laboral: string;
  /** Las más recientes (hasta 50). */
  operaciones_fuera_horario: OperacionFueraHorario[];
  /** Aprobadas por día de la semana (1 = lunes … 7 = domingo) y hora, en hora
   *  de Panamá: el mapa de horas. Solo las casillas con alguna. */
  aprobadas_por_hora: { dia: number; hora: number; total: number }[];
  por_tipo: { codigo: string; nombre: string; recibidas: number; aprobadas: number; negadas: number; expiradas: number }[];
  /** La misma serie por día (los últimos 31 del periodo), por mes (hasta 12) y por año (hasta 10). */
  por_dia: FilaSerie[];
  por_mes: FilaSerie[];
  por_anio: FilaSerie[];
  por_puesto: { puesto: string; aprobadas: number; finalizadas: number; expiradas: number }[];
}

function formularioMultipart(datos: unknown, archivos: File[]): FormData {
  const fd = new FormData();
  fd.append("solicitud", JSON.stringify(datos));
  archivos.forEach((a) => fd.append("files", a));
  return fd;
}

const OPCIONES_SUBIDA = {
  headers: { "Content-Type": "multipart/form-data" },
  timeout: 300_000,
};

/** Quita los filtros vacíos para no mandarlos en la query string. */
function parametros(consulta: ConsultaBandeja): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(consulta).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ) as Record<string, string | number>;
}

export const apiSolicitudes = {
  /** Envía la solicitud con su expediente. Los archivos van en el mismo orden
   *  que `datos.asignaciones`; el backend rechaza si falta alguno del checklist. */
  crear: (datos: DatosCrearSolicitud, archivos: File[]) =>
    clienteApi.post<SolicitudDetalle>("/solicitudes", formularioMultipart(datos, archivos), OPCIONES_SUBIDA)
      .then((r) => r.data),

  corregir: (id: number, datos: DatosCorregirSolicitud, archivos: File[]) =>
    clienteApi.put<SolicitudDetalle>(`/solicitudes/${id}`, formularioMultipart(datos, archivos), OPCIONES_SUBIDA)
      .then((r) => r.data),

  /** Bandeja paginada: la agencia del usuario, la cola de UCVMM o la del puesto de control. */
  bandeja: (bandeja: Bandeja, consulta: ConsultaBandeja) =>
    clienteApi.get<PaginaSolicitudes>(`/solicitudes/${bandeja}`, { params: parametros(consulta) })
      .then((r) => r.data),

  obtener: (id: number) =>
    clienteApi.get<SolicitudDetalle>(`/solicitudes/${id}`).then((r) => r.data),

  /** Verificación de impedimentos por tripulante: van todos los de la solicitud. */
  /** `motivoCorreccion` solo al corregir una verificación ya registrada. */
  registrarImpedimentos: (id: number, tripulantes: ResultadoImpedimento[], comentario: string | null,
    motivoCorreccion: string | null = null) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/impedimentos`,
      { tripulantes, comentario, motivo_correccion: motivoCorreccion })
      .then((r) => r.data),

  aprobar: (id: number, observacion: string | null) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/aprobar`, { observacion }).then((r) => r.data),

  devolver: (id: number, motivo: string) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/devolver`, { motivo }).then((r) => r.data),

  negar: (id: number, motivo: string) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/negar`, { motivo }).then((r) => r.data),


  /** La verificación de impedimentos del puesto de control, obligatoria antes de finalizar. */
  registrarImpedimentosPuesto: (id: number, tripulantes: ResultadoImpedimento[], comentario: string | null,
    motivoCorreccion: string | null = null) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/impedimentos-puesto`,
      { tripulantes, comentario, motivo_correccion: motivoCorreccion })
      .then((r) => r.data),

  /** Cierra la autorización en el puesto autorizado (no se finaliza en otro). */
  finalizar: (id: number, comentario: string) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/finalizar`, { comentario }).then((r) => r.data),

  /** Un documento del expediente como blob: exige la sesión (un <a href>
   *  directo saldría sin la cabecera Authorization). Cada consulta queda en
   *  la bitácora como vista previa o descarga. */
  obtenerDocumento: (id: number, documentoId: number, descargar = false) =>
    clienteApi.get<Blob>(`/solicitudes/${id}/documentos/${documentoId}`, {
      params: descargar ? { descargar: true } : undefined,
      responseType: "blob",
      timeout: 300_000,
    }).then((r) => r.data),

  async descargarDocumento(id: number, documento: Pick<DocumentoSolicitud, "id" | "nombre_original">): Promise<void> {
    const blob = await apiSolicitudes.obtenerDocumento(id, documento.id, true);
    guardarComoArchivo(blob, documento.nombre_original);
  },

  async descargarAutorizacion(id: number, numero: string | null): Promise<void> {
    const { data, headers } = await clienteApi.get<Blob>(`/solicitudes/${id}/autorizacion.pdf`, {
      responseType: "blob",
      timeout: 120_000,
    });
    // El nombre lo da el servidor: el personal del SNM recibe la copia interna ("-interna.pdf").
    const nombre = /filename="([^"]+)"/.exec(String(headers["content-disposition"] ?? ""))?.[1];
    guardarComoArchivo(data, nombre ?? `Autorizacion-${numero ?? id}.pdf`);
  },

  estadisticas: (desde?: string | null, hasta?: string | null) =>
    clienteApi.get<EstadisticasSolicitudes>("/solicitudes/estadisticas", {
      params: { desde: desde || undefined, hasta: hasta || undefined },
    }).then((r) => r.data),

  /** Verificación pública del QR (no requiere sesión). */
  verificar: (codigo: string) =>
    clienteApi.get<VerificacionAutorizacion>(`/verificacion/${encodeURIComponent(codigo)}`).then((r) => r.data),
};

/** Si una acción chocó con un cambio de estado (409: otra persona ya la decidió o
 *  la finalizó, venció el plazo…), vuelve a pedir el expediente para mostrar cómo
 *  quedó, en vez de dejar en pantalla botones que ya no corresponden. */
export async function releerSiCambio(error: unknown, id: number, alReleer: (s: SolicitudDetalle) => void): Promise<void> {
  if ((error as { response?: { status?: number } } | null)?.response?.status !== 409) return;
  try {
    alReleer(await apiSolicitudes.obtener(id));
  } catch {
    // Queda lo que hay en pantalla: el aviso del error ya se mostró.
  }
}
