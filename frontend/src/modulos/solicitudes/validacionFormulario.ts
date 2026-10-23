/** Validación del formulario de solicitud en el navegador. Espeja las reglas
 *  del backend (que igual vuelve a validar todo) para avisar antes de enviar. */
import type { Pais } from "../../api/catalogos";
import type { TripulanteEntrada } from "../../api/solicitudes";
import type { TipoTramite } from "../../api/tramites";
import { ETIQUETA_RANGO, RANGOS_CON_LIBRETA, formatearFecha, normalizarImo } from "./presentacion";

export interface CabeceraFormulario {
  puesto_control_id: string;
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
  puesto_control_id: "", fecha_operacion: "",
  nombre_buque: "", imo: "", bandera: "",
  nombre_puerto: "", puerto_desembarque: "", motivo: "", clinica_hospital: "",
  observaciones: "",
};

/** Mismos límites que el backend (tramite_service.py y DIAS_MAXIMOS_ANTICIPACION). */
export const EDAD_MINIMA = 18;
export const NACIMIENTO_MINIMO = "1900-01-01";
export const DIAS_MAXIMOS_ANTICIPACION = 365;

/** Suma años o días a una fecha ISO (AAAA-MM-DD), sin pasar por la zona horaria.
 *  Si el día no existe en el año de destino (29 de febrero), queda el último del
 *  mes, como cuenta la edad el backend: el 29/02/2028 no tiene 18 años quien nació
 *  el 01/03/2010. */
function desplazar(iso: string, { anios = 0, dias = 0 }: { anios?: number; dias?: number }): string {
  const [a, m, d] = iso.split("-").map(Number);
  const ultimoDelMes = new Date(Date.UTC(a + anios, m, 0)).getUTCDate();
  const fecha = new Date(Date.UTC(a + anios, m - 1, Math.min(d, ultimoDelMes) + dias));
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

export function portaLibreta(ficha: Pick<TripulanteEntrada, "rango">): boolean {
  return RANGOS_CON_LIBRETA.includes(ficha.rango);
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

  if (tripulantes.length === 0) errores.push("Registra al menos un tripulante.");

  const referencia = fechaReferencia(c.fecha_operacion, hoy);
  const pasaportes = new Map<string, number>();
  const rangos = tipo.rangos_permitidos;
  const rangosTexto = rangos?.map((r) => ETIQUETA_RANGO[r]).join(", ");
  tripulantes.forEach((t, i) => {
    const quien = `Tripulante ${i + 1}${t.nombre.trim() ? ` (${t.nombre.trim()} ${t.apellido.trim()})` : ""}`;
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
      if (t.pasaporte_expira && t.pasaporte_expira < referencia) {
        errores.push(`${quien}: el pasaporte vence el ${formatearFecha(t.pasaporte_expira)}, antes de la operación.`);
      }
      if (conLibreta && t.libreta_expira && t.libreta_expira < referencia) {
        errores.push(`${quien}: el seamanbook vence el ${formatearFecha(t.libreta_expira)}, antes de la operación.`);
      }
    }

    const clave = `${t.nacionalidad}|${t.pasaporte.trim().toUpperCase()}`;
    if (t.pasaporte.trim()) {
      const previo = pasaportes.get(clave);
      if (previo !== undefined) errores.push(`${quien}: el pasaporte ya está registrado en el tripulante ${previo + 1}.`);
      else pasaportes.set(clave, i);
    }
  });

  return errores;
}
