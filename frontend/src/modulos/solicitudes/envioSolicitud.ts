/**
 * Ida y vuelta del formulario de solicitud, sin React: la precarga de una
 * solicitud devuelta (desdeSolicitud), las fichas nuevas y lo que se manda al
 * servidor (armarEnvio). Lo usan FormularioSolicitud y sus hooks; lo prueba
 * envioSolicitud.test.ts.
 */
import type {
  AsignacionArchivo, DatosFormularioSolicitud, DocumentoSolicitud, RangoMarino, SolicitudDetalle, TripulanteEntrada,
} from "../../api/solicitudes";
import { claveCasilla, type CasillaFormulario } from "./checklist";
import type { AdicionalNuevo } from "./DocumentosAdicionales";
import { normalizarImo } from "./presentacion";
import { portaLibreta, type CabeceraFormulario, type FichaTripulante } from "./validacionFormulario";

let contadorClaves = 0;

/** Clave estable de un tripulante o de un archivo nuevo (no depende de su posición). */
export function nuevaClave(prefijo: string): string {
  contadorClaves += 1;
  return `${prefijo}${contadorClaves}`;
}

export function fichaVacia(rango: RangoMarino = "marino"): FichaTripulante {
  return {
    clave: nuevaClave("n"), nombre: "", apellido: "", fecha_nacimiento: "",
    pais_nacimiento: "", nacionalidad: "", sexo: "", pasaporte: "", pasaporte_expira: "",
    libreta_marino: "", libreta_expira: "", rango, ocupacion: "",
  };
}

/** Lo que trae una solicitud devuelta para corregirla. */
export interface Precarga {
  cabecera: CabeceraFormulario;
  tripulantes: FichaTripulante[];
  /** Documentos del checklist ya cargados, por clave de casilla. */
  existentes: Record<string, DocumentoSolicitud[]>;
  adicionales: DocumentoSolicitud[];
}

/** Precarga del formulario a partir de una solicitud devuelta. Las
 *  observaciones empiezan vacías: son las de esta corrección. */
export function desdeSolicitud(s: SolicitudDetalle): Precarga {
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

/** Los documentos del formulario, como los lleva useDocumentosFormulario. */
export interface DocumentosElegidos {
  casillas: CasillaFormulario[];
  /** Archivos elegidos ahora, por clave de casilla. */
  nuevos: Record<string, File>;
  /** Ya cargados en la solicitud que se corrige, por clave de casilla. */
  existentes: Record<string, DocumentoSolicitud[]>;
  adicionalesNuevos: AdicionalNuevo[];
  adicionalesExistentes: DocumentoSolicitud[];
}

/** Lo que se manda: los datos, los archivos en el orden de sus asignaciones y,
 *  al corregir, los documentos ya cargados que se conservan. */
export interface Envio {
  datos: DatosFormularioSolicitud;
  archivos: File[];
  conservados: number[];
}

export function armarEnvio(
  cabecera: CabeceraFormulario, tripulantes: FichaTripulante[], documentos: DocumentosElegidos,
): Envio {
  const { casillas, nuevos, existentes, adicionalesNuevos, adicionalesExistentes } = documentos;
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

  // Al corregir se conservan los documentos de las casillas vigentes que no se
  // reemplazaron y los adicionales que no se quitaron.
  const conservados = [
    ...casillas.filter((c) => !nuevos[c.clave]).flatMap((c) => (existentes[c.clave] ?? []).map((d) => d.id)),
    ...adicionalesExistentes.map((d) => d.id),
  ];
  return { datos, archivos, conservados };
}
