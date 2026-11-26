/** Los tipos de la API de solicitudes (hasta el 2026-11-14, en api/solicitudes.ts, que
 *  los reexporta: se siguen importando de ahí). Son el contrato con el backend
 *  (domain/schemas/solicitud.py): un campo nuevo allá va también aquí. */

export type EstadoSolicitud = "review" | "returned" | "approved" | "denied" | "finalized" | "expired";
/** «pasajero» (2026-11-13): un Marino sin libreta. */
export type RangoMarino = "marino" | "pasajero" | "militar" | "tecnico" | "supernumerario" | "superintendente";
export type Sexo = "M" | "F" | "X";
/** La operación del trámite de Técnico, Superintendente o Supernumerario (2026-11-18):
 *  obligatoria ahí, no cambia los documentos. Espejo de OperacionTecnico (models/solicitud.py). */
export const OPERACIONES = ["embarque", "desembarque", "subir_y_bajar"] as const;
export type Operacion = (typeof OPERACIONES)[number];
/** Los días del sellado de Shore Pass (2026-11-18): obligatorios ahí; no cambian los documentos
 *  ni la vigencia. Espejo de DIAS_SELLADO (models/solicitud.py). */
export const DIAS_SELLADO = [5, 15] as const;
export type DiasSellado = (typeof DIAS_SELLADO)[number];
/** «supervision»: solo lectura, las de sus sectores o las de los dos (2026-11-10). */
export type Bandeja = "agencia" | "revision" | "puerto" | "supervision";

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
  // La ocupación salió del formulario el 2026-11-16.
}

/** A qué documento corresponde cada archivo enviado (en el mismo orden).
 *  Sin código = documento adicional, fuera del checklist. */
export interface AsignacionArchivo {
  documento_codigo: string | null;
  indice_tripulante: number | null;
}

export interface DatosFormularioSolicitud {
  puesto_control_id: number | null;
  /** Cambio de puerto (2026-11-13): el nuevo puesto, del mismo sector. null = sin cambio. */
  puesto_destino_id: number | null;
  /** «¿Subir y bajar?» (2026-11-16): el servidor lo descarta si el trámite no lo pregunta. */
  subir_y_bajar: boolean;
  /** La del trámite de Técnico (2026-11-18); el servidor la descarta en los demás. */
  operacion: Operacion | null;
  /** Los de Shore Pass (2026-11-18); el servidor los descarta en los demás. */
  dias_sellado: DiasSellado | null;
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
  /** Cambio de puerto (2026-11-13): el nuevo puesto, donde vale y se finaliza. */
  puesto_destino_nombre: string | null;
  /** La del trámite de Técnico (2026-11-18): null en los demás y en las de antes. */
  operacion: Operacion | null;
  /** Los días del sellado de Shore Pass (2026-11-18): null en los demás y en las de antes. */
  dias_sellado: DiasSellado | null;
  /** El sector de UCVMM que la revisó o, sin revisar, el del puesto (2026-11-22). Solo para
   *  el SNM: a la agencia le llega null. */
  sector_nombre: string | null;
  /** El sector de hoy del puesto, si cambió desde que se revisó. Solo para el SNM. */
  sector_actual_nombre: string | null;
  nombre_buque: string | null;
  imo: string | null;
  fecha_operacion: string;
  cantidad_tripulantes: number;
  creada_por: string | null;
  created_at: string;
  enviada_en: string;
  plazo_correccion: string | null;
  vigente_hasta: string | null;
  /** Las horas que vale desde la aprobación, si se aprobó con esa regla (Urgencia médica, 2026-11-26). */
  horas_vigencia?: number | null;
  aprobada_en: string | null;
  negada_en: string | null;
  finalizada_en: string | null;
  expirada_en: string | null;
  veces_devuelta: number;
  tripulantes_con_alerta: number;
  tiene_nacionalidad_restringida: boolean;
  /** Aprobada fuera del horario laboral (null: sin aprobar). Desde el 2026-11-11
   *  lo ve también la agencia, con el recargo guardado al aprobar. */
  fuera_de_horario: boolean | null;
  /** «B/.20.00»; null si no tiene costo (dentro del horario o aprobada antes del cambio). */
  costo_fuera_de_horario: string | null;
  /** Al buscar un tripulante en la consulta histórica, los que coinciden (2026-11-22). Null en lo demás. */
  tripulantes_encontrados: { nombre: string; pasaporte: string }[] | null;
}

export interface PaginaSolicitudes {
  total: number;
  pagina: number;
  por_pagina: number;
  /** Cantidad por estado con los mismos filtros, sin el de estado. */
  conteos: Partial<Record<EstadoSolicitud, number>>;
  /** Las que se aprobaron alguna vez, con los mismos filtros (2026-11-22). */
  autorizadas: number;
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

/** Filtros de la consulta histórica (2026-11-11): UCVMM, el supervisor de sector y el Administrador. */
export interface ConsultaHistorica {
  texto?: string;
  pasajero?: string;
  agencia_id?: number;
  puesto_id?: number;
  tipo_tramite_id?: number;
  estado?: EstadoSolicitud;
  /** Solo las que se aprobaron alguna vez: vigentes, finalizadas y vencidas sin finalizar (2026-11-22). */
  autorizadas?: boolean;
  fuera_de_horario?: boolean;
  fecha?: "envio" | "operacion";
  desde?: string;
  hasta?: string;
  pagina?: number;
  por_pagina?: number;
}

export interface OpcionFiltro {
  id: number;
  nombre: string;
  activo: boolean;
}

/** Para los filtros de la consulta histórica, también lo desactivado. */
export interface OpcionesHistorico {
  agencias: OpcionFiltro[];
  puestos: OpcionFiltro[];
  tramites: OpcionFiltro[];
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
  /** Solo la traen las solicitudes enviadas antes del 2026-11-16 (salió del formulario). */
  ocupacion: string | null;
  es_panameno: boolean;
  nacionalidad_restringida: boolean;
  /** Verificación de impedimentos de la persona (solo personal SNM; null = sin verificar):
   *  la de UCVMM y la del puesto de control antes de finalizar. */
  con_impedimento: boolean | null;
  con_impedimento_puesto: boolean | null;
  porta_libreta: boolean;
  orden: number;
  pasaporte_vencido: boolean;
  /** Vigente el día de la operación, pero vence antes de 3 meses (2026-11-13). */
  pasaporte_vigencia_corta: boolean;
  /** El seamanbook vencido no impide enviar (2026-11-13): solo se señala. */
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
  /** Opcional (2026-11-11): sin archivo no cuenta como faltante. */
  obligatoria: boolean;
}

export interface EventoSolicitud {
  id: number;
  tipo: "creada" | "corregida" | "impedimentos" | "impedimentos_corregidos"
    | "impedimentos_puesto" | "impedimentos_puesto_corregidos" | "devuelta" | "aprobada" | "negada"
    | "comentario" | "finalizada" | "expirada" | "boleta_generada" | "boleta_anulada";
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
  /** Boleta de recargo (2026-11-16): generar si no hay una vigente; anular la vigente. */
  generar_boleta: boolean;
  anular_boleta: boolean;
  /** El historial completo: versiones, documentos retirados y huellas (2026-11-22). */
  ver_registro: boolean;
}

/** Un valor con su rótulo: («Buque», «AURORA»). */
export type ParRotulado = [string, string];

/** Lo que la agencia había enviado antes de una corrección (2026-11-22), con los nombres de
 *  ese día. Espejo de SalidaVersion. */
export interface VersionSolicitud {
  numero: number;
  enviada_en: string;
  enviada_por: string | null;
  devuelta_en: string | null;
  devuelta_por: string | null;
  motivo: string | null;
  corregida_en: string;
  corregida_por: string | null;
  datos: ParRotulado[];
  tripulantes: { id: number; nombre: string; datos: ParRotulado[] }[];
  /** `documento` null: un adicional. Se abren por su id, también los retirados. */
  documentos: { id: number; documento: string | null; tripulante: string | null; nombre: string }[];
  /** Qué cambió la agencia al corregirla, en palabras. */
  cambios: string[];
}

/** Un archivo de la solicitud con su huella: un documento (vigente o retirado) o una
 *  autorización emitida (2026-11-22). Espejo de SalidaArchivo. */
export interface ArchivoRegistro {
  clase: "documento" | "emitido";
  id: number;
  documento: string;
  tripulante: string | null;
  nombre: string;
  tamano: number;
  tipo_mime: string;
  /** Null: de antes, hasta que se le calcula. */
  sha256: string | null;
  fecha: string;
  por: string | null;
  retirado_en: string | null;
}

/** El historial completo de una solicitud (2026-11-22): solo lo ve el SNM que la revisa. */
export interface RegistroSolicitud {
  versiones: VersionSolicitud[];
  /** Correcciones de antes, que no guardaron lo que se había enviado. */
  sin_version: number;
  archivos: ArchivoRegistro[];
}

/** Un archivo para la vista previa: un documento del expediente o una autorización emitida. */
export interface ArchivoVisible {
  id: number;
  nombre_original: string;
  tipo_mime: string | null;
  emitido?: boolean;
}

/** Una boleta de recargo por atención fuera del horario laboral (2026-11-16). Solo
 *  la ve el personal del SNM: la agencia no (la imprime el SNM y se la entrega). */
export interface BoletaRecargo {
  id: number;
  numero_oficio: string;
  /** "B/.20.00" */
  monto: string;
  generada_en: string;
  generada_por: string | null;
  anulada_en: string | null;
  anulada_por: string | null;
  motivo_anulacion: string | null;
  vigente: boolean;
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
  puesto_destino_id: number | null;
  /** «¿Subir y bajar?» (2026-11-16): la respuesta y si el trámite hace la pregunta. */
  subir_y_bajar: boolean;
  permite_subir_y_bajar: boolean;
  /** Si el trámite pide la operación (2026-11-18: el de Técnico). */
  pide_operacion: boolean;
  /** Si el trámite pide los días del sellado (2026-11-18: Shore Pass). */
  pide_dias_sellado: boolean;
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
  /** Con las anuladas. null para la agencia, que no las ve. */
  boletas: BoletaRecargo[] | null;
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
  puesto_destino_nombre: string | null;
  fecha_operacion: string | null;
  aprobada_en: string | null;
  vigente_hasta: string | null;
  /** Las horas que vale desde la aprobación, si se aprobó con esa regla (Urgencia médica, 2026-11-26). */
  horas_vigencia?: number | null;
  finalizada_en: string | null;
  puesto_finalizacion_nombre: string | null;
  /** Quien escanea puede ver el PDF (la copia de la agencia, 2026-11-14): mientras
   *  valga y hasta 30 días después de la operación. */
  pdf_disponible: boolean;
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

/** Los formatos en que se exportan las estadísticas. */
export type FormatoExportacion = "xlsx" | "pdf" | "csv";

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
  /** De qué sectores son las cifras (2026-11-10): "Todos los sectores", "Sector Pacífico"… */
  alcance: string;
  /** El sector elegido, si se eligió uno. */
  sector_id: number | null;
  /** Los que puede elegir quien consulta (uno solo si ve un sector). */
  sectores: { id: number; nombre: string }[];
  /** Si ve el uso del sistema: solo quien ve todos los sectores. */
  uso_del_sistema: boolean;
}
