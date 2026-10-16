/**
 * Verificación pública de una Autorización Marítima (destino del QR del PDF).
 * No requiere sesión: muestra lo mínimo para comprobar que la autorización
 * existe y si sigue vigente, con los pasaportes enmascarados.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiSolicitudes, type VerificacionAutorizacion } from "../../api/solicitudes";
import { MarcoPagina } from "../../components/MarcoPagina";
import { IconoAlerta, IconoExito, IconoXCirculo } from "../../components/Iconos";
import { mensajeDeError } from "../../utils/errores";
import { ETIQUETA_ESTADO, ETIQUETA_RANGO, formatearFecha, formatearFechaHora } from "./presentacion";
import styles from "./PaginaVerificacion.module.css";

export default function PaginaVerificacion() {
  const { codigo = "" } = useParams<{ codigo: string }>();
  const [datos, setDatos] = useState<VerificacionAutorizacion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    apiSolicitudes.verificar(codigo)
      .then((d) => { if (!cancelado) setDatos(d); })
      .catch((e) => { if (!cancelado) setError(mensajeDeError(e, "No se pudo verificar la autorización.")); });
    return () => { cancelado = true; };
  }, [codigo]);

  return (
    <MarcoPagina publica>
      <div className={styles.contenedor}>
        <h1 className={styles.titulo}>Verificación de Autorización Marítima</h1>

        {!datos && !error && <div className={styles.cargando}>Verificando…</div>}

        {error && (
          <div className={`${styles.resultado} ${styles.invalida}`}>
            <IconoXCirculo tamano={34} />
            <div>
              <div className={styles.resultadoTitulo}>Autorización no encontrada</div>
              <div className={styles.resultadoTexto}>{error}</div>
            </div>
          </div>
        )}

        {datos && (
          <>
            <div className={`${styles.resultado} ${datos.valida ? styles.valida : styles.invalida}`}>
              {datos.valida ? <IconoExito tamano={34} /> : <IconoAlerta tamano={34} />}
              <div>
                <div className={styles.resultadoTitulo}>
                  {datos.valida
                    ? datos.estado === "finalized" ? "Autorización auténtica — operación finalizada" : "Autorización auténtica y vigente"
                    : "Autorización no vigente"}
                </div>
                <div className={styles.resultadoTexto}>
                  Estado: {ETIQUETA_ESTADO[datos.estado] ?? datos.estado}
                  {datos.estado === "approved" && datos.vigente_hasta && <> — vigente hasta el {formatearFechaHora(datos.vigente_hasta)}</>}
                  {datos.estado === "finalized" && <> — finalizada el {formatearFechaHora(datos.finalizada_en)}</>}
                </div>
              </div>
            </div>

            <div className={styles.tarjeta}>
              <dl className={styles.datos}>
                <div><dt>N° de autorización</dt><dd>{datos.numero ?? "—"}</dd></div>
                <div><dt>Trámite</dt><dd>{datos.tipo_tramite ?? "—"}</dd></div>
                <div><dt>Agencia naviera</dt><dd>{datos.agencia_nombre ?? "—"}</dd></div>
                <div><dt>Buque</dt><dd>{[datos.nombre_buque, datos.imo && `IMO ${datos.imo}`].filter(Boolean).join(" · ") || "—"}</dd></div>
                <div><dt>Bandera</dt><dd>{datos.bandera ?? "—"}</dd></div>
                <div><dt>Puesto de control</dt><dd>{datos.puesto_nombre ?? "—"}</dd></div>
                <div><dt>Fecha de la operación</dt><dd>{formatearFecha(datos.fecha_operacion)}</dd></div>
                <div><dt>Aprobada</dt><dd>{formatearFechaHora(datos.aprobada_en)}</dd></div>
                {datos.finalizada_en && (
                  <div>
                    <dt>Finalizada en</dt>
                    <dd>{datos.puesto_finalizacion_nombre ?? datos.puesto_nombre ?? "—"} · {formatearFechaHora(datos.finalizada_en)}</dd>
                  </div>
                )}
              </dl>

              <h2 className={styles.subtitulo}>Tripulantes autorizados ({datos.tripulantes.length})</h2>
              <ul className={styles.marinos}>
                {datos.tripulantes.map((m, i) => (
                  <li key={i}>
                    <span className={styles.marinoNombre}>{m.nombre_completo}</span>
                    <span className={styles.marinoMeta}>
                      {[m.nacionalidad, m.pasaporte && `Pasaporte ${m.pasaporte}`, m.rango && ETIQUETA_RANGO[m.rango]]
                        .filter(Boolean).join(" · ")}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <p className={styles.pie}>
              Consulta registrada. Esta página confirma los datos emitidos por el Servicio Nacional de Migración.
            </p>
          </>
        )}
      </div>
    </MarcoPagina>
  );
}
