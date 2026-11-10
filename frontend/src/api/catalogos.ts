import { clienteApi } from "./client";
import type { CatalogoMini } from "../types";

export type PuestoMini = CatalogoMini;

export interface Pais {
  codigo: string;
  nombre: string;
  nacionalidad_restringida: boolean;
}

/** Puesto de control o agencia naviera, con sus usuarios asignados. */
export interface CatalogoConUsuarios {
  id: number;
  nombre: string;
  correo: string | null;
  activo: boolean;
  usuarios: { id: number; username: string; full_name: string }[];
  total_solicitudes: number;
}

/** Un puesto es de un sector de UCVMM (2026-11-10): sus solicitudes las revisa ese sector. */
export interface PuestoAdmin extends CatalogoConUsuarios {
  sector_id: number;
  sector_nombre: string;
}
export type AgenciaAdmin = CatalogoConUsuarios;

/** Sector Pacífico o Atlántico, con su buzón, sus puestos y sus funcionarios (UCVMM y supervisores). */
export interface SectorAdmin {
  id: number;
  nombre: string;
  correo: string | null;
  usuarios: { id: number; username: string; full_name: string }[];
  puestos: CatalogoMini[];
}

export interface DatosCatalogo {
  nombre?: string;
  correo?: string | null;
  activo?: boolean;
  /** Solo los puestos. */
  sector_id?: number;
}

/** Ordena alfabéticamente en español y deja Panamá primero (el caso más común). */
export function ordenarPaises(paises: Pais[]): Pais[] {
  return [...paises].sort((a, b) => {
    if (a.codigo === "PAN") return -1;
    if (b.codigo === "PAN") return 1;
    return a.nombre.localeCompare(b.nombre, "es");
  });
}

export const apiCatalogos = {
  listarPuestos: () =>
    clienteApi.get<PuestoMini[]>("/catalogos/puestos").then((r) => r.data),

  listarPaises: () =>
    clienteApi.get<Pais[]>("/catalogos/paises").then((r) => ordenarPaises(r.data)),

  // ── Administración: puestos de control ──
  listarPuestosAdmin: () =>
    clienteApi.get<PuestoAdmin[]>("/admin/puestos").then((r) => r.data),

  crearPuesto: (nombre: string, correo: string | null, sector_id: number) =>
    clienteApi.post<PuestoAdmin>("/admin/puestos", { nombre, correo, sector_id }).then((r) => r.data),

  actualizarPuesto: (id: number, datos: DatosCatalogo) =>
    clienteApi.patch<PuestoAdmin>(`/admin/puestos/${id}`, datos).then((r) => r.data),

  eliminarPuesto: (id: number) =>
    clienteApi.delete(`/admin/puestos/${id}`),

  asignarUsuariosPuesto: (id: number, usuario_ids: number[]) =>
    clienteApi.put<PuestoAdmin>(`/admin/puestos/${id}/usuarios`, { usuario_ids }).then((r) => r.data),

  // ── Administración: sectores de UCVMM ──
  listarSectoresAdmin: () =>
    clienteApi.get<SectorAdmin[]>("/admin/sectores").then((r) => r.data),

  actualizarSector: (id: number, correo: string | null) =>
    clienteApi.patch<SectorAdmin>(`/admin/sectores/${id}`, { correo }).then((r) => r.data),

  asignarUsuariosSector: (id: number, usuario_ids: number[]) =>
    clienteApi.put<SectorAdmin>(`/admin/sectores/${id}/usuarios`, { usuario_ids }).then((r) => r.data),

  // ── Administración: agencias navieras ──
  listarAgenciasAdmin: () =>
    clienteApi.get<AgenciaAdmin[]>("/admin/agencias").then((r) => r.data),

  crearAgencia: (nombre: string, correo: string | null) =>
    clienteApi.post<AgenciaAdmin>("/admin/agencias", { nombre, correo }).then((r) => r.data),

  actualizarAgencia: (id: number, datos: DatosCatalogo) =>
    clienteApi.patch<AgenciaAdmin>(`/admin/agencias/${id}`, datos).then((r) => r.data),

  eliminarAgencia: (id: number) =>
    clienteApi.delete(`/admin/agencias/${id}`),

  asignarUsuariosAgencia: (id: number, usuario_ids: number[]) =>
    clienteApi.put<AgenciaAdmin>(`/admin/agencias/${id}/usuarios`, { usuario_ids }).then((r) => r.data),

  // ── Administración: países ──
  actualizarPais: (codigo: string, nacionalidad_restringida: boolean) =>
    clienteApi.patch<Pais>(`/admin/paises/${codigo}`, { nacionalidad_restringida }).then((r) => r.data),
};
