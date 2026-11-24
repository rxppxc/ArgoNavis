/**
 * El borrador de una solicitud nueva (2026-11-23). Pedido del usuario: si la agencia sale del
 * formulario sin enviar («Volver», la sesión que se cierra, otra pantalla), lo que llenó queda
 * en borrador; si en un tiempo no lo continúa, se reinicia. Decidido: 24 horas desde el último
 * cambio, en el navegador de ese equipo, por usuario y con los archivos.
 *
 * Aquí, lo que no es React ni el navegador: cuándo vale, cuándo hay algo que guardar, cómo se
 * restaura (con claves nuevas) y el texto del aviso. Lo guarda `almacenBorradores.ts`.
 */
import { claveCasilla } from "../checklist";
import type { AdicionalNuevo } from "./DocumentosAdicionales";
import { fichaVacia, nuevaClave } from "./envioSolicitud";
import { CABECERA_VACIA, type CabeceraFormulario, type FichaTripulante } from "./validacionFormulario";

export const HORAS_BORRADOR = 24;
const MS_BORRADOR = HORAS_BORRADOR * 3_600_000;
/** Un reloj del equipo un poco adelantado no invalida lo recién guardado. */
const TOLERANCIA_RELOJ = 60_000;

export interface DatosBorrador {
  codigoTramite: string;
  cabecera:      CabeceraFormulario;
  tripulantes:   FichaTripulante[];
}

export interface ArchivosBorrador {
  /** Los del checklist, por casilla (`claveCasilla`). */
  nuevos:      Record<string, File>;
  adicionales: AdicionalNuevo[];
}

/** Uno por usuario: otra cuenta en el mismo equipo no ve el borrador de esta. */
export function claveBorrador(usuarioId: number): string {
  return `solicitud-nueva:${usuarioId}`;
}

export function borradorVigente(guardadoEn: number, ahora: number): boolean {
  return guardadoEn <= ahora + TOLERANCIA_RELOJ && ahora - guardadoEn < MS_BORRADOR;
}

/** El rango de la ficha trae un valor de entrada: no cuenta como algo escrito. */
const CAMPOS_FICHA: (keyof FichaTripulante)[] = [
  "nombre", "apellido", "fecha_nacimiento", "pais_nacimiento", "nacionalidad", "sexo", "pasaporte",
  "pasaporte_expira", "libreta_marino", "libreta_expira",
];

/** Solo se guarda si hay algo: un trámite elegido, un dato escrito o un archivo. */
export function tieneContenido(datos: DatosBorrador, archivos: ArchivosBorrador): boolean {
  if (datos.codigoTramite) return true;
  if (Object.keys(archivos.nuevos).length || archivos.adicionales.length) return true;
  const cabecera = Object.entries(datos.cabecera) as [keyof CabeceraFormulario, string][];
  if (cabecera.some(([campo, valor]) => valor !== CABECERA_VACIA[campo])) return true;
  return datos.tripulantes.some((t) => CAMPOS_FICHA.some((campo) => String(t[campo] ?? "").trim() !== ""));
}

/** Lo guardado, listo para el formulario. Las claves de los tripulantes y de los archivos salen
 *  de un contador de la página que empieza de cero al recargarla: se renuevan, y cada archivo
 *  sigue a su tripulante. El de un tripulante que ya no está se descarta. */
export function restaurar(datos: DatosBorrador, archivos: ArchivosBorrador): { datos: DatosBorrador; archivos: ArchivosBorrador } {
  const claves = new Map<string, string>();
  const tripulantes = datos.tripulantes.map((t) => {
    const clave = nuevaClave("n");
    claves.set(t.clave, clave);
    // Sobre una ficha vacía: lo guardado por la versión anterior no trae los campos nuevos.
    return { ...fichaVacia(), ...t, clave };
  });
  const nuevos: Record<string, File> = {};
  for (const [casilla, archivo] of Object.entries(archivos.nuevos)) {
    const corte = casilla.lastIndexOf("|");
    const documento = casilla.slice(0, corte);
    const tripulante = casilla.slice(corte + 1);
    if (tripulante === "s") nuevos[claveCasilla(documento, null)] = archivo;
    else if (claves.has(tripulante)) nuevos[claveCasilla(documento, claves.get(tripulante) ?? null)] = archivo;
  }
  return {
    datos: { ...datos, cabecera: { ...CABECERA_VACIA, ...datos.cabecera }, tripulantes: tripulantes.length ? tripulantes : [fichaVacia()] },
    archivos: { nuevos, adicionales: archivos.adicionales.map((a) => ({ clave: nuevaClave("a"), archivo: a.archivo })) },
  };
}

const dos = (n: number) => String(n).padStart(2, "0");

function hora(d: Date): string {
  const h = d.getHours();
  return `${h % 12 || 12}:${dos(d.getMinutes())} ${h < 12 ? "a. m." : "p. m."}`;
}

const mismoDia = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

/** «hoy a las 10:42 a. m.», «ayer a las 4:05 p. m.» o «el 22/11/2026 a las 9:15 a. m.». */
export function cuandoSeGuardo(guardadoEn: number, ahora: Date): string {
  const d = new Date(guardadoEn);
  const ayer = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate() - 1);
  if (mismoDia(d, ahora)) return `hoy a las ${hora(d)}`;
  if (mismoDia(d, ayer)) return `ayer a las ${hora(d)}`;
  return `el ${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} a las ${hora(d)}`;
}
