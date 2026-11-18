import { Link } from "react-router-dom";
import type { Bandeja, SolicitudResumen } from "../../../api/solicitudes";
import { IconoAlerta, IconoReloj } from "../../../components/Iconos";
import { InsigniaEstado } from "../InsigniaEstado";
import {
  ETIQUETA_OPERACION, formatearFecha, formatearFechaHora, TEXTO_HORARIO_LABORAL, textoDias, textoPuestos,
  tiempoRestante,
} from "../presentacion";
import styles from "./TarjetaSolicitud.module.css";

/** Fila de las bandejas, como un pase (identidad «pase oficial», 2026-11-11): el
 *  talón con el número y el sello del estado, y los datos del trámite. Lleva al
 *  expediente. `conSector`: para quien ve los dos sectores (Administrador,
 *  supervisor general), el del puesto. */
export function TarjetaSolicitud({ s, vista, volverA, conSector = false }: {
  s: SolicitudResumen; vista: Bandeja; conSector?: boolean;
  /** La bandeja y la pestaña de donde se abre: el «Volver» del expediente regresa ahí. */
  volverA?: string;
}) {
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
    <Link to={`/solicitudes/${s.id}`} state={volverA ? { volverA } : undefined} className={styles.enlace}>
      {/* data-estado: el color de su estado en el borde y el talón (rediseño del 2026-11-17). */}
      <div className={`${styles.pase} ${styles[s.estado] ?? ""}`} data-estado={s.estado}>
        <div className={styles.talon}>
          <span className={styles.numero}><small>N.º</small>{s.numero ?? `#${s.id}`}</span>
          <InsigniaEstado estado={s.estado} inclinado />
        </div>

        <div className={styles.cuerpo}>
          {/* Con la operación del trámite de Técnico o los días del sellado de Shore Pass al lado (2026-11-18). */}
          <span className={styles.titulo}>
            {s.tipo_tramite_nombre}
            {s.operacion && <> · {ETIQUETA_OPERACION[s.operacion]}</>}
            {s.dias_sellado && <> · {textoDias(s.dias_sellado)}</>}
          </span>
          <dl className={styles.datos}>
            {s.nombre_buque && <div><dt>Buque</dt><dd>{s.nombre_buque}</dd></div>}
            {s.imo && <div><dt>IMO</dt><dd className={styles.mono}>{s.imo}</dd></div>}
            {/* La agencia solo ve las suyas: su nombre en cada pase sobraba. */}
            {!deAgencia && <div><dt>Agencia</dt><dd>{s.agencia_nombre}</dd></div>}
            <div><dt>Puesto</dt><dd>{textoPuestos(s)}{conSector && s.sector_nombre && <> · {s.sector_nombre}</>}</dd></div>
            <div><dt>Operación</dt><dd className={styles.mono}>{formatearFecha(s.fecha_operacion)}</dd></div>
            <div><dt>Pasajeros</dt><dd className={styles.mono}>{s.cantidad_tripulantes}</dd></div>
            <div><dt>Enviada</dt><dd>{formatearFechaHora(s.enviada_en)}{!deAgencia && s.creada_por && <> por {s.creada_por}</>}</dd></div>
          </dl>

          {conMarcas && (
            <div className={styles.marcas}>
              {s.tripulantes_con_alerta > 0 && (
                <span className={styles.chipAlerta}>
                  <IconoAlerta tamano={11} /> {s.tripulantes_con_alerta} con documento vencido o por vencer
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
