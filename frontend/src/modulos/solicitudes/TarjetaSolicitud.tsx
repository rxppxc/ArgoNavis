import { Link } from "react-router-dom";
import type { Bandeja, SolicitudResumen } from "../../api/solicitudes";
import { IconoAlerta, IconoBarco, IconoReloj, IconoUsuario } from "../../components/Iconos";
import { InsigniaEstado } from "./InsigniaEstado";
import { formatearFecha, formatearFechaHora, tiempoRestante } from "./presentacion";
import styles from "./TarjetaSolicitud.module.css";

/** Fila de las bandejas: lleva al expediente de la solicitud. */
export function TarjetaSolicitud({ s, vista }: { s: SolicitudResumen; vista: Bandeja }) {
  const deAgencia = vista === "agencia";
  // Quien finaliza es el puesto de control: a la agencia le basta saber hasta cuándo vale.
  const plazo =
    s.estado === "returned" ? { etiqueta: "Corregir antes del", fecha: s.plazo_correccion }
    : s.estado === "approved" ? { etiqueta: deAgencia ? "Vigente hasta el" : "Finalizar antes del", fecha: s.vigente_hasta }
    : null;
  const restante = plazo ? tiempoRestante(plazo.fecha) : null;

  return (
    <Link to={`/solicitudes/${s.id}`} className={`${styles.tarjeta} ${styles[s.estado] ?? ""}`}>
      <div className={styles.filaSuperior}>
        <span className={styles.numero}>{s.numero ?? `#${s.id}`}</span>
        <InsigniaEstado estado={s.estado} />
        {s.tripulantes_con_alerta > 0 && (
          <span className={styles.chipAlerta}>
            <IconoAlerta tamano={11} /> {s.tripulantes_con_alerta} con documento vencido
          </span>
        )}
        {s.tiene_nacionalidad_restringida && <span className={styles.chipRestringida}>Nacionalidad restringida</span>}
      </div>

      <div className={styles.titulo}>
        {s.tipo_tramite_nombre}
        {s.nombre_buque && <span className={styles.buque}><IconoBarco tamano={14} /> {s.nombre_buque}{s.imo && ` · IMO ${s.imo}`}</span>}
      </div>

      <div className={styles.meta}>
        {/* La agencia solo ve las suyas: su nombre en cada tarjeta sobraba. */}
        {!deAgencia && <span>{s.agencia_nombre}</span>}
        <span>{s.puesto_nombre}</span>
        <span>Operación: {formatearFecha(s.fecha_operacion)}</span>
        <span><IconoUsuario tamano={12} /> {s.cantidad_tripulantes} tripulante{s.cantidad_tripulantes === 1 ? "" : "s"}</span>
        <span>
          Enviada {formatearFechaHora(s.enviada_en)}
          {!deAgencia && s.creada_por && <> por {s.creada_por}</>}
        </span>
      </div>

      {plazo && restante && (
        <div className={restante.vencido ? styles.plazoVencido : styles.plazo}>
          <IconoReloj tamano={12} /> {plazo.etiqueta} {formatearFechaHora(plazo.fecha)}
          {restante.vencido ? " — plazo vencido" : ` (${restante.frase})`}
        </div>
      )}
    </Link>
  );
}
