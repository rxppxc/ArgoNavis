import type { PuestoMini } from "../../../api/catalogos";
import type { TipoTramite } from "../../../api/tramites";
import { SelectorBuscable } from "../../../components/SelectorBuscable";
import { SelectorFecha } from "../../../components/SelectorFecha";
import type { OpcionBuscable } from "../../../utils/busqueda";
import { isoATexto, sumarDias } from "../../../utils/calendario";
import { DIAS_SELLADO, OPERACIONES } from "../../../api/tiposSolicitudes";
import {
  AYUDA_CAMPOS_TRAMITE, avisoSubirYBajar, ETIQUETA_OPERACION, formatearFechaHora, textoDias, textoVigencia,
} from "../presentacion";
import { operacionMaxima, puestosParaCambio, type CabeceraFormulario } from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

interface Props {
  tipo:         TipoTramite;
  cabecera:     CabeceraFormulario;
  agencia:      string;
  /** Al corregir, la de la solicitud; en una nueva, la hora actual (la que
   *  queda es la del servidor al enviar). */
  fechaSolicitud: string;
  puestos:      PuestoMini[];
  opcionesPais: OpcionBuscable[];
  hoy:          string;
  onCambiar:    (campo: keyof CabeceraFormulario, valor: string) => void;
}

/** Paso 2 del formulario: la agencia y la fecha, el buque, la fecha de la operación y
 *  el puesto, lo que pide el trámite (puerto, clínica, motivo), con las aclaraciones
 *  del Form. 3, la operación del trámite de Técnico (2026-11-18), «¿Subir y bajar?»
 *  (2026-11-16) y al final el cambio de puerto (orden pedido el 2026-11-13). */
export function DatosTramite({ tipo, cabecera, agencia, fechaSolicitud, puestos, opcionesPais, hoy, onCambiar }: Props) {
  const ayuda = AYUDA_CAMPOS_TRAMITE[tipo.codigo];
  // El cambio de puerto, solo en los trámites que lo admiten (Embarque y Desembarque, 2026-11-13).
  const ofreceCambio = tipo.permite_cambio_puerto;
  const conCambio = ofreceCambio && cabecera.cambio_puerto === "si";
  const paraCambio = puestosParaCambio(puestos, cabecera.puesto_control_id);
  const destino = puestos.find((p) => String(p.id) === cabecera.puesto_destino_id);

  /** Otro puesto elegido: el del cambio se quita si pasa a ser el mismo. */
  function elegirPuesto(id: string) {
    onCambiar("puesto_control_id", id);
    if (cabecera.puesto_destino_id && !puestosParaCambio(puestos, id).some((p) => String(p.id) === cabecera.puesto_destino_id)) {
      onCambiar("puesto_destino_id", "");
    }
  }

  function elegirCambio(valor: string) {
    onCambiar("cambio_puerto", valor);
    if (valor !== "si") onCambiar("puesto_destino_id", "");
  }

  return (
    <section className={styles.bloque} id="paso-datos">
      <div className={styles.bloqueTitulo}><span className={styles.paso}>2</span> Datos del trámite</div>
      <div className={styles.grid}>
        <label className={styles.campo}>
          <span>Agencia naviera</span>
          <input type="text" value={agencia} readOnly disabled />
        </label>
        <label className={styles.campo}>
          <span>Fecha y hora de solicitud</span>
          <input type="text" value={formatearFechaHora(fechaSolicitud)} readOnly disabled />
        </label>
        {tipo.requiere_buque && (
          <>
            <label className={styles.campo}>
              <span>Nombre del buque *</span>
              <input type="text" maxLength={255} placeholder={ayuda?.buque} value={cabecera.nombre_buque}
                onChange={(e) => onCambiar("nombre_buque", e.target.value)} />
            </label>
            <label className={styles.campo}>
              <span>IMO * <em>(7 dígitos)</em></span>
              <input type="text" maxLength={20} placeholder="Ej. IMO 9074729" value={cabecera.imo}
                onChange={(e) => onCambiar("imo", e.target.value)} />
            </label>
            <SelectorBuscable className={styles.campo} etiqueta="Bandera *" opciones={opcionesPais}
              valor={cabecera.bandera} onCambiar={(valor) => onCambiar("bandera", valor)} />
          </>
        )}
        {/* De hoy a un año (DIAS_MAXIMOS_ANTICIPACION): lo demás va rayado en el calendario y,
            si se escribe, el campo dice por qué no vale. */}
        <SelectorFecha className={styles.campo} etiqueta="Fecha de la operación en puerto *"
          valor={cabecera.fecha_operacion} onCambiar={(iso) => onCambiar("fecha_operacion", iso)}
          min={hoy} max={operacionMaxima(hoy)}
          motivoAntes="Esa fecha ya pasó: la operación es de hoy en adelante."
          motivoDespues={`La operación puede ser hasta un año después de hoy (el ${isoATexto(operacionMaxima(hoy))}).`}
          ayuda={`Desde hoy hasta el ${isoATexto(operacionMaxima(hoy))} (un año).`}
          atajos={[{ etiqueta: "Hoy", fecha: hoy }, { etiqueta: "Mañana", fecha: sumarDias(hoy, 1) }]} />
        <label className={styles.campo}>
          <span>Puesto de Control Migratorio *</span>
          <select value={cabecera.puesto_control_id}
            onChange={(e) => elegirPuesto(e.target.value)}>
            <option value="">{puestos.length ? "Selecciona…" : "No hay puestos configurados"}</option>
            {puestos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </label>
        {tipo.requiere_puerto && (
          <label className={styles.campo}>
            <span>Nombre del puerto *</span>
            <input type="text" maxLength={255} placeholder={ayuda?.puerto} value={cabecera.nombre_puerto}
              onChange={(e) => onCambiar("nombre_puerto", e.target.value)} />
          </label>
        )}
        {tipo.requiere_puerto_desembarque && (
          <label className={styles.campo}>
            <span>Puerto de desembarque *</span>
            <input type="text" maxLength={255} value={cabecera.puerto_desembarque}
              onChange={(e) => onCambiar("puerto_desembarque", e.target.value)} />
          </label>
        )}
        {tipo.requiere_clinica && (
          <label className={styles.campo}>
            <span>Clínica u hospital *</span>
            <input type="text" maxLength={255} placeholder="Donde será llevado el tripulante"
              value={cabecera.clinica_hospital}
              onChange={(e) => onCambiar("clinica_hospital", e.target.value)} />
          </label>
        )}
        {tipo.requiere_motivo && (
          <label className={styles.campo}>
            <span>Motivo * <em>(Tribunal ACP, compras, otros)</em></span>
            <input type="text" maxLength={2000} value={cabecera.motivo}
              onChange={(e) => onCambiar("motivo", e.target.value)} />
          </label>
        )}
        {/* La operación del trámite de Técnico (pedido del usuario del 2026-11-18): obligatoria y empieza
            sin elegir. La Carta de Responsabilidad, una por solicitud, va con toda operación desde el
            2026-11-27 (antes, solo con «Subir y bajar»). */}
        {tipo.pide_operacion && (
          <label className={styles.campo}>
            <span>Operación *</span>
            <select value={cabecera.operacion} onChange={(e) => onCambiar("operacion", e.target.value)}>
              <option value="">Selecciona…</option>
              {/* Las del trámite: «Subir y bajar», solo el de Técnico (2026-11-26). */}
              {OPERACIONES.filter((o) => !tipo.operaciones || tipo.operaciones.includes(o))
                .map((o) => <option key={o} value={o}>{ETIQUETA_OPERACION[o]}</option>)}
            </select>
          </label>
        )}
        {/* Lo que «Subir y bajar» suma en el trámite de Técnico: la carta de garantía de la agencia
            contratante, una por solicitud (hasta el 2026-11-27, también la Carta Form. 7, que desde
            entonces va con toda operación). En Urgencia médica la operación solo se registra. */}
        {tipo.pide_operacion && cabecera.operacion === "subir_y_bajar" && avisoSubirYBajar(tipo.documentos) && (
          <p className={styles.operacionAviso}>{avisoSubirYBajar(tipo.documentos)}</p>
        )}
        {tipo.horas_vigencia && (
          <p className={styles.operacionAviso}>
            La autorización de este trámite vale <strong>{textoVigencia(tipo.horas_vigencia)}</strong>.
          </p>
        )}
        {/* Los días del sellado de Shore Pass (pedido del usuario del 2026-11-18): obligatorios, empiezan
            sin elegir y no cambian los documentos ni la vigencia. */}
        {tipo.pide_dias_sellado && (
          <label className={styles.campo}>
            <span>Días del sellado *</span>
            <select value={cabecera.dias_sellado} onChange={(e) => onCambiar("dias_sellado", e.target.value)}>
              <option value="">Selecciona…</option>
              {DIAS_SELLADO.map((d) => <option key={d} value={d}>{textoDias(d)}</option>)}
            </select>
          </label>
        )}
        {/* «¿Subir y bajar?» (Sí / No), en los trámites que lo pregunten: con «Sí», cada tripulante adjunta
            la Carta de Responsabilidad. Embarque y Desembarque lo preguntaron del 2026-11-16 al 18; desde
            entonces, ninguno («Subir y bajar» es una operación del trámite de Técnico). */}
        {tipo.permite_subir_y_bajar && (
          <div className={styles.subirBajar} role="group" aria-label="Subir y bajar">
            <label className={styles.campo}>
              <span>¿Subir y bajar? *</span>
              <select value={cabecera.subir_y_bajar} onChange={(e) => onCambiar("subir_y_bajar", e.target.value)}>
                <option value="no">No</option>
                <option value="si">Sí</option>
              </select>
            </label>
            {cabecera.subir_y_bajar === "si" && (
              <p className={styles.subirBajarAviso}>
                Cada tripulante adjunta la <strong>Carta de Responsabilidad (Form. No. 7)</strong> en sus documentos.
              </p>
            )}
          </div>
        )}
        {/* Al final (pedido del 2026-11-13): la pregunta y el nuevo puesto, juntos; con «Sí», el
            nuevo aparece al lado, y debajo su aviso. Sin nombrar los sectores: lo lee la agencia. */}
        {ofreceCambio && (
        <div className={styles.cambioPuerto} role="group" aria-label="Cambio de puerto">
          <label className={styles.campo}>
            <span>¿Cambio de puerto? *</span>
            <select value={cabecera.cambio_puerto} onChange={(e) => elegirCambio(e.target.value)}>
              <option value="no">No</option>
              <option value="si">Sí</option>
            </select>
          </label>
          {conCambio && (
            <label className={styles.campo}>
              <span>Nuevo puesto de control *</span>
              <select value={cabecera.puesto_destino_id} disabled={!cabecera.puesto_control_id}
                onChange={(e) => onCambiar("puesto_destino_id", e.target.value)}>
                <option value="">
                  {!cabecera.puesto_control_id ? "Elige primero el puesto de control"
                    : paraCambio.length ? "Selecciona…" : "No hay otros puestos disponibles"}
                </option>
                {paraCambio.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </label>
          )}
          {conCambio && (
            <p className={styles.cambioPuertoAviso}>
              La autorización vale para el nuevo puesto de control
              {destino ? <> (<strong>{destino.nombre}</strong>)</> : null}, donde se finaliza.
            </p>
          )}
        </div>
        )}
      </div>
      {/* Con cambio de puerto, su aviso va en su recuadro. */}
      {!conCambio && (
        <div className={styles.nota}>
          La autorización vale solo para el puesto de control que elijas. Si la operación se realiza en otro puesto,
          deberás presentar una nueva solicitud.
        </div>
      )}
    </section>
  );
}
