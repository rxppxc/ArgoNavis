import { clienteApi } from "./client";
import type { CatalogoMini } from "../types";

export interface UsuarioAD {
  username: string;
  name: string;
  last_name: string;
  email: string;
  guid: string;
  department: string;
}

export interface RolMini {
  id: number;
  nombre: string;
  es_sistema: boolean;
}

export interface UsuarioSistema {
  id: number;
  username: string;
  name: string | null;
  last_name: string | null;
  email: string | null;
  user_type: "ad" | "local";
  status: "active" | "inactive";
  rol_id: number | null;
  rol_personalizado: RolMini | null;
  agencia_id: number | null;
  agencia: CatalogoMini | null;
  debe_cambiar_password: boolean;
  full_name: string;
}

export interface Permiso {
  id: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  created_at: string;
}

export interface Rol {
  id: number;
  nombre: string;
  descripcion: string | null;
  es_sistema: boolean;
  created_at: string;
  permisos: Permiso[];
  total_usuarios: number;
}

export interface DatosUsuarioLocal {
  username: string;
  password: string;
  name?: string;
  last_name?: string;
  email?: string;
  rol_id?: number | null;
}

/** Uso del sistema (no del flujo): cuentas, agencias y documentos almacenados. */
export interface UsoSistema {
  usuarios:             number;
  usuarios_activos:     number;
  agencias:             number;
  documentos:           number;
  almacenamiento_bytes: number;
  top_agencias:         { agencia_id: number; nombre: string; total: number }[];
}

export interface RegistroBitacora {
  id:        number;
  creado_en: string;
  accion:    string;
  user_id:   number | null;
  username:  string | null;
  detalle:   Record<string, unknown> | null;
  ip:        string | null;
}

export interface PaginaBitacora {
  total:      number;
  pagina:     number;
  por_pagina: number;
  items:      RegistroBitacora[];
}

export interface FiltrosBitacora {
  accion?:     string;
  usuario?:    string;
  texto?:      string;
  desde?:      string;
  hasta?:      string;
  pagina?:     number;
  por_pagina?: number;
}

export const apiAdmin = {
  // Bitácora
  consultarBitacora: (filtros: FiltrosBitacora) =>
    clienteApi.get<PaginaBitacora>("/admin/bitacora", {
      params: Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== undefined && v !== "")),
    }),

  accionesBitacora: () =>
    clienteApi.get<string[]>("/admin/bitacora/acciones"),

  buscarEnAD: (q: string) =>
    clienteApi.get<UsuarioAD[]>(`/admin/usuarios/buscar-ad`, { params: { q } }),

  listarUsuarios: () =>
    clienteApi.get<UsuarioSistema[]>("/admin/usuarios"),

  crearUsuario: (username: string) =>
    clienteApi.post<UsuarioSistema>("/admin/usuarios", { username }),

  // Cuenta local (sin AD), p. ej. para usuarios de agencias navieras.
  crearUsuarioLocal: (datos: DatosUsuarioLocal) =>
    clienteApi.post<UsuarioSistema>("/admin/usuarios/local", datos),

  /** Genera una contraseña temporal (se muestra una sola vez). */
  restablecerContrasena: (id: number) =>
    clienteApi.post<{ contrasena_temporal: string }>(`/admin/usuarios/${id}/restablecer-contrasena`)
      .then((r) => r.data.contrasena_temporal),

  cambiarEstado: (id: number, status: "active" | "inactive") =>
    clienteApi.patch<UsuarioSistema>(`/admin/usuarios/${id}/estado`, { status }),

  eliminarUsuario: (id: number) =>
    clienteApi.delete(`/admin/usuarios/${id}`),

  // Uso del sistema
  obtenerUso: () =>
    clienteApi.get<UsoSistema>("/admin/stats").then((r) => r.data),

  // Permisos (solo lectura: los define el sistema)
  listarPermisos: () =>
    clienteApi.get<Permiso[]>("/admin/permisos"),

  // Roles
  listarRoles: () =>
    clienteApi.get<Rol[]>("/admin/roles"),

  crearRol: (nombre: string, descripcion?: string) =>
    clienteApi.post<Rol>("/admin/roles", { nombre, descripcion }),

  actualizarRol: (id: number, datos: { nombre?: string; descripcion?: string }) =>
    clienteApi.patch<Rol>(`/admin/roles/${id}`, datos),

  eliminarRol: (id: number) =>
    clienteApi.delete(`/admin/roles/${id}`),

  asignarPermisosARol: (id: number, permiso_ids: number[]) =>
    clienteApi.put<Rol>(`/admin/roles/${id}/permisos`, { permiso_ids }),

  asignarRolAUsuario: (user_id: number, rol_id: number | null) =>
    clienteApi.patch<UsuarioSistema>(`/admin/usuarios/${user_id}/rol-personalizado`, { rol_id }),
};
