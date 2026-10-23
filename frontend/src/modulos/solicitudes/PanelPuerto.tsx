import { useEffect, useState } from "react";
import { apiCatalogos, type PuestoMini } from "../../api/catalogos";
import { apiSolicitudes, type SolicitudDetalle } from "../../api/solicitudes";
import { IconoExito } from "../../components/Iconos";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { mensajeDeError } from "../../utils/errores";
import { formatearFechaHora } from "./presentacion";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  onActualizada: (s: SolicitudDetalle) => void;
}

/** Panel del puesto de control: un solo paso que registra lo ocurrido (con
 *  fecha, hora y usuario automáticos), indica en qué puesto terminó la
 *  operación y cierra la autorización. */
export function PanelPuerto({ solicitud, onActualizada }: Props) {
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();
  const [comentario, setComentario] = useState("");
  const [puestos, setPuestos] = useState<PuestoMini[]>([]);
  const [puestoId, setPuestoId] = useState<number>(solicitud.puesto_control_id);
  const [trabajando, setTrabajando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    apiCatalogos.listarPuestos()
      .then((lista) => { if (!cancelado) setPuestos(lista); })
      .catch(() => { /* sin la lista se finaliza en el puesto autorizado */ });
    return () => { cancelado = true; };
  }, []);

  const otroPuesto = puestoId !== solicitud.puesto_control_id;
  const nombrePuesto = puestos.find((p) => p.id === puestoId)?.nombre ?? solicitud.puesto_nombre;

  async function finalizar() {
    const texto = comentario.trim();
    if (texto.length < 3) {
      mostrar("Escribe el comentario de la operación (al menos 3 caracteres).", "aviso");
      return;
    }
    const ok = await confirmar({
      titulo: "Finalizar solicitud",
      mensaje: `Se registrará la operación con tu comentario como finalizada en ${nombrePuesto}`
        + `${otroPuesto ? ` (la autorización era para ${solicitud.puesto_nombre})` : ""} y la autorización quedará cerrada.`,
      textoOk: "Finalizar",
      tono: "finalizar",
    });
    if (!ok) return;
    setTrabajando(true);
    try {
      onActualizada(await apiSolicitudes.finalizar(solicitud.id, texto, puestoId));
      setComentario("");
      mostrar("Solicitud finalizada.", "exito");
    } catch (error) {
      mostrar(mensajeDeError(error, "No se pudo finalizar."), "error");
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <section className={`${styles.panel} ${styles.panelAccion}`}>
      <h2 className={styles.panelTitulo}>Puesto de control</h2>
      <p className={styles.ayuda}>
        Registra lo ocurrido en la operación y finalízala. Queda con la fecha, la hora y tu usuario.
        Debe finalizarse antes del {formatearFechaHora(solicitud.vigente_hasta)} o la autorización expira.
      </p>
      <label className={styles.etiqueta} htmlFor="comentario-puerto">Comentario de la operación *</label>
      <textarea id="comentario-puerto" className={styles.textarea} rows={3} maxLength={2000} value={comentario}
        placeholder="Ej. Tripulantes presentados en garita, desembarque sin novedad…"
        onChange={(e) => setComentario(e.target.value)} />
      <label className={styles.etiqueta} htmlFor="puesto-finalizacion">Puesto donde finalizó la operación</label>
      <select id="puesto-finalizacion" className={styles.select} value={puestoId}
        onChange={(e) => setPuestoId(Number(e.target.value))}>
        {!puestos.some((p) => p.id === solicitud.puesto_control_id) && (
          <option value={solicitud.puesto_control_id}>{solicitud.puesto_nombre}</option>
        )}
        {puestos.map((p) => (
          <option key={p.id} value={p.id}>
            {p.nombre}{p.id === solicitud.puesto_control_id ? " (autorizado)" : ""}
          </option>
        ))}
      </select>
      {otroPuesto && (
        <p className={styles.ayuda}>La operación terminó en otro puesto: así quedará en el expediente y en la autorización.</p>
      )}
      {/* A todo el ancho, como las decisiones de UCVMM: es la acción del panel. */}
      <button type="button" className={`${styles.btnFinalizar} ${styles.anchoCompleto}`} onClick={finalizar} disabled={trabajando}>
        <IconoExito tamano={15} /> {trabajando ? "Finalizando…" : "Finalizar"}
      </button>
    </section>
  );
}
