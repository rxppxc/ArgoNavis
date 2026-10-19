/**
 * Verificación de impedimentos en SIMPLUS de una solicitud (UCVMM): el
 * resultado de cada tripulante, el comentario y la corrección de una
 * verificación ya registrada, que exige motivo y deja el cambio en el
 * historial. Se marca en la tabla de tripulantes (SeccionTripulantes) y el
 * panel de decisión (PanelRevision) la resume.
 */
import { useState } from "react";
import { apiSolicitudes, type SolicitudDetalle } from "../../api/solicitudes";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";

/** true = con impedimento, false = sin, null = sin marcar. */
export type ResultadoImpedimento = boolean | null;

export interface VerificacionImpedimentos {
  resultados: Record<number, ResultadoImpedimento>;
  comentario: string;
  motivoCorreccion: string;
  /** Ya hay una verificación guardada. */
  registrada: boolean;
  corrigiendo: boolean;
  /** Se pueden marcar los resultados: aún no se registra o se está corrigiendo. */
  editable: boolean;
  /** La última verificación guardada fue una corrección. */
  corregida: boolean;
  pendientes: number;
  hayCambios: boolean;
  trabajando: boolean;
  /** Nombres con impedimento según lo guardado (lo que tiene en cuenta quien decide). */
  conImpedimento: string[];
  marcar: (tripulanteId: number, conImpedimento: boolean) => void;
  marcarTodosSin: () => void;
  setComentario: (texto: string) => void;
  setMotivoCorreccion: (texto: string) => void;
  guardar: () => Promise<void>;
  empezarCorreccion: () => void;
  cancelarCorreccion: () => void;
}

export function useVerificacionImpedimentos(
  solicitud: SolicitudDetalle,
  onActualizada: (s: SolicitudDetalle) => void,
): VerificacionImpedimentos {
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  const guardados = (): Record<number, ResultadoImpedimento> =>
    Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, t.con_impedimento]));
  const [resultados, setResultados] = useState<Record<number, ResultadoImpedimento>>(guardados);
  const [comentario, setComentario] = useState(solicitud.comentario_impedimentos ?? "");
  // Registrada, la verificación es de solo lectura; cambiarla es una corrección con motivo.
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [motivoCorreccion, setMotivoCorreccion] = useState("");
  const [trabajando, setTrabajando] = useState(false);

  const registrada = solicitud.impedimentos_verificados;
  const editable = !registrada || corrigiendo;
  const corregida = [...solicitud.eventos].reverse()
    .find((e) => e.tipo === "impedimentos" || e.tipo === "impedimentos_corregidos")?.tipo === "impedimentos_corregidos";
  const pendientes = solicitud.tripulantes.filter((t) => resultados[t.id] == null).length;
  const conImpedimento = solicitud.tripulantes.filter((t) => t.con_impedimento).map((t) => t.nombre_completo);
  const cambiados = solicitud.tripulantes.filter((t) => t.con_impedimento !== null && resultados[t.id] !== t.con_impedimento);
  const hayCambios = solicitud.tripulantes.some((t) => resultados[t.id] !== t.con_impedimento)
    || comentario.trim() !== (solicitud.comentario_impedimentos ?? "");

  function marcar(tripulanteId: number, conImpedimentoNuevo: boolean) {
    setResultados((r) => ({ ...r, [tripulanteId]: conImpedimentoNuevo }));
  }

  function marcarTodosSin() {
    setResultados(Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, false])));
  }

  function empezarCorreccion() {
    setResultados(guardados());
    setComentario(solicitud.comentario_impedimentos ?? "");
    setMotivoCorreccion("");
    setCorrigiendo(true);
  }

  function cancelarCorreccion() {
    setResultados(guardados());
    setComentario(solicitud.comentario_impedimentos ?? "");
    setCorrigiendo(false);
  }

  async function guardar() {
    if (pendientes) {
      mostrar(`Falta marcar el resultado de ${pendientes} tripulante${pendientes === 1 ? "" : "s"}.`, "aviso");
      return;
    }
    if (corrigiendo) {
      const motivo = motivoCorreccion.trim();
      if (motivo.length < 5) {
        mostrar("Escribe el motivo de la corrección (al menos 5 caracteres).", "aviso");
        return;
      }
      const resultado = (conImp: boolean | null | undefined) => (conImp ? "con impedimento" : "sin impedimento");
      const ok = await confirmar({
        titulo: "Corregir verificación de impedimentos",
        mensaje: (
          cambiados.length === 1
            ? `${cambiados[0].nombre_completo} pasa de ${resultado(cambiados[0].con_impedimento)} a ${resultado(resultados[cambiados[0].id])}.`
            : cambiados.length > 1
              ? `Cambia el resultado de ${cambiados.map((t) => `${t.nombre_completo} (ahora ${resultado(resultados[t.id])})`).join(", ")}.`
              : "Se actualiza el comentario de la verificación."
        ) + ` Motivo: ${/[.!?]$/.test(motivo) ? motivo : `${motivo}.`} La verificación anterior queda en el historial.`,
        textoOk: "Guardar corrección",
      });
      if (!ok) return;
    }
    setTrabajando(true);
    try {
      const lista = solicitud.tripulantes.map((t) => ({ tripulante_id: t.id, con_impedimento: !!resultados[t.id] }));
      onActualizada(await apiSolicitudes.registrarImpedimentos(
        solicitud.id, lista, comentario.trim() || null, corrigiendo ? motivoCorreccion.trim() : null,
      ));
      mostrar(corrigiendo ? "Verificación de impedimentos corregida." : "Verificación de impedimentos registrada.", "exito");
      setCorrigiendo(false);
      setMotivoCorreccion("");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo registrar la verificación."), "error");
    } finally {
      setTrabajando(false);
    }
  }

  return {
    resultados, comentario, motivoCorreccion, registrada, corrigiendo, editable, corregida,
    pendientes, hayCambios, trabajando, conImpedimento,
    marcar, marcarTodosSin, setComentario, setMotivoCorreccion, guardar, empezarCorreccion, cancelarCorreccion,
  };
}
