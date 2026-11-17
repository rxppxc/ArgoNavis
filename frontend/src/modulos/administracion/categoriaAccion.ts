/**
 * La categoría de cada acción de la bitácora, para el color de su etiqueta (rediseño visual
 * del 2026-11-17): antes todas eran grises iguales y había que leerlas una por una. El color
 * es solo una ayuda: la etiqueta dice la acción.
 */
export type CategoriaAccion =
  | "sesion" | "alerta" | "credencial" | "solicitud" | "documento" | "boleta" | "administracion" | "historico" | "otra";

const EXACTAS: Record<string, CategoriaAccion> = {
  LOGIN_EXITOSO: "sesion", CERRAR_SESION: "sesion", SESION_EXPIRADA: "sesion",
  LOGIN_FALLIDO: "alerta", CUENTA_BLOQUEADA: "alerta",
  CONTRASENA_CAMBIADA: "credencial", CONTRASENA_RESTABLECIDA: "credencial",
  IMPEDIMENTOS_REGISTRADOS: "solicitud",
  // Del storage original: se conservan para leer el historial.
  DESCARGA_REALIZADA: "historico", CHAT_CONSULTA: "historico",
};

const PREFIJOS: [string, CategoriaAccion][] = [
  ["SOLICITUD_", "solicitud"],
  ["DOCUMENTO_", "documento"], ["AUTORIZACION_", "documento"],
  ["BOLETA_", "boleta"],
  ["USUARIO_", "administracion"], ["ROL_", "administracion"], ["PERMISO_", "administracion"],
  ["PUESTO_", "administracion"], ["SECTOR_", "administracion"], ["AGENCIA_", "administracion"],
  ["PAIS_", "administracion"],
  ["TRANSFERENCIA_", "historico"],
];

export function categoriaAccion(accion: string): CategoriaAccion {
  return EXACTAS[accion] ?? PREFIJOS.find(([prefijo]) => accion.startsWith(prefijo))?.[1] ?? "otra";
}
