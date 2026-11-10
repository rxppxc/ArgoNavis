import { useState } from "react";
import type { EstadisticasSolicitudes, EstadoSolicitud } from "../../../api/solicitudes";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { IconoActividad, IconoExito, IconoProcesada, IconoReloj, IconoXCirculo } from "../../../components/Iconos";
import { ESTADOS_BARRA, SERIE_DE_ESTADO, cifra, duracion, porcentaje, segun, textoPeriodo } from "./calculos";
import { Indicador } from "./Graficos";
import graficos from "./Graficos.module.css";
import styles from "./Estadisticas.module.css";

/** Lo primero que se lee: cuántas llegaron y, al lado, en qué estado están hoy
 *  (una barra que suma el 100 %, con su leyenda); debajo, cinco cifras sueltas.
 *  Hasta el 2026-11-10 llevaba además un párrafo con lo mismo en frases y una
 *  explicación por estado: era mucho texto (ahora la explicación sale al pasar
 *  el mouse por la leyenda). */
export default function ResumenPeriodo({ datos, rango }: { datos: EstadisticasSolicitudes; rango: RangoFechas }) {
  const [resaltado, setResaltado] = useState<EstadoSolicitud | null>(null);
  const estados = ESTADOS_BARRA.map((e) => ({ ...e, total: datos.por_estado[e.estado] ?? 0 }));
  const suma = estados.reduce((s, e) => s + e.total, 0);
  const apagado = (estado: EstadoSolicitud) => (resaltado && resaltado !== estado ? styles.apagado : "");
  /** El porcentaje junto a la cifra, si hay de dónde sacarlo. */
  const parte = (valor: number, total: number) => (total > 0 ? porcentaje(valor, total) : undefined);

  return (
    <>
      <section className={styles.resumen} aria-labelledby="titulo-resumen">
        <h3 id="titulo-resumen" className="sr-only">Resumen del periodo</h3>
        <div className={styles.cifraPrincipal}>
          <span className={styles.heroe}>{cifra(datos.recibidas)}</span>
          <span className={styles.heroeEtiqueta}>{segun(datos.recibidas, "solicitud recibida", "solicitudes recibidas")}</span>
          <span className={styles.heroePeriodo}>{textoPeriodo(rango)}</span>
        </div>

        <div className={styles.estados}>
          <h4 className={styles.estadosTitulo}>Estado actual</h4>
          {suma === 0 ? <p className={styles.sinEstados}>No llegaron solicitudes en este periodo.</p> : (
            <>
              {/* La barra es el dibujo; la leyenda tiene las mismas cifras en texto. */}
              <div className={styles.barraEstados} aria-hidden="true">
                {estados.filter((e) => e.total > 0).map((e) => (
                  <span
                    key={e.estado}
                    className={`${styles.segmentoEstado} ${graficos[SERIE_DE_ESTADO[e.estado]]} ${apagado(e.estado)}`}
                    style={{ flexGrow: e.total }}
                    onPointerEnter={() => setResaltado(e.estado)}
                    onPointerLeave={() => setResaltado(null)}
                  />
                ))}
              </div>
              <ul className={styles.leyendaEstados}>
                {estados.map((e) => (
                  <li
                    key={e.estado}
                    title={e.explicacion}
                    className={`${resaltado === e.estado ? styles.leyendaResaltada : ""} ${apagado(e.estado)}`}
                    onPointerEnter={() => setResaltado(e.estado)}
                    onPointerLeave={() => setResaltado(null)}
                  >
                    <span className={`${graficos.muestra} ${graficos[SERIE_DE_ESTADO[e.estado]]}`} aria-hidden="true" />
                    <span className={styles.leyendaNombre}>{e.etiqueta}</span>
                    <span className={styles.leyendaCifra}><strong>{cifra(e.total)}</strong> · {porcentaje(e.total, suma)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </section>

      <div className={styles.indicadores}>
        <Indicador
          icono={<IconoExito tamano={18} />} tono="aprobada" etiqueta="Aprobadas"
          valor={cifra(datos.aprobadas)} porcentaje={parte(datos.aprobadas, datos.recibidas)}
          medidor={{ valor: datos.aprobadas, total: datos.recibidas, serie: "aprobada" }}
          nota={datos.recibidas > 0 ? "de las recibidas" : undefined}
        />
        <Indicador
          icono={<IconoXCirculo tamano={18} />} tono="denegada" etiqueta="Denegadas"
          valor={cifra(datos.negadas)} porcentaje={parte(datos.negadas, datos.recibidas)}
          medidor={{ valor: datos.negadas, total: datos.recibidas, serie: "denegada" }}
          nota={datos.recibidas > 0 ? "de las recibidas" : undefined}
        />
        <Indicador
          icono={<IconoProcesada tamano={18} />} tono="finalizada" etiqueta="Finalizadas en el puesto"
          valor={cifra(datos.finalizadas)} porcentaje={parte(datos.finalizadas, datos.aprobadas)}
          medidor={{ valor: datos.finalizadas, total: datos.aprobadas, serie: "finalizada" }}
          nota={datos.aprobadas > 0 ? "de las aprobadas" : undefined}
        />
        <Indicador
          icono={<IconoReloj tamano={18} />} tono="fuera" etiqueta="Fuera del horario"
          valor={cifra(datos.aprobadas_fuera_horario)} porcentaje={parte(datos.aprobadas_fuera_horario, datos.aprobadas)}
          medidor={{ valor: datos.aprobadas_fuera_horario, total: datos.aprobadas, serie: "fuera" }}
          nota={datos.aprobadas > 0 ? "de las aprobadas" : undefined}
        />
        <Indicador
          icono={<IconoActividad tamano={18} />} etiqueta="Respuesta de UCVMM"
          valor={duracion(datos.horas_promedio_resolucion)}
          nota={datos.horas_promedio_resolucion === null ? "Todavía sin decisiones" : "Promedio, del envío a la decisión"}
        />
      </div>
    </>
  );
}
