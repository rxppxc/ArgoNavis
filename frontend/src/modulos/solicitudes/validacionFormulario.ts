/** Validación del formulario de solicitud en el navegador. Espeja las reglas
 *  del backend (que igual vuelve a validar todo) para avisar antes de enviar. */
import type { Pais, PuestoMini } from "../../api/catalogos";
import type { TripulanteEntrada } from "../../api/solicitudes";
import type { TipoTramite } from "../../api/tramites";
import { ETIQUETA_RANGO, RANGOS_CON_LIBRETA, formatearFecha, normalizarImo } from "./presentacion";

export interface CabeceraFormulario {
  puesto_control_id: string;
  /** ¿Cambio de puerto? (2026-11-13) y, con «si», el nuevo puesto. */
  cambio_puerto: "no" | "si";
  puesto_destino_id: string;
  fecha_operacion: string;
  nombre_buque: string;
  imo: string;
  bandera: string;
  nombre_puerto: string;
  puerto_desembarque: string;
  motivo: string;
  clinica_hospital: string;
  observaciones: string;
}

export interface FichaTripulante extends TripulanteEntrada {
  clave: string;
}

export const CABECERA_VACIA: CabeceraFormulario = {
  puesto_control_id: "", cambio_puerto: "no", puesto_destino_id: "", fecha_operacion: "",
  nombre_buque: "", imo: "", bandera: "",
  nombre_puerto: "", puerto_desembarque: "", motivo: "", clinica_hospital: "",
  observaciones: "",
};

/** Mismos límites que el backend (tramite_service.py, DIAS_MAXIMOS_ANTICIPACION
 *  y MAX_TRIPULANTES de solicitud_service.py). */
export const EDAD_MINIMA = 18;
export const NACIMIENTO_MINIMO = "1900-01-01";
export const DIAS_MAXIMOS_ANTICIPACION = 365;
export const MAX_TRIPULANTES = 30;
/** El pasaporte tiene que vencer al menos estos meses después de la operación
 *  (2026-11-13). Espejo de MESES_VIGENCIA_PASAPORTE (models/solicitud.py). */
export const MESES_VIGENCIA_PASAPORTE = 3;

/** Suma años, meses o días a una fecha ISO (AAAA-MM-DD), sin pasar por la zona
 *  horaria. Si el día no existe en el mes de destino (29 de febrero, 30 de
 *  febrero), queda el último del mes, como el backend: el 29/02/2028 no tiene 18
 *  años quien nació el 01/03/2010, y el 30/11 más 3 meses es el 28/02. */
function desplazar(iso: string, { anios = 0, meses = 0, dias = 0 }: { anios?: number; meses?: number; dias?: number }): string {
  const [a, m, d] = iso.split("-").map(Number);
  const mes = m - 1 + meses;   // desde 0; Date.UTC pasa al año siguiente si se sale de 11
  const ultimoDelMes = new Date(Date.UTC(a + anios, mes + 1, 0)).getUTCDate();
  const fecha = new Date(Date.UTC(a + anios, mes, Math.min(d, ultimoDelMes) + dias));
  return fecha.toISOString().slice(0, 10);
}

/** Nacido a más tardar este día para tener EDAD_MINIMA años cumplidos hoy. */
export function nacimientoMaximo(hoy: string): string {
  return desplazar(hoy, { anios: -EDAD_MINIMA });
}

/** Última fecha de operación admitida. */
export function operacionMaxima(hoy: string): string {
  return desplazar(hoy, { dias: DIAS_MAXIMOS_ANTICIPACION });
}

/** Día contra el que se juzga la vigencia: el de la operación, o hoy si fuera anterior. */
export function fechaReferencia(fechaOperacion: string, hoy: string): string {
  return fechaOperacion && fechaOperacion > hoy ? fechaOperacion : hoy;
}

/** Primer día en que puede vencer el pasaporte: la operación (`fechaReferencia`)
 *  más 3 meses de calendario. Espejo de vigencia_minima_pasaporte. */
export function vigenciaMinimaPasaporte(referencia: string): string {
  return desplazar(referencia, { meses: MESES_VIGENCIA_PASAPORTE });
}

/** Cómo está el pasaporte para la operación: vencido, vigente pero con menos de 3
 *  meses, o bien. Lo usan la validación y el aviso de la tarjeta del pasajero. */
export function estadoPasaporte(vence: string, referencia: string): "vencido" | "corto" | "bien" {
  if (!vence) return "bien";
  if (vence < referencia) return "vencido";
  return vence < vigenciaMinimaPasaporte(referencia) ? "corto" : "bien";
}

/** El aviso de un pasaporte con menos de 3 meses, después de «el pasaporte» (el mismo
 *  texto que el backend). */
export function textoVigenciaCorta(vence: string, referencia: string): string {
  return `debe tener al menos ${MESES_VIGENCIA_PASAPORTE} meses de vigencia a partir de la operación `
    + `(vencer el ${formatearFecha(vigenciaMinimaPasaporte(referencia))} o después); vence el ${formatearFecha(vence)}.`;
}

export function portaLibreta(ficha: Pick<TripulanteEntrada, "rango">): boolean {
  return RANGOS_CON_LIBRETA.includes(ficha.rango);
}

/** Los puestos a los que se puede cambiar desde el elegido (2026-11-13): los del
 *  mismo sector, sin él. Si el nuevo puerto es del otro sector, va una solicitud
 *  nueva. El backend lo vuelve a validar (`_validar_cambio_de_puerto`). */
export function puestosParaCambio(puestos: PuestoMini[], puestoControlId: string): PuestoMini[] {
  const elegido = puestos.find((p) => String(p.id) === puestoControlId);
  if (!elegido) return [];
  return puestos.filter((p) => p.sector_id === elegido.sector_id && p.id !== elegido.id);
}

export function validarFormulario(
  tipo: TipoTramite,
  c: CabeceraFormulario,
  tripulantes: FichaTripulante[],
  paises: Map<string, Pais>,
  hoy: string,
): string[] {
  const errores: string[] = [];

  if (!c.puesto_control_id) errores.push("Elige el puesto de Control Migratorio.");
  if (tipo.permite_cambio_puerto && c.cambio_puerto === "si" && !c.puesto_destino_id) {
    errores.push("Elige el nuevo puesto de control del cambio de puerto.");
  }
  if (!c.fecha_operacion) errores.push("Indica la fecha de la operación.");
  else if (c.fecha_operacion < hoy) errores.push("La fecha de la operación no puede ser anterior a hoy.");
  else if (c.fecha_operacion > operacionMaxima(hoy)) {
    errores.push(`La fecha de la operación no puede estar a más de ${DIAS_MAXIMOS_ANTICIPACION} días.`);
  }
  if (tipo.requiere_buque) {
    if (!c.nombre_buque.trim()) errores.push("Indica el nombre del buque.");
    if (!c.imo.trim()) errores.push("Indica el número IMO del buque.");
    else if (!normalizarImo(c.imo)) errores.push("El número IMO no es válido (7 dígitos con dígito verificador, ej. IMO 9074729).");
    if (!c.bandera) errores.push("Elige la bandera del buque.");
  }
  if (tipo.requiere_puerto && !c.nombre_puerto.trim()) errores.push("Indica el nombre del puerto.");
  if (tipo.requiere_puerto_desembarque && !c.puerto_desembarque.trim()) errores.push("Indica el puerto de desembarque.");
  if (tipo.requiere_motivo && !c.motivo.trim()) errores.push("Indica el motivo.");
  if (tipo.requiere_clinica && !c.clinica_hospital.trim()) errores.push("Indica la clínica u hospital.");

  if (tripulantes.length === 0) errores.push("Registra al menos un pasajero.");
  // Solo pasa al corregir una solicitud enviada antes del tope: el botón no deja agregar más.
  if (tripulantes.length > MAX_TRIPULANTES) {
    errores.push(`Una solicitud admite hasta ${MAX_TRIPULANTES} pasajeros: quita ${tripulantes.length - MAX_TRIPULANTES} `
      + "y preséntalos en otra solicitud.");
  }

  const referencia = fechaReferencia(c.fecha_operacion, hoy);
  const pasaportes = new Map<string, number>();
  const rangos = tipo.rangos_permitidos;
  const rangosTexto = rangos?.map((r) => ETIQUETA_RANGO[r]).join(", ");
  tripulantes.forEach((t, i) => {
    const quien = `Pasajero ${i + 1}${t.nombre.trim() ? ` (${t.nombre.trim()} ${t.apellido.trim()})` : ""}`;
    const faltan: string[] = [];
    if (t.nombre.trim().length < 2) faltan.push("nombre");
    if (t.apellido.trim().length < 2) faltan.push("apellido");
    if (!t.sexo) faltan.push("sexo");
    if (!t.fecha_nacimiento) faltan.push("fecha de nacimiento");
    if (!paises.has(t.pais_nacimiento)) faltan.push("país de nacimiento");
    if (!paises.has(t.nacionalidad)) faltan.push("nacionalidad");
    if (t.ocupacion.trim().length < 2) faltan.push("ocupación");
    if (t.pasaporte.trim().length < 3) faltan.push("N° de pasaporte");
    if (!t.pasaporte_expira) faltan.push("vencimiento del pasaporte");
    const conLibreta = portaLibreta(t);
    if (conLibreta && !t.libreta_marino?.trim()) faltan.push("N° de seamanbook");
    if (conLibreta && !t.libreta_expira) faltan.push("vencimiento del seamanbook");
    if (faltan.length) errores.push(`${quien}: falta ${faltan.join(", ")}.`);
    if (rangos?.length && !rangos.includes(t.rango)) {
      errores.push(`${quien}: en este trámite el rango debe ser ${rangosTexto}.`);
    }

    if (t.fecha_nacimiento) {
      if (t.fecha_nacimiento >= hoy) errores.push(`${quien}: la fecha de nacimiento debe ser anterior a hoy.`);
      else if (t.fecha_nacimiento < NACIMIENTO_MINIMO) errores.push(`${quien}: la fecha de nacimiento no es válida.`);
      else if (t.fecha_nacimiento > nacimientoMaximo(hoy)) {
        errores.push(`${quien}: debe ser mayor de edad (${EDAD_MINIMA} años cumplidos).`);
      }
      if (t.pasaporte_expira && t.pasaporte_expira <= t.fecha_nacimiento) {
        errores.push(`${quien}: el vencimiento del pasaporte debe ser posterior a la fecha de nacimiento.`);
      }
      if (conLibreta && t.libreta_expira && t.libreta_expira <= t.fecha_nacimiento) {
        errores.push(`${quien}: el vencimiento del seamanbook debe ser posterior a la fecha de nacimiento.`);
      }
    }

    if (tipo.valida_vigencia) {
      const pasaporte = estadoPasaporte(t.pasaporte_expira, referencia);
      if (pasaporte === "vencido") {
        errores.push(`${quien}: el pasaporte vence el ${formatearFecha(t.pasaporte_expira)}, antes de la operación.`);
      } else if (pasaporte === "corto") {
        errores.push(`${quien}: el pasaporte ${textoVigenciaCorta(t.pasaporte_expira, referencia)}`);
      }
      // El seamanbook vencido no impide enviar (2026-11-13): la tarjeta lo avisa y
      // el expediente lo señala.
    }

    const clave = `${t.nacionalidad}|${t.pasaporte.trim().toUpperCase()}`;
    if (t.pasaporte.trim()) {
      const previo = pasaportes.get(clave);
      if (previo !== undefined) errores.push(`${quien}: el pasaporte ya está registrado en el pasajero ${previo + 1}.`);
      else pasaportes.set(clave, i);
    }
  });

  return errores;
}
