/**
 * La consulta histórica sin React (2026-11-11): los filtros, cómo van en la URL
 * (para volver a la misma búsqueda o compartirla), la consulta para la API y el
 * atajo por año. El pasajero no va en la URL (2026-11-14: quedaba en el historial del
 * navegador y en los logs del servidor): viaja en el estado de la navegación.
 */
import type { ConsultaHistorica, EstadoSolicitud, OpcionesHistorico, SolicitudResumen } from "../../../api/solicitudes";

/** El primer año con solicitudes en ARGO NAVIS (el atajo por año empieza aquí). */
export const PRIMER_ANIO = 2026;

/** Una pestaña: un estado, "" (todas) o las autorizadas (2026-11-22), que son las que se
 *  aprobaron alguna vez: vigentes, finalizadas y vencidas sin finalizar. */
export type PestanaHistorico = EstadoSolicitud | "autorizadas" | "";

export interface FiltrosHistorico {
  texto: string;
  pasajero: string;
  agencia: string;   // id, o "" (todas)
  puesto: string;
  tramite: string;
  estado: PestanaHistorico;
  fecha: "envio" | "operacion";   // a qué fecha van desde y hasta
  desde: string;     // AAAA-MM-DD, o ""
  hasta: string;
  fueraDeHorario: boolean;
}

export const FILTROS_VACIOS: FiltrosHistorico = {
  texto: "", pasajero: "", agencia: "", puesto: "", tramite: "", estado: "",
  fecha: "envio", desde: "", hasta: "", fueraDeHorario: false,
};

const PESTANAS: PestanaHistorico[] = ["autorizadas", "review", "returned", "approved", "denied", "finalized", "expired"];
const TOPE_TEXTO = 100;   // el max_length de ConsultaHistorica en el backend

function fechaValida(valor: string | null): string {
  return valor && /^\d{4}-\d{2}-\d{2}$/.test(valor) && !Number.isNaN(Date.parse(valor)) ? valor : "";
}

function idValido(valor: string | null): string {
  return valor && /^[1-9]\d{0,8}$/.test(valor) ? valor : "";
}

/** Los filtros que trae la URL. Lo que no se entiende se ignora (un enlace viejo
 *  o tocado a mano no rompe la página). */
export function filtrosDeUrl(p: URLSearchParams): FiltrosHistorico {
  const estado = p.get("estado") as PestanaHistorico | null;
  return {
    texto: (p.get("texto") ?? "").slice(0, TOPE_TEXTO),
    pasajero: "",   // no va en la URL: un enlace viejo que lo traiga no lo filtra
    agencia: idValido(p.get("agencia")),
    puesto: idValido(p.get("puesto")),
    tramite: idValido(p.get("tramite")),
    estado: estado && PESTANAS.includes(estado) ? estado : "",
    fecha: p.get("fecha") === "operacion" ? "operacion" : "envio",
    desde: fechaValida(p.get("desde")),
    hasta: fechaValida(p.get("hasta")),
    fueraDeHorario: p.get("fuera") === "1",
  };
}

/** La página que trae la URL (1 si no trae una válida). */
export function paginaDeUrl(p: URLSearchParams): number {
  const n = Number(p.get("pagina"));
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

/** Los filtros para la URL: solo los que filtran (y la página, desde la 2). */
export function urlDeFiltros(f: FiltrosHistorico, pagina = 1): Record<string, string> {
  const r: Record<string, string> = {};
  if (f.texto.trim()) r.texto = f.texto.trim();
  if (f.agencia) r.agencia = f.agencia;
  if (f.puesto) r.puesto = f.puesto;
  if (f.tramite) r.tramite = f.tramite;
  if (f.estado) r.estado = f.estado;
  if (f.fecha === "operacion") r.fecha = "operacion";
  if (f.desde) r.desde = f.desde;
  if (f.hasta) r.hasta = f.hasta;
  if (f.fueraDeHorario) r.fuera = "1";
  if (pagina > 1) r.pagina = String(pagina);
  return r;
}

/** La consulta para la API (lo vacío no se manda). */
export function consultaDeFiltros(f: FiltrosHistorico, pagina: number, porPagina: number): ConsultaHistorica {
  return {
    texto: f.texto.trim() || undefined,
    pasajero: f.pasajero.trim() || undefined,
    agencia_id: f.agencia ? Number(f.agencia) : undefined,
    puesto_id: f.puesto ? Number(f.puesto) : undefined,
    tipo_tramite_id: f.tramite ? Number(f.tramite) : undefined,
    estado: f.estado && f.estado !== "autorizadas" ? f.estado : undefined,
    autorizadas: f.estado === "autorizadas" || undefined,
    fuera_de_horario: f.fueraDeHorario || undefined,
    fecha: f.fecha === "operacion" ? "operacion" : undefined,
    desde: f.desde || undefined,
    hasta: f.hasta || undefined,
    pagina,
    por_pagina: porPagina,
  };
}

/** De una expirada, si se llegó a aprobar; de las demás, nada (2026-11-22). */
export function motivoExpiracion(s: Pick<SolicitudResumen, "estado" | "aprobada_en">): string | null {
  if (s.estado !== "expired") return null;
  return s.aprobada_en ? "Aprobada; venció sin finalizarse" : "No se corrigió a tiempo";
}

const ENCONTRADOS_VISIBLES = 3;

/** Los tripulantes que coinciden con lo buscado: los primeros y cuántos más (2026-11-22). */
export function primerosEncontrados<T>(encontrados: T[] | null): { visibles: T[]; mas: number } {
  const visibles = (encontrados ?? []).slice(0, ENCONTRADOS_VISIBLES);
  return { visibles, mas: (encontrados ?? []).length - visibles.length };
}

/** Si algo acota la consulta (la fecha «por» sola no acota: sin desde ni hasta). */
export function hayFiltros(f: FiltrosHistorico): boolean {
  return Object.entries(f).some(([clave, v]) => clave !== "fecha" && (typeof v === "string" ? v.trim() !== "" : v));
}

/** La última página que tiene resultados (1 si no hay ninguno). */
export function ultimaPagina(total: number, porPagina: number): number {
  return Math.max(1, Math.ceil(total / porPagina));
}

/** Del primer año con solicitudes hasta el de hoy, el más reciente primero. */
export function aniosDisponibles(hoy: Date): number[] {
  const anios: number[] = [];
  for (let a = Math.max(hoy.getFullYear(), PRIMER_ANIO); a >= PRIMER_ANIO; a--) anios.push(a);
  return anios;
}

export function rangoDeAnio(anio: number): { desde: string; hasta: string } {
  return { desde: `${anio}-01-01`, hasta: `${anio}-12-31` };
}

/** Qué muestra el atajo por año: todos, un año entero de la lista u otras fechas. */
export function anioDelRango(desde: string, hasta: string, anios: number[]): "todos" | "otras" | number {
  if (!desde && !hasta) return "todos";
  const anio = Number(desde.slice(0, 4));
  const entero = desde === `${anio}-01-01` && hasta === `${anio}-12-31`;
  return entero && anios.includes(anio) ? anio : "otras";
}

/** Sin los ids que no están en las opciones (un enlace viejo, o uno tocado a mano): antes
 *  se filtraba por ellos mientras el desplegable decía «Todos». Si no cambia nada, el mismo objeto. */
export function sinOpcionesDesconocidas(f: FiltrosHistorico, o: OpcionesHistorico): FiltrosHistorico {
  const existe = (lista: { id: number }[], id: string) => !id || lista.some((x) => String(x.id) === id);
  const limpios = {
    agencia: existe(o.agencias, f.agencia) ? f.agencia : "",
    puesto: existe(o.puestos, f.puesto) ? f.puesto : "",
    tramite: existe(o.tramites, f.tramite) ? f.tramite : "",
  };
  return limpios.agencia === f.agencia && limpios.puesto === f.puesto && limpios.tramite === f.tramite
    ? f : { ...f, ...limpios };
}
