/**
 * «Qué sigue» del expediente (rediseño visual del 2026-11-17, pedido del usuario: que
 * cualquier persona sepa qué hacer y no se pierda). Los pasos dependen de quién mira y en
 * qué estado está la solicitud; los que ya están hechos se marcan. Sin nada que hacer no
 * hay pasos y el recuadro no se muestra: el estado ya lo cuenta su aviso (BannerEstado).
 * Lo que lee la agencia no nombra a UCVMM ni a los sectores.
 */
import type { AccionesSolicitud, EstadoSolicitud } from "../../../api/solicitudes";

export interface PasoSiguiente {
  texto: string;
  hecho: boolean;
}

export interface EntradaPasos {
  estado: EstadoSolicitud;
  acciones: AccionesSolicitud;
  /** Quien mira es la agencia (no el personal del SNM). */
  esAgencia: boolean;
  /** La verificación de impedimentos de la etapa que toca (UCVMM al revisar, el puesto al finalizar). */
  verificacion: { pendientes: number; guardada: boolean } | null;
  /** El plazo para corregir, ya con formato (solo la devuelta). */
  plazo: string | null;
  /** El puesto donde vale la autorización (con cambio de puerto, el nuevo). */
  puesto: string;
}

const BOLETA = "Genera la boleta de recargo (aprobada fuera del horario) y entrégala a la agencia";

export function pasosSiguientes(e: EntradaPasos): PasoSiguiente[] {
  const guardada = !!e.verificacion?.guardada;
  const pasos: PasoSiguiente[] = [];

  if (e.acciones.revisar) {
    pasos.push(
      { texto: "Marca «Sin» o «Con» a cada pasajero en la tabla", hecho: guardada || e.verificacion?.pendientes === 0 },
      { texto: "Guarda la verificación", hecho: guardada },
      { texto: "Aprueba, devuelve a corrección o deniega la solicitud", hecho: false },
    );
  } else if (e.acciones.finalizar) {
    pasos.push(
      { texto: "Verifica los impedimentos de cada pasajero en SIMPLUS y guarda la verificación", hecho: guardada },
      { texto: "Escribe el comentario de la operación", hecho: false },
      { texto: `Finaliza la solicitud (solo si la operación se hizo en ${e.puesto})`, hecho: false },
    );
  } else if (e.esAgencia && e.acciones.corregir) {
    pasos.push(
      { texto: "Lee el motivo de la devolución", hecho: false },
      { texto: "Pulsa «Corregir solicitud» y cambia lo que se pidió", hecho: false },
      { texto: e.plazo ? `Envíala de nuevo antes del ${e.plazo}` : "Envíala de nuevo", hecho: false },
    );
  } else if (e.esAgencia && e.estado === "approved" && e.acciones.descargar_autorizacion) {
    pasos.push(
      { texto: "Descarga la autorización (PDF)", hecho: false },
      { texto: `Preséntala en ${e.puesto} el día de la operación`, hecho: false },
    );
  }

  // La boleta de recargo, para quien la genera (generar_boleta: hay recargo y no hay una vigente).
  if (e.acciones.generar_boleta) pasos.push({ texto: BOLETA, hecho: false });
  return pasos;
}
