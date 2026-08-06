import { clienteApi, URL_BASE_API } from "./client";
import type { Transferencia, TransferenciaPublica } from "../types";

export const apiTransferencias = {
  listar: () =>
    clienteApi.get<Transferencia[]>("/transfers/").then((r) => r.data),

  listarTodasActivas: () =>
    clienteApi.get<Transferencia[]>("/transfers/todas-activas").then((r) => r.data),

  crear: (formulario: FormData) =>
    clienteApi.post<Transferencia>("/transfers/", formulario, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data),

  obtenerPublica: (token: string) =>
    clienteApi.get<TransferenciaPublica>(`/transfers/public/${token}`).then((r) => r.data),

  urlDescarga: (token: string, fileId: number) =>
    `${URL_BASE_API}/transfers/download/${token}/${fileId}`,

  urlPreview: (token: string, fileId: number) =>
    `${URL_BASE_API}/transfers/preview/${token}/${fileId}`,

  eliminar: (token: string) =>
    clienteApi.delete(`/transfers/${token}`),
};
