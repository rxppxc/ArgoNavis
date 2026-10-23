import type { ReactNode } from "react";
import type { PuestoMini } from "../../api/catalogos";
import type { TipoTramite } from "../../api/tramites";
import { AYUDA_CAMPOS_TRAMITE, formatearFechaHora } from "./presentacion";
import { operacionMaxima, type CabeceraFormulario } from "./validacionFormulario";
import styles from "./PaginaSolicitud.module.css";

interface Props {
  tipo:         TipoTramite;
  cabecera:     CabeceraFormulario;
  agencia:      string;
  /** Al corregir, la de la solicitud; en una nueva, la hora actual (la que
   *  queda es la del servidor al enviar). */
  fechaSolicitud: string;
  puestos:      PuestoMini[];
  opcionesPais: ReactNode;
  hoy:          string;
  onCambiar:    (campo: keyof CabeceraFormulario, valor: string) => void;
}

/** Paso 2 del formulario: el puesto, la fecha de la operación y lo que pide el
 *  trámite (buque, puerto, clínica, motivo), con las aclaraciones del Form. 3. */
export function DatosTramite({ tipo, cabecera, agencia, fechaSolicitud, puestos, opcionesPais, hoy, onCambiar }: Props) {
  const ayuda = AYUDA_CAMPOS_TRAMITE[tipo.codigo];
  return (
    <section className={styles.bloque}>
      <div className={styles.bloqueTitulo}><span className={styles.paso}>2</span> Datos del trámite</div>
      <div className={styles.grid}>
        <div className={styles.campo}>
          <span>Agencia naviera</span>
          <input type="text" value={agencia} readOnly disabled />
        </div>
        <div className={styles.campo}>
          <span>Fecha y hora de solicitud</span>
          <input type="text" value={formatearFechaHora(fechaSolicitud)} readOnly disabled />
        </div>
        <label className={styles.campo}>
          <span>Puesto de Control Migratorio *</span>
          <select value={cabecera.puesto_control_id}
            onChange={(e) => onCambiar("puesto_control_id", e.target.value)}>
            <option value="">{puestos.length ? "Selecciona…" : "No hay puestos configurados"}</option>
            {puestos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </label>
        <label className={styles.campo}>
          <span>Fecha de la operación en puerto *</span>
          <input type="date" min={hoy} max={operacionMaxima(hoy)} value={cabecera.fecha_operacion}
            onChange={(e) => onCambiar("fecha_operacion", e.target.value)} />
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
              <input type="text" maxLength={20} placeholder="IMO 9074729" value={cabecera.imo}
                onChange={(e) => onCambiar("imo", e.target.value)} />
            </label>
            <label className={styles.campo}>
              <span>Bandera *</span>
              <select value={cabecera.bandera} onChange={(e) => onCambiar("bandera", e.target.value)}>
                <option value="">Selecciona…</option>
                {opcionesPais}
              </select>
            </label>
          </>
        )}
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
      </div>
    </section>
  );
}
