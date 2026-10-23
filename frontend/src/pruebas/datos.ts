/** Datos de prueba que comparten las pruebas unitarias del frontend. */
import type { DocumentoSolicitud, SolicitudDetalle, TripulanteSolicitud } from "../api/solicitudes";
import type { TipoTramite } from "../api/tramites";

/** Un trámite completo con valores neutros: cada prueba cambia solo lo que mira. */
export function tramiteDePrueba(cambios: Partial<TipoTramite> = {}): TipoTramite {
  return {
    id: 1, codigo: "T", nombre: "Trámite de prueba", formulario: "formulario_3",
    requiere_buque: false, requiere_puerto: false, requiere_puerto_desembarque: false,
    requiere_motivo: false, requiere_clinica: false, valida_vigencia: true, rangos_permitidos: null,
    aviso_custodia: false, descripcion: null, nota: null, orden: 1, activo: true, documentos: [],
    ...cambios,
  };
}

/** Un tripulante ya registrado: marino panameño, sin verificar impedimentos. */
export function tripulanteDePrueba(cambios: Partial<TripulanteSolicitud> = {}): TripulanteSolicitud {
  return {
    id: 1, nombre: "Juan", apellido: "Pérez", nombre_completo: "Juan Pérez", fecha_nacimiento: "1988-03-14",
    pais_nacimiento: "PAN", pais_nacimiento_nombre: "Panamá", nacionalidad: "PAN", nacionalidad_nombre: "Panamá",
    sexo: "M", pasaporte: "PA1234567", pasaporte_expira: "2030-05-01",
    libreta_marino: "SB-778812", libreta_expira: "2029-11-30", rango: "marino", ocupacion: "Primer oficial",
    es_panameno: true, nacionalidad_restringida: false, con_impedimento: null, porta_libreta: true, orden: 1,
    pasaporte_vencido: false, libreta_vencida: false,
    ...cambios,
  };
}

/** Un documento del checklist ya cargado, de la solicitud (sin tripulante). */
export function documentoDePrueba(cambios: Partial<DocumentoSolicitud> = {}): DocumentoSolicitud {
  return {
    id: 1, nombre_original: "documento.pdf", tamano: 1024, tipo_mime: "application/pdf",
    documento_id: 1, documento_codigo: "DOC", documento_nombre: "Documento", tripulante_id: null,
    created_at: "2026-10-20T15:00:00Z",
    ...cambios,
  };
}

/** Una solicitud devuelta a corrección, sin tripulantes ni documentos. */
export function solicitudDePrueba(cambios: Partial<SolicitudDetalle> = {}): SolicitudDetalle {
  return {
    id: 1, numero: "PRUEBA-0001", titulo: "Trámite de prueba", estado: "returned",
    tipo_tramite_codigo: "T", tipo_tramite_nombre: "Trámite de prueba",
    agencia_id: 1, agencia_nombre: "Agencia de prueba", puesto_nombre: "Puesto de prueba",
    nombre_buque: null, imo: null, fecha_operacion: "2026-11-02", cantidad_tripulantes: 0,
    creada_por: null, created_at: "2026-10-20T15:00:00Z", enviada_en: "2026-10-20T15:00:00Z",
    plazo_correccion: "2026-10-23T15:00:00Z", vigente_hasta: null, aprobada_en: null, negada_en: null,
    finalizada_en: null, expirada_en: null, veces_devuelta: 1, tripulantes_con_alerta: 0,
    tiene_nacionalidad_restringida: false,
    tipo_tramite_nota: null, tipo_tramite_aviso_custodia: false,
    requiere_buque: false, requiere_puerto: false, requiere_puerto_desembarque: false,
    requiere_motivo: false, requiere_clinica: false, valida_vigencia: true,
    puesto_control_id: 1, bandera: null, bandera_nombre: null, nombre_puerto: null, puerto_desembarque: null,
    motivo: null, clinica_hospital: null, observaciones: null,
    impedimentos_verificados: false, comentario_impedimentos: null,
    impedimentos_verificados_en: null, impedimentos_verificados_por: null,
    motivo_devolucion: "Motivo de prueba", observacion_aprobacion: null, aprobada_por: null,
    motivo_negacion: null, comentario_finalizacion: null, finalizada_por: null,
    puesto_finalizacion_id: null, puesto_finalizacion_nombre: null,
    tripulantes: [], documentos: [], checklist: [], eventos: [],
    acciones: { corregir: true, revisar: false, finalizar: false, descargar_autorizacion: false, conflicto_revision: false },
    ...cambios,
  };
}
