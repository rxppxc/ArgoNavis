import { useState } from "react";
import type { EstadisticasSolicitudes, EstadoSolicitud } from "../../../api/solicitudes";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { IconoActividad, IconoExito, IconoProcesada, IconoReloj } from "../../../components/Iconos";
import {
  ESTADOS_BARRA, SERIE_DE_ESTADO, cifra, duracion, porcentaje, resumenEnPalabras, segun, textoPeriodo,
} from "./calculos";
import { Indicador } from "./Graficos";
import graficos from "./Graficos.module.css";
import styles from "./Estadisticas.module.css";

/** "77 % de las recibidas", o qué falta para poder calcularlo. */
function parteDe(valor: number, total: number, deLas: string): string {
  return total > 0 ? `${porcentaje(valor, total)} de las ${deLas}` : `Todavía no hay ${deLas}.`;
}

/** Lo primero que se lee: cuántas llegaron, qué pasó con ellas en palabras, en
 *  qué estado están hoy (una barra que suma el 100 %) y cuatro cifras sueltas. */
export default function ResumenPeriodo({ datos, rango }: { datos: EstadisticasSolicitudes; rango: RangoFechas }) {
  const [resaltado, setResaltado] = useState<EstadoSolicitud | null>(null);
  const estados = ESTADOS_BARRA.map((e) => ({ ...e, total: datos.por_estado[e.estado] ?? 0 }));
  const suma = estados.reduce((s, e) => s + e.total, 0);
  const apagado = (estado: EstadoSolicitud) => (resaltado && resaltado !== estado ? styles.apagado : "");

  return (
    <>
      <section className={styles.resumen} aria-labelledby="titulo-resumen">
        <h3 id="titulo-resumen" className="sr-only">Resumen del periodo</h3>
        <div className={styles.cifraPrincipal}>
          <span className={styles.heroe}>{cifra(datos.recibidas)}</span>
          <span className={styles.heroeEtiqueta}>{segun(datos.recibidas, "solicitud recibida", "solicitudes recibidas")}</span>
          <span className={styles.heroePeriodo}>{textoPeriodo(rango)}</span>
        </div>
        <p className={styles.frases}>
          {resumenEnPalabras(datos).map((t, i) => (typeof t === "string" ? t : <strong key={i}>{t.fuerte}</strong>))}
        </p>

        {suma > 0 && (
          <div className={styles.estados}>
            <h4 className={styles.estadosTitulo}>¿En qué van?</h4>
            {/* La barra es el dibujo; la leyenda de abajo tiene las mismas cifras en texto. */}
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
                  className={`${resaltado === e.estado ? styles.leyendaResaltada : ""} ${apagado(e.estado)}`}
                  onPointerEnter={() => setResaltado(e.estado)}
                  onPointerLeave={() => setResaltado(null)}
                >
                  <span className={`${graficos.muestra} ${graficos[SERIE_DE_ESTADO[e.estado]]} ${styles.leyendaMuestra}`} aria-hidden="true" />
                  <span>
                    <span className={styles.leyendaNombre}>{e.etiqueta}</span>
                    <span className={styles.leyendaCifra}>
                      <strong>{cifra(e.total)}</strong> · {porcentaje(e.total, suma)}
                    </span>
                    <span className={styles.leyendaExplicacion}>{e.explicacion}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <div className={styles.indicadores}>
        <Indicador
          icono={<IconoExito tamano={18} />} tono="aprobada" etiqueta="Aprobadas"
          valor={cifra(datos.aprobadas)}
          medidor={{ valor: datos.aprobadas, total: datos.recibidas, serie: "aprobada" }}
          nota={datos.recibidas > 0 ? `${porcentaje(datos.aprobadas, datos.recibidas)} de las recibidas, con las ya finalizadas.` : "Sin solicitudes en el periodo."}
        />
        <Indicador
          icono={<IconoProcesada tamano={18} />} tono="finalizada" etiqueta="Finalizadas en el puesto"
          valor={cifra(datos.finalizadas)}
          medidor={{ valor: datos.finalizadas, total: datos.aprobadas, serie: "finalizada" }}
          nota={parteDe(datos.finalizadas, datos.aprobadas, "aprobadas")}
        />
        <Indicador
          icono={<IconoReloj tamano={18} />} tono="fuera" etiqueta="Aprobadas fuera del horario"
          valor={cifra(datos.aprobadas_fuera_horario)}
          medidor={{ valor: datos.aprobadas_fuera_horario, total: datos.aprobadas, serie: "fuera" }}
          nota={parteDe(datos.aprobadas_fuera_horario, datos.aprobadas, "aprobadas")}
        />
        <Indicador
          icono={<IconoActividad tamano={18} />} etiqueta="Tiempo de respuesta de UCVMM"
          valor={duracion(datos.horas_promedio_resolucion)}
          nota={datos.horas_promedio_resolucion === null ? "Todavía no hay decisiones."
            : "Promedio entre el envío y la aprobación o denegación, con el tiempo en corrección."}
        />
      </div>
    </>
  );
}
