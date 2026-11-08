/**
 * Verificación de impedimentos en SIMPLUS de una solicitud: la de UCVMM al
 * revisar y la del puesto de control antes de finalizar (2026-11-06), cada
 * una en sus propios campos. El resultado de cada tripulante, el comentario y
 * la corrección de una verificación ya registrada, que exige motivo y deja el
 * cambio en el historial. Se marca en la tabla de tripulantes
 * (SeccionTripulantes); el panel de decisión (PanelRevision) o el del puesto
 * (PanelPuerto) la resume.
 */
import { useState } from "react";
import {
  apiSolicitudes, releerSiCambio, type EventoSolicitud, type SolicitudDetalle, type TripulanteSolicitud,
} from "../../api/solicitudes";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";

/** true = con impedimento, false = sin, null = sin marcar. */
export type ResultadoImpedimento = boolean | null;

/** "ucvmm": la de la revisión; "puesto": la del puesto de control antes de finalizar. */
export type EtapaVerificacion = "ucvmm" | "puesto";

interface CamposEtapa {
  resultado: (t: TripulanteSolicitud) => ResultadoImpedimento;
  registrada: (s: SolicitudDetalle) => boolean;
  comentario: (s: SolicitudDetalle) => string | null;
  por: (s: SolicitudDetalle) => string | null;
  en: (s: SolicitudDetalle) => string | null;
  /** El evento de una verificación y el de su corrección, en el historial. */
  eventos: readonly [EventoSolicitud["tipo"], EventoSolicitud["tipo"]];
  metodo: "registrarImpedimentos" | "registrarImpedimentosPuesto";
}

/** Dónde vive cada verificación en el expediente. */
const ETAPAS: Record<EtapaVerificacion, CamposEtapa> = {
  ucvmm: {
    resultado: (t) => t.con_impedimento,
    registrada: (s) => s.impedimentos_verificados,
    comentario: (s) => s.comentario_impedimentos,
    por: (s) => s.impedimentos_verificados_por,
    en: (s) => s.impedimentos_verificados_en,
    eventos: ["impedimentos", "impedimentos_corregidos"],
    metodo: "registrarImpedimentos",
  },
  puesto: {
    resultado: (t) => t.con_impedimento_puesto,
    registrada: (s) => s.impedimentos_puesto_verificados,
    comentario: (s) => s.comentario_impedimentos_puesto,
    por: (s) => s.impedimentos_puesto_por,
    en: (s) => s.impedimentos_puesto_en,
    eventos: ["impedimentos_puesto", "impedimentos_puesto_corregidos"],
    metodo: "registrarImpedimentosPuesto",
  },
};

export interface VerificacionImpedimentos {
  etapa: EtapaVerificacion;
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
  /** Lo guardado de esta etapa: el resultado de un tripulante, el comentario, quién y cuándo. */
  resultadoGuardado: (t: TripulanteSolicitud) => ResultadoImpedimento;
  comentarioGuardado: string | null;
  registradaPor: string | null;
  registradaEn: string | null;
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
  etapa: EtapaVerificacion = "ucvmm",
): VerificacionImpedimentos {
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();
  const campos = ETAPAS[etapa];

  const guardados = (): Record<number, ResultadoImpedimento> =>
    Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, campos.resultado(t)]));
  const [resultados, setResultados] = useState<Record<number, ResultadoImpedimento>>(guardados);
  const [comentario, setComentario] = useState(campos.comentario(solicitud) ?? "");
  // Registrada, la verificación es de solo lectura; cambiarla es una corrección con motivo.
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [motivoCorreccion, setMotivoCorreccion] = useState("");
  const [trabajando, setTrabajando] = useState(false);

  const registrada = campos.registrada(solicitud);
  const comentarioGuardado = campos.comentario(solicitud);
  const editable = !registrada || corrigiendo;
  const [eventoRegistro, eventoCorreccion] = campos.eventos;
  const corregida = [...solicitud.eventos].reverse()
    .find((e) => e.tipo === eventoRegistro || e.tipo === eventoCorreccion)?.tipo === eventoCorreccion;
  const pendientes = solicitud.tripulantes.filter((t) => resultados[t.id] == null).length;
  const conImpedimento = solicitud.tripulantes.filter((t) => campos.resultado(t)).map((t) => t.nombre_completo);
  const cambiados = solicitud.tripulantes.filter((t) => campos.resultado(t) !== null && resultados[t.id] !== campos.resultado(t));
  const hayCambios = solicitud.tripulantes.some((t) => resultados[t.id] !== campos.resultado(t))
    || comentario.trim() !== (comentarioGuardado ?? "");

  function marcar(tripulanteId: number, conImpedimentoNuevo: boolean) {
    setResultados((r) => ({ ...r, [tripulanteId]: conImpedimentoNuevo }));
  }

  function marcarTodosSin() {
    setResultados(Object.fromEntries(solicitud.tripulantes.map((t) => [t.id, false])));
  }

  function empezarCorreccion() {
    setResultados(guardados());
    setComentario(comentarioGuardado ?? "");
    setMotivoCorreccion("");
    setCorrigiendo(true);
  }

  function cancelarCorreccion() {
    setResultados(guardados());
    setComentario(comentarioGuardado ?? "");
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
            ? `${cambiados[0].nombre_completo} pasa de ${resultado(campos.resultado(cambiados[0]))} a ${resultado(resultados[cambiados[0].id])}.`
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
      onActualizada(await apiSolicitudes[campos.metodo](
        solicitud.id, lista, comentario.trim() || null, corrigiendo ? motivoCorreccion.trim() : null,
      ));
      mostrar(corrigiendo ? "Verificación de impedimentos corregida." : "Verificación de impedimentos registrada.", "exito");
      setCorrigiendo(false);
      setMotivoCorreccion("");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo registrar la verificación."), "error");
      await releerSiCambio(error, solicitud.id, onActualizada);   // ya decidida o finalizada por otra persona (409)
    } finally {
      setTrabajando(false);
    }
  }

  return {
    etapa, resultados, comentario, motivoCorreccion, registrada, corrigiendo, editable, corregida,
    pendientes, hayCambios, trabajando, conImpedimento,
    resultadoGuardado: campos.resultado, comentarioGuardado,
    registradaPor: campos.por(solicitud), registradaEn: campos.en(solicitud),
    marcar, marcarTodosSin, setComentario, setMotivoCorreccion, guardar, empezarCorreccion, cancelarCorreccion,
  };
}
