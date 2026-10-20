import type { SolicitudDetalle, TripulanteSolicitud } from "../../api/solicitudes";
import BarraProgreso from "../../components/BarraProgreso";
import { IconoArchivo, IconoCheck } from "../../components/Iconos";
import { ETIQUETA_RANGO, ETIQUETA_SEXO, formatearFecha, formatearFechaHora } from "./presentacion";
import type { VerificacionImpedimentos } from "./useVerificacionImpedimentos";
import styles from "./DetalleSolicitud.module.css";

interface Props {
  solicitud: SolicitudDetalle;
  /** Solo para quien revisa (UCVMM): agrega la columna de impedimentos. */
  verificacion: VerificacionImpedimentos | null;
  onVerDocumentacion: (tripulante: TripulanteSolicitud) => void;
}

/** Tripulantes del expediente. Para UCVMM lleva además la verificación de
 *  impedimentos en SIMPLUS, tripulante por tripulante: antes se marcaba en un
 *  panel aparte que repetía la lista y, con tripulaciones grandes, dejaba la
 *  decisión muy abajo. */
export function SeccionTripulantes({ solicitud: s, verificacion: v, onVerDocumentacion }: Props) {
  const total = s.tripulantes.length;
  const marcados = v ? total - v.pendientes : 0;

  return (
    <section className={styles.panel}>
      <h2 className={styles.panelTitulo}>
        Tripulantes <span className={styles.contador}>{total}</span>
      </h2>
      {s.valida_vigencia && (
        <p className={styles.ayuda}>Este trámite exige pasaporte y seamanbook vigentes a la fecha de la operación.</p>
      )}

      {v && (
        <div className={styles.verifCabecera}>
          <div>
            <div className={styles.verifTitulo}>
              {v.corrigiendo ? "Corrección de la verificación de impedimentos" : "Verificación de impedimentos en SIMPLUS"}
            </div>
            <div className={styles.progreso}>
              <div className={styles.progresoBarra}>
                <BarraProgreso valor={v.editable ? marcados : total} max={total} color="green" />
              </div>
              <span>{v.editable ? `${marcados} de ${total} marcados` : `${total} de ${total} verificados`}</span>
            </div>
          </div>
          {v.editable && (
            <button type="button" className={styles.btnPequeno} onClick={v.marcarTodosSin}>
              <IconoCheck tamano={13} /> Marcar todos sin impedimento
            </button>
          )}
        </div>
      )}

      <div className={styles.tablaScroll}>
        <table className={styles.tabla}>
          <thead>
            <tr>
              <th>#</th>
              <th>Tripulante</th>
              <th>Nacionalidad</th>
              <th>Pasaporte</th>
              <th>Seamanbook</th>
              {/* Para UCVMM el rango va debajo del nombre y deja lugar a la columna de impedimentos. */}
              {!v && <th>Rango / ocupación</th>}
              <th>Documentos</th>
              {v && <th>Impedimento</th>}
            </tr>
          </thead>
          <tbody>
            {s.tripulantes.map((m, i) => {
              const faltan = s.checklist.filter((c) => c.tripulante_id === m.id && !c.cubierta).length;
              const adjuntos = s.documentos.filter((d) => d.tripulante_id === m.id).length;
              // Mientras se marca, lo que se va eligiendo; ya registrada, lo guardado.
              const resultado = v ? (v.editable ? v.resultados[m.id] : m.con_impedimento) : null;
              // data-etiqueta: el título de cada dato cuando la tabla pasa a fichas en el celular.
              return (
                <tr key={m.id} className={resultado === true ? styles.filaConImpedimento : undefined}>
                  <td className={styles.celdaOrden}>{i + 1}</td>
                  <td className={styles.celdaAncha}>
                    <div className={styles.celdaPrincipal}>{m.nombre_completo}</div>
                    {v && <div className={styles.celdaSecundaria}>{ETIQUETA_RANGO[m.rango]} · {m.ocupacion}</div>}
                    <div className={styles.celdaSecundaria}>
                      {ETIQUETA_SEXO[m.sexo]} · Nacimiento: {formatearFecha(m.fecha_nacimiento)}
                      {m.pais_nacimiento_nombre && <> · {m.pais_nacimiento_nombre}</>}
                    </div>
                    {/* Solo llega al personal del SNM: a la agencia el backend le manda null.
                        Quien revisa lo ve en su columna. */}
                    {!v && m.con_impedimento && <span className={styles.chipImpedimento}>Con impedimento</span>}
                  </td>
                  <td data-etiqueta="Nacionalidad">
                    {m.nacionalidad_nombre ?? m.nacionalidad}
                    {m.nacionalidad_restringida && s.tipo_tramite_aviso_custodia && (
                      <div className={styles.chipRestringida}>Restringida</div>
                    )}
                  </td>
                  <td data-etiqueta="Pasaporte">
                    <div className={styles.celdaPrincipal}>{m.pasaporte}</div>
                    <div className={m.pasaporte_vencido ? styles.vencido : styles.celdaSecundaria}>
                      Vence {formatearFecha(m.pasaporte_expira)}{m.pasaporte_vencido && " — vencido"}
                    </div>
                  </td>
                  <td data-etiqueta="Seamanbook">
                    {m.porta_libreta ? (
                      <>
                        <div className={styles.celdaPrincipal}>{m.libreta_marino ?? "—"}</div>
                        <div className={m.libreta_vencida ? styles.vencido : styles.celdaSecundaria}>
                          Vence {formatearFecha(m.libreta_expira)}{m.libreta_vencida && " — vencido"}
                        </div>
                      </>
                    ) : (
                      <span className={styles.celdaSecundaria}>No aplica</span>
                    )}
                  </td>
                  {!v && (
                    <td data-etiqueta="Rango / ocupación">
                      <div className={styles.celdaPrincipal}>{ETIQUETA_RANGO[m.rango]}</div>
                      <div className={styles.celdaSecundaria}>{m.ocupacion}</div>
                    </td>
                  )}
                  <td className={v ? undefined : styles.celdaAncha} data-etiqueta={v ? "Documentos" : undefined}>
                    <button type="button" className={styles.btnDocumentacion} onClick={() => onVerDocumentacion(m)}
                      aria-label={`Ver documentación de ${m.nombre_completo}`}>
                      <IconoArchivo tamano={13} />
                      <span>{adjuntos > 0 ? `Ver ${adjuntos} documento${adjuntos === 1 ? "" : "s"}` : "Ver documentación"}</span>
                    </button>
                    {faltan > 0 && (
                      <div className={styles.textoFalta}>
                        {faltan === 1 ? "Falta 1 documento" : `Faltan ${faltan} documentos`}
                      </div>
                    )}
                  </td>
                  {v && (
                    <td className={styles.celdaAncha} data-etiqueta="Impedimento en SIMPLUS">
                      <div className={styles.segmento} role="radiogroup"
                        aria-label={`Impedimento de ${m.nombre_completo} en SIMPLUS`}>
                        {([false, true] as const).map((con) => (
                          <label key={String(con)} title={con ? "Con impedimento" : "Sin impedimento"}
                            className={[
                              styles.segmentoOpcion,
                              resultado === con && (con ? styles.segmentoCon : styles.segmentoSin),
                              !v.editable && styles.segmentoFijo,
                            ].filter(Boolean).join(" ")}>
                            <input type="radio" className="sr-only" name={`impedimento-${m.id}`}
                              checked={resultado === con} disabled={!v.editable}
                              onChange={() => v.marcar(m.id, con)} />
                            {con ? "Con" : "Sin"}
                          </label>
                        ))}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {v && <PieVerificacion solicitud={s} verificacion={v} />}
    </section>
  );
}

/** Debajo de la tabla: comentario y guardar mientras se marca; ya registrada,
 *  quién la hizo y la opción de corregirla. */
function PieVerificacion({ solicitud: s, verificacion: v }: { solicitud: SolicitudDetalle; verificacion: VerificacionImpedimentos }) {
  if (!v.editable) {
    return (
      <div className={styles.verifPie}>
        {s.comentario_impedimentos && (
          <div className={styles.observaciones}>
            <span>Comentario de la verificación</span>
            {s.comentario_impedimentos}
          </div>
        )}
        <div className={styles.filaBotones}>
          <p className={styles.verificacionRegistrada}>
            <IconoCheck tamano={13} />
            {v.corregida ? "Corregida" : "Registrada"} por {s.impedimentos_verificados_por ?? "—"} el{" "}
            {formatearFechaHora(s.impedimentos_verificados_en)}
          </p>
          <button type="button" className={styles.btnSecundario} onClick={v.empezarCorreccion} disabled={v.trabajando}>
            Corregir verificación
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.verifPie}>
      <textarea className={styles.textarea} rows={2} maxLength={2000} aria-label="Comentario de la verificación"
        placeholder="Comentario de la verificación (opcional)"
        value={v.comentario} onChange={(e) => v.setComentario(e.target.value)} />
      {v.corrigiendo && (
        <div>
          <label className={styles.etiqueta} htmlFor="motivo-correccion">Motivo de la corrección *</label>
          <textarea id="motivo-correccion" className={styles.textarea} rows={2} maxLength={2000}
            placeholder="Ej. se revisó de nuevo en SIMPLUS"
            value={v.motivoCorreccion} onChange={(e) => v.setMotivoCorreccion(e.target.value)} />
        </div>
      )}
      <div className={styles.filaBotones}>
        {v.pendientes > 0 && (
          <span className={styles.ayuda}>
            Falta marcar {v.pendientes} tripulante{v.pendientes === 1 ? "" : "s"}.
          </span>
        )}
        {v.corrigiendo && (
          <button type="button" className={styles.btnTexto} onClick={v.cancelarCorreccion} disabled={v.trabajando}>
            Cancelar
          </button>
        )}
        <button type="button" className={styles.btnPrimario} onClick={v.guardar}
          disabled={v.trabajando || v.pendientes > 0 || !v.hayCambios}
          title={v.pendientes > 0 ? "Marca el resultado de todos los tripulantes"
            : v.hayCambios ? undefined : "No hay cambios que guardar"}>
          {v.corrigiendo ? "Guardar corrección" : "Guardar verificación"}
        </button>
      </div>
    </div>
  );
}
