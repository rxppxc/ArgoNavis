import { Link } from "react-router-dom";
import type { Bandeja, SolicitudResumen } from "../../api/solicitudes";
import { IconoAlerta, IconoReloj } from "../../components/Iconos";
import { InsigniaEstado } from "./InsigniaEstado";
import { formatearFecha, formatearFechaHora, TEXTO_HORARIO_LABORAL, tiempoRestante } from "./presentacion";
import styles from "./TarjetaSolicitud.module.css";

/** Fila de las bandejas, como un pase (identidad «pase oficial», 2026-11-11): el
 *  talón con el número y el sello del estado, y los datos del trámite. Lleva al
 *  expediente. `conSector`: para quien ve los dos sectores (Administrador,
 *  supervisor general), el del puesto. */
export function TarjetaSolicitud({ s, vista, conSector = false }: { s: SolicitudResumen; vista: Bandeja; conSector?: boolean }) {
  const deAgencia = vista === "agencia";
  // Quien finaliza es el puesto de control: a la agencia le basta saber hasta cuándo vale.
  const plazo =
    s.estado === "returned" ? { etiqueta: "Corregir antes del", fecha: s.plazo_correccion }
    : s.estado === "approved" ? { etiqueta: deAgencia ? "Vigente hasta el" : "Finalizar antes del", fecha: s.vigente_hasta }
    : null;
  const restante = plazo ? tiempoRestante(plazo.fecha) : null;
  const conMarcas = s.tripulantes_con_alerta > 0 || s.tiene_nacionalidad_restringida || s.fuera_de_horario;

  return (
    // El enlace lleva el foco; el pase, dentro, lleva las muescas (una máscara
    // recortaría también el anillo de foco).
    <Link to={`/solicitudes/${s.id}`} className={styles.enlace}>
      <div className={`${styles.pase} ${styles[s.estado] ?? ""}`}>
        <div className={styles.talon}>
          <span className={styles.numero}><small>N.º</small>{s.numero ?? `#${s.id}`}</span>
          <InsigniaEstado estado={s.estado} inclinado />
        </div>

        <div className={styles.cuerpo}>
          <span className={styles.titulo}>{s.tipo_tramite_nombre}</span>
          <dl className={styles.datos}>
            {s.nombre_buque && <div><dt>Buque</dt><dd>{s.nombre_buque}</dd></div>}
            {s.imo && <div><dt>IMO</dt><dd className={styles.mono}>{s.imo}</dd></div>}
            {/* La agencia solo ve las suyas: su nombre en cada pase sobraba. */}
            {!deAgencia && <div><dt>Agencia</dt><dd>{s.agencia_nombre}</dd></div>}
            <div><dt>Puesto</dt><dd>{s.puesto_nombre}{conSector && s.sector_nombre && <> · {s.sector_nombre}</>}</dd></div>
            <div><dt>Operación</dt><dd className={styles.mono}>{formatearFecha(s.fecha_operacion)}</dd></div>
            <div><dt>Pasajeros</dt><dd className={styles.mono}>{s.cantidad_tripulantes}</dd></div>
            <div><dt>Enviada</dt><dd>{formatearFechaHora(s.enviada_en)}{!deAgencia && s.creada_por && <> por {s.creada_por}</>}</dd></div>
          </dl>

          {conMarcas && (
            <div className={styles.marcas}>
              {s.tripulantes_con_alerta > 0 && (
                <span className={styles.chipAlerta}>
                  <IconoAlerta tamano={11} /> {s.tripulantes_con_alerta} con documento vencido
                </span>
              )}
              {s.tiene_nacionalidad_restringida && <span className={styles.chipRestringida}>Nacionalidad restringida</span>}
              {/* Aprobada fuera del horario laboral, con su costo: también para la agencia (2026-11-11). */}
              {s.fuera_de_horario && (
                <span className={styles.chipHorario} title={`Aprobada fuera del horario laboral (${TEXTO_HORARIO_LABORAL})`}>
                  <IconoReloj tamano={11} /> Aprobada fuera del horario
                  {s.costo_fuera_de_horario && <> · {s.costo_fuera_de_horario}</>}
                </span>
              )}
            </div>
          )}

          {plazo && restante && (
            <div className={restante.vencido ? styles.plazoVencido : styles.plazo}>
              <IconoReloj tamano={12} /> {plazo.etiqueta} {formatearFechaHora(plazo.fecha)}
              {restante.vencido ? " — plazo vencido" : ` (${restante.frase})`}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
