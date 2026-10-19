import { useState, useEffect } from "react";
import { apiTramites, ETIQUETA_ALCANCE, ETIQUETA_CONDICION, type TipoTramite } from "../../api/tramites";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { useNotificacion } from "../../components/Notificaciones";
import { ETIQUETA_RANGO } from "../solicitudes/presentacion";
import {
  IconoArchivo, IconoUsuario, IconoChevronDerecha, IconoCandado,
} from "../../components/Iconos";
import styles from "./PaginaTramites.module.css";

export default function PaginaTramites() {
  const [tipos, setTipos] = useState<TipoTramite[]>([]);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState<number | null>(null);
  const { mostrar } = useNotificacion();

  useEffect(() => {
    (async () => {
      try {
        setTipos(await apiTramites.listar());
      } catch {
        mostrar("No se pudo cargar el catálogo de trámites.", "error");
      } finally {
        setCargando(false);
      }
    })();
  }, [mostrar]);

  return (
    <MarcoPagina volverA="/dashboard">
      <>
        <EncabezadoPagina
          titulo="Catálogo de trámites"
          descripcion={
            "Qué datos y documentos exige cada trámite del Formulario 3 (Solicitud de Autorización, la llena la "
            + "agencia naviera). Es lo que el sistema pide al crear una solicitud; el catálogo se ajusta con una "
            + "migración de la base de datos."
          }
        />

        {cargando ? (
          <div className={styles.empty}>Cargando catálogo…</div>
        ) : tipos.length === 0 ? (
          <div className={styles.empty}>No hay trámites configurados.</div>
        ) : (
          <div className={styles.lista}>
            {tipos.map((t) => {
              const expandido = abierto === t.id;
              const campos = [
                t.requiere_buque && "Buque, IMO y bandera",
                t.requiere_puerto && "Puerto",
                t.requiere_puerto_desembarque && "Puerto de desembarque",
                t.requiere_clinica && "Clínica u hospital",
                t.requiere_motivo && "Motivo",
              ].filter(Boolean) as string[];

              return (
                <div key={t.id} className={`${styles.card} ${expandido ? styles.cardOpen : ""}`}>
                  <button
                    className={styles.cardHeader}
                    onClick={() => setAbierto(expandido ? null : t.id)}
                  >
                    <span className={`${styles.chevron} ${expandido ? styles.chevronOpen : ""}`}>
                      <IconoChevronDerecha />
                    </span>
                    <div className={styles.cardInfo}>
                      <div className={styles.cardNombre}>{t.nombre}</div>
                      {t.descripcion && <div className={styles.cardDescripcion}>{t.descripcion}</div>}
                      <div className={styles.cardCodigo}>{t.codigo}</div>
                    </div>
                    <span className={styles.docCount}>
                      {t.documentos.length === 0
                        ? "Sin checklist"
                        : `${t.documentos.length} documento${t.documentos.length === 1 ? "" : "s"}`}
                    </span>
                  </button>

                  {expandido && (
                    <div className={styles.cardBody}>
                      {campos.length > 0 && (
                        <div className={styles.seccion}>
                          <div className={styles.seccionTitulo}>Campos que pide el formulario</div>
                          <div className={styles.chips}>
                            <span className={styles.chipCampo}>Fecha de la operación</span>
                            {campos.map((c) => (
                              <span key={c} className={styles.chipCampo}>{c}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {t.nota && (
                        <div className={styles.nota}>
                          <IconoCandado tamano={13} />
                          <span>{t.nota}</span>
                        </div>
                      )}

                      {t.rangos_permitidos && (
                        <div className={styles.nota}>
                          <IconoCandado tamano={13} />
                          <span>Solo admite tripulantes con rango {t.rangos_permitidos.map((r) => ETIQUETA_RANGO[r]).join(", ")}.</span>
                        </div>
                      )}

                      {t.aviso_custodia && (
                        <div className={styles.nota}>
                          <IconoCandado tamano={13} />
                          <span>
                            Al aprobar, se avisa a la agencia que debe realizar el trámite de solicitud de custodia de
                            los tripulantes de nacionalidad restringida.
                          </span>
                        </div>
                      )}

                      {t.valida_vigencia && (
                        <div className={styles.nota}>
                          <IconoCandado tamano={13} />
                          <span>Exige pasaporte y seamanbook vigentes a la fecha de la operación.</span>
                        </div>
                      )}

                      <div className={styles.seccion}>
                        <div className={styles.seccionTitulo}>Documentos a adjuntar</div>
                        {t.documentos.length === 0 ? (
                          <div className={styles.sinDocs}>
                            Este trámite no exige documentos adjuntos.
                          </div>
                        ) : (
                          <table className={styles.tabla}>
                            <thead>
                              <tr>
                                <th>Documento</th>
                                <th>Se adjunta</th>
                                <th>Cuándo se exige</th>
                              </tr>
                            </thead>
                            <tbody>
                              {t.documentos.map((d) => (
                                <tr key={d.id}>
                                  <td>
                                    <div className={styles.docNombre}>{d.nombre}</div>
                                    {d.descripcion && (
                                      <div className={styles.docDesc}>{d.descripcion}</div>
                                    )}
                                    {d.requiere_libreta && (
                                      <div className={styles.docDesc}>Solo a tripulantes que portan seamanbook (rango Marino).</div>
                                    )}
                                  </td>
                                  <td>
                                    <span
                                      className={
                                        d.alcance === "marino" ? styles.badgeMarino : styles.badgeSolicitud
                                      }
                                    >
                                      {d.alcance === "marino" ? <IconoUsuario tamano={12} /> : <IconoArchivo tamano={12} />}
                                      {ETIQUETA_ALCANCE[d.alcance]}
                                    </span>
                                  </td>
                                  <td>
                                    <span
                                      className={
                                        d.condicion === "siempre" ? styles.condSiempre : styles.condCondicional
                                      }
                                    >
                                      {ETIQUETA_CONDICION[d.condicion]}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </>
    </MarcoPagina>
  );
}
