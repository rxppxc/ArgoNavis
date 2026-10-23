/**
 * Lo que el formulario de solicitud necesita antes de mostrarse: los puestos,
 * los países, la agencia del usuario y los trámites. Al corregir, la solicitud
 * devuelta y solo su trámite (no se cambia).
 */
import { useEffect, useState } from "react";
import { apiAutenticacion } from "../../api/auth";
import { apiCatalogos, type Pais, type PuestoMini } from "../../api/catalogos";
import { apiSolicitudes, type SolicitudDetalle } from "../../api/solicitudes";
import { apiTramites, type TipoTramite } from "../../api/tramites";
import type { CatalogoMini } from "../../types";
import { mensajeDeError } from "../../utils/errores";

export interface DatosFormulario {
  tipos: TipoTramite[];
  puestos: PuestoMini[];
  paises: Pais[];
  agencia: CatalogoMini | null;
  /** La solicitud devuelta, al corregir; null en una nueva. */
  original: SolicitudDetalle | null;
}

export type CargaFormulario =
  | { estado: "cargando" }
  | { estado: "error"; mensaje: string }
  | { estado: "lista"; datos: DatosFormulario };

const CARGANDO: CargaFormulario = { estado: "cargando" };

export function useCargaFormulario(solicitudId: number | null): CargaFormulario {
  // Cada carga recuerda de qué solicitud es: si cambia la ruta, se vuelve a
  // «cargando» en vez de mostrar la anterior.
  const [carga, setCarga] = useState<{ solicitudId: number | null; resultado: CargaFormulario } | null>(null);

  useEffect(() => {
    let cancelado = false;
    cargar(solicitudId).then((resultado) => {
      if (!cancelado) setCarga({ solicitudId, resultado });
    });
    return () => { cancelado = true; };
  }, [solicitudId]);

  return carga?.solicitudId === solicitudId ? carga.resultado : CARGANDO;
}

async function cargar(solicitudId: number | null): Promise<CargaFormulario> {
  try {
    const [puestos, paises, perfil] = await Promise.all([
      apiCatalogos.listarPuestos(), apiCatalogos.listarPaises(), apiAutenticacion.perfilActual(),
    ]);
    const catalogos = { puestos, paises, agencia: perfil.agencia };

    if (solicitudId !== null) {
      const original = await apiSolicitudes.obtener(solicitudId);
      if (!original.acciones.corregir) {
        return {
          estado: "error",
          mensaje: "Esta solicitud no está disponible para corrección (no está devuelta o el plazo ya venció).",
        };
      }
      const tipo = await apiTramites.obtener(original.tipo_tramite_codigo);
      return { estado: "lista", datos: { ...catalogos, tipos: [tipo], original } };
    }
    if (!perfil.agencia) {
      return {
        estado: "error",
        mensaje: "Tu usuario no tiene una agencia naviera asignada, así que todavía no puedes enviar solicitudes. "
          + "Pide al administrador que te asigne a tu agencia.",
      };
    }
    return { estado: "lista", datos: { ...catalogos, tipos: await apiTramites.listar(), original: null } };
  } catch (error) {
    return { estado: "error", mensaje: mensajeDeError(error, "No se pudo cargar el formulario.") };
  }
}
