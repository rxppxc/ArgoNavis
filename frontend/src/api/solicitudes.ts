import { clienteApi, guardarComoArchivo } from "./client";
import type {
  Bandeja, ConsultaBandeja, ConsultaHistorica, DatosCorregirSolicitud, DatosCrearSolicitud, DocumentoSolicitud,
  EstadisticasSolicitudes, FormatoExportacion, OpcionesHistorico, PaginaSolicitudes, ResultadoImpedimento,
  SolicitudDetalle, VerificacionAutorizacion,
} from "./tiposSolicitudes";

export type * from "./tiposSolicitudes";

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
function parametros(consulta: ConsultaBandeja | ConsultaHistorica): Record<string, string | number | boolean> {
  return Object.fromEntries(
    Object.entries(consulta).filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== false),
  ) as Record<string, string | number | boolean>;
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

  /** Consulta histórica (personal del SNM): las que ve, de cualquier año. Los filtros van en
   *  el cuerpo (POST): el pasajero buscado no queda en los logs del servidor (2026-11-14). */
  historico: (consulta: ConsultaHistorica) =>
    clienteApi.post<PaginaSolicitudes>("/solicitudes/historico", parametros(consulta))
      .then((r) => r.data),

  opcionesHistorico: () =>
    clienteApi.get<OpcionesHistorico>("/solicitudes/historico/opciones").then((r) => r.data),

  /** Lo que cumple los filtros, en Excel con la identidad del SNM (lo arma el servidor). */
  async exportarHistorico(consulta: ConsultaHistorica): Promise<string> {
    // Todo lo que cumple los filtros, no una página.
    const { data, headers } = await clienteApi.post<Blob>(
      "/solicitudes/historico/exportar",
      parametros({ ...consulta, pagina: undefined, por_pagina: undefined }),
      { responseType: "blob", timeout: 120_000 },
    );
    const nombre = /filename="([^"]+)"/.exec(String(headers["content-disposition"] ?? ""))?.[1]
      ?? "Consulta-historica.xlsx";
    guardarComoArchivo(data, nombre);
    return nombre;
  },

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

  /** Boleta de recargo (2026-11-16): con el número de oficio, que no se repite. */
  generarBoleta: (id: number, numeroOficio: string) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/boletas`, { numero_oficio: numeroOficio })
      .then((r) => r.data),

  /** Como en un talonario: queda anulada, con su número, y se puede generar otra. */
  anularBoleta: (id: number, boletaId: number, motivo: string) =>
    clienteApi.post<SolicitudDetalle>(`/solicitudes/${id}/boletas/${boletaId}/anular`, { motivo })
      .then((r) => r.data),

  async descargarBoleta(id: number, boletaId: number): Promise<void> {
    const { data, headers } = await clienteApi.get<Blob>(`/solicitudes/${id}/boletas/${boletaId}/boleta.pdf`, {
      responseType: "blob",
      timeout: 120_000,
    });
    const nombre = /filename="([^"]+)"/.exec(String(headers["content-disposition"] ?? ""))?.[1];
    guardarComoArchivo(data, nombre ?? `Boleta-recargo-${id}.pdf`);
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

  estadisticas: (desde?: string | null, hasta?: string | null, sectorId?: number | null) =>
    clienteApi.get<EstadisticasSolicitudes>("/solicitudes/estadisticas", {
      params: { desde: desde || undefined, hasta: hasta || undefined, sector_id: sectorId ?? undefined },
    }).then((r) => r.data),

  /** Las estadísticas del periodo (y el uso del sistema) en Excel, PDF o CSV, con
   *  la identidad del SNM; las arma el servidor. `unidad`: la serie que se ve en
   *  pantalla, que va en el PDF y en la hoja «Resumen». */
  async exportarEstadisticas(formato: FormatoExportacion, desde: string | null, hasta: string | null,
    unidad: "dia" | "mes" | "anio", sectorId: number | null = null): Promise<string> {
    const { data, headers } = await clienteApi.get<Blob>("/solicitudes/estadisticas/exportar", {
      params: { formato, desde: desde || undefined, hasta: hasta || undefined, unidad, sector_id: sectorId ?? undefined },
      responseType: "blob",
      timeout: 120_000,
    });
    const nombre = /filename="([^"]+)"/.exec(String(headers["content-disposition"] ?? ""))?.[1]
      ?? `Estadisticas-autorizaciones.${formato}`;
    guardarComoArchivo(data, nombre);
    return nombre;
  },

  /** Verificación pública del QR (no requiere sesión). */
  verificar: (codigo: string) =>
    clienteApi.get<VerificacionAutorizacion>(`/verificacion/${encodeURIComponent(codigo)}`).then((r) => r.data),
  /** El PDF de la autorización para quien escanea el QR, sin sesión (2026-11-14): se
   *  abre con un enlace normal, para que el celular lo muestre en su visor. */
  urlPdfPublico: (codigo: string) =>
    `${clienteApi.defaults.baseURL ?? ""}/verificacion/${encodeURIComponent(codigo)}/autorizacion.pdf`,
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
