import { useLayoutEffect, useRef, useState } from "react";
import type { EstadisticasSolicitudes, FilaSerie } from "../../../api/solicitudes";
import type { RangoFechas } from "../../../components/FiltroFechas";
import { UNIDADES, cifra, escalaEje, mayuscula, partesPeriodo, proporcion, type Serie, type Unidad } from "./calculos";
import { FilaGlobo, Globo, TarjetaGrafico } from "./Graficos";
import { useGlobo } from "./useGlobo";
import styles from "./Graficos.module.css";
import seccion from "./Estadisticas.module.css";

type ClaveDibujada = "recibidas" | "aprobadas" | "finalizadas";

/** Las que se dibujan, en este orden dentro de cada grupo; la leyenda las muestra
 *  u oculta (siempre queda una). Hasta el 2026-11-10 también se dibujaba «Fuera del
 *  horario», que al encenderla apagaba las recibidas (su morado y ese azul no se
 *  distinguen con daltonismo): confundía. Ahora va en el globo y en la tabla, y
 *  tiene su cifra y su mapa de horas. Los tres colores, con ΔE 15 o más entre sí en
 *  los dos temas (validador de dataviz). */
const DIBUJADAS: { clave: ClaveDibujada; etiqueta: string; serie: Serie }[] = [
  { clave: "recibidas",   etiqueta: "Recibidas",   serie: "revision" },
  { clave: "aprobadas",   etiqueta: "Aprobadas",   serie: "aprobada" },
  { clave: "finalizadas", etiqueta: "Finalizadas", serie: "finalizada" },
];
/** Las que van solo en el globo y en la tabla. */
const OTRAS: { clave: "negadas" | "expiradas" | "fuera_horario"; etiqueta: string; serie: Serie }[] = [
  { clave: "negadas",       etiqueta: "Denegadas",         serie: "denegada" },
  { clave: "expiradas",     etiqueta: "Expiradas",         serie: "expirada" },
  { clave: "fuera_horario", etiqueta: "Fuera del horario", serie: "fuera" },
];
const TODAS = [...DIBUJADAS, ...OTRAS];
/** Lo que ocupa la cifra sobre la columna de las recibidas (.valorTope). */
const ALTO_CIFRA = 18;
/** Por día, el ancho mínimo de cada uno: en el celular el gráfico se desplaza de lado. */
const ANCHO_DIA = 20;
/** Cuántos periodos trae la serie como mucho (los últimos del periodo elegido). */
const TOPE: Record<Unidad, { cantidad: number; plural: string }> = {
  dia:  { cantidad: 31, plural: "días" },
  mes:  { cantidad: 12, plural: "meses" },
  anio: { cantidad: 10, plural: "años" },
};

/** Si la serie no llega al comienzo del periodo (con «Todo», o un periodo más largo que el tope). */
function recortada(filas: FilaSerie[], rango: RangoFechas, unidad: Unidad): boolean {
  if (filas.length < TOPE[unidad].cantidad) return false;
  if (!rango.desde) return true;
  const largo = { dia: 10, mes: 7, anio: 4 }[unidad];
  return filas[0].periodo > rango.desde.slice(0, largo);
}

interface Props {
  datos: EstadisticasSolicitudes;
  rango: RangoFechas;
  /** La lleva la página: cambia sola con el periodo y la usa la exportación. */
  unidad: Unidad;
  onUnidad: (u: Unidad) => void;
}

/** Columnas agrupadas por día, mes o año: recibidas, aprobadas y finalizadas.
 *  Pasar el mouse (o el foco) por un periodo muestra todas sus cifras. */
export default function GraficoTiempo({ datos, rango, unidad, onUnidad }: Props) {
  const [ocultas, setOcultas] = useState<ReadonlySet<ClaveDibujada>>(() => new Set());
  const { lienzo, activo, mostrar, ocultar, alSalir } = useGlobo<FilaSerie>();
  const filas = unidad === "dia" ? datos.por_dia : unidad === "mes" ? datos.por_mes : datos.por_anio;
  const cada = UNIDADES.find((u) => u.id === unidad)?.cada ?? "mes";
  const compacto = unidad === "dia";
  const visibles = DIBUJADAS.filter((s) => !ocultas.has(s.clave));
  const mayorDe = (f: FilaSerie) => Math.max(0, ...visibles.map((s) => f[s.clave]));
  const { tope, marcas } = escalaEje(Math.max(0, ...filas.map(mayorDe)));
  const sinDatos = filas.every((f) => TODAS.every((s) => f[s.clave] === 0));
  const columnasGrilla = { gridTemplateColumns: `repeat(${filas.length}, minmax(0, 1fr))` };
  // Si no entra (por día, en el celular), arranca mostrando los días más recientes.
  const desplazable = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const caja = desplazable.current;
    if (caja) caja.scrollLeft = caja.scrollWidth;
  }, [unidad, filas]);

  function cambiarUnidad(nueva: Unidad) {
    ocultar();
    onUnidad(nueva);
  }

  function alternar(clave: ClaveDibujada) {
    setOcultas((antes) => {
      const despues = new Set(antes);
      if (despues.has(clave)) despues.delete(clave);
      else if (DIBUJADAS.length - despues.size > 1) despues.add(clave);
      return despues;
    });
  }

  /** El globo, sobre la columna más alta del periodo y su cifra (que no la tape). */
  function mostrarPeriodo(f: FilaSerie, grupo: HTMLElement) {
    const r = grupo.getBoundingClientRect();
    mostrar(f, grupo, { arriba: r.top + r.height * (1 - proporcion(mayorDe(f), tope)) - ALTO_CIFRA });
  }

  const descripcionDe = (f: FilaSerie) =>
    `${mayuscula(partesPeriodo(f.periodo).largo)}: ${TODAS.map((s) => `${cifra(f[s.clave])} ${s.etiqueta.toLowerCase()}`).join(", ")}`;

  const tabla = (
    <table className={styles.tabla}>
      <thead>
        <tr><th>{mayuscula(cada)}</th>{TODAS.map((s) => <th key={s.clave}>{s.etiqueta}</th>)}</tr>
      </thead>
      <tbody>
        {filas.map((f) => (
          <tr key={f.periodo}>
            <td>{mayuscula(partesPeriodo(f.periodo).largo)}</td>
            {TODAS.map((s) => <td key={s.clave} className={styles.numero}>{cifra(f[s.clave])}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );

  const alcance = recortada(filas, rango, unidad) ? `Últimos ${TOPE[unidad].cantidad} ${TOPE[unidad].plural}. ` : "";

  return (
    <TarjetaGrafico
      ancha
      titulo={`Solicitudes por ${cada}`}
      descripcion={`${alcance}Cada cifra cuenta en la fecha en que ocurrió.`}
      tabla={tabla}
    >
      <div className={styles.controlesSerie}>
        <div className={seccion.chips} role="group" aria-label="Ver la serie por día, mes o año">
          <span className={styles.verPor}>Ver por</span>
          {UNIDADES.map((u) => (
            <button key={u.id} type="button" className={seccion.chip} aria-pressed={unidad === u.id}
              onClick={() => cambiarUnidad(u.id)}>
              {u.etiqueta}
            </button>
          ))}
        </div>
        {!sinDatos && (
          <div className={styles.leyendaBotones} role="group" aria-label="Series del gráfico">
            {DIBUJADAS.map((s) => (
              <button
                key={s.clave}
                type="button"
                className={`${styles.botonSerie} ${styles[s.serie]}`}
                aria-pressed={!ocultas.has(s.clave)}
                onClick={() => alternar(s.clave)}
              >
                <span className={styles.muestra} aria-hidden="true" />{s.etiqueta}
              </button>
            ))}
          </div>
        )}
      </div>

      {sinDatos ? <p className={styles.vacio}>Sin movimiento en este periodo.</p> : (
        <div className={styles.lienzo} ref={lienzo}>
          <div className={styles.desplazable} ref={desplazable}>
            <div className={`${styles.columnas} ${compacto ? styles.compacto : ""}`}
              style={compacto ? { minWidth: `${42 + filas.length * ANCHO_DIA}px` } : undefined}>
              <div className={styles.ejeY} aria-hidden="true">
                {marcas.map((v) => <span key={v} style={{ bottom: `${proporcion(v, tope) * 100}%` }}>{cifra(v)}</span>)}
              </div>
              <div className={styles.areaColumnas} style={columnasGrilla}>
                {marcas.map((v) => (
                  <span key={v} className={v === 0 ? styles.base : styles.rejilla}
                    style={{ bottom: `${proporcion(v, tope) * 100}%` }} aria-hidden="true" />
                ))}
                {filas.map((f) => (
                  <div
                    key={f.periodo}
                    className={`${styles.grupo} ${activo?.dato.periodo === f.periodo ? styles.grupoActivo : ""}`}
                    tabIndex={0}
                    aria-label={descripcionDe(f)}
                    onPointerEnter={(e) => mostrarPeriodo(f, e.currentTarget)}
                    onPointerLeave={alSalir}
                    onFocus={(e) => mostrarPeriodo(f, e.currentTarget)}
                    onBlur={ocultar}
                  >
                    {visibles.map((s) => (
                      <span key={s.clave} className={`${styles.columna} ${styles[s.serie]}`}
                        style={{ height: `${proporcion(f[s.clave], tope) * 100}%` }}>
                        {/* Solo la cifra de las recibidas, y no por día: una en cada columna sería ruido. */}
                        {!compacto && s.clave === "recibidas" && f.recibidas > 0 && (
                          <span className={styles.valorTope}>{cifra(f.recibidas)}</span>
                        )}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
              <div className={styles.ejeX} style={columnasGrilla} aria-hidden="true">
                {filas.map((f, i) => {
                  const p = partesPeriodo(f.periodo);
                  // Por día, el mes va solo en el primero y donde empieza uno nuevo.
                  const abajo = compacto && i > 0 && p.arriba !== "1" ? "" : p.abajo;
                  return <span key={f.periodo}><span className={styles.ejeArriba}>{p.arriba}</span><span className={styles.ejeAbajo}>{abajo}</span></span>;
                })}
              </div>
            </div>
          </div>
          {activo && (
            <Globo x={activo.x} y={activo.y}>
              <p className={styles.globoTitulo}>{partesPeriodo(activo.dato.periodo).largo}</p>
              {TODAS.map((s) => <FilaGlobo key={s.clave} serie={s.serie} valor={cifra(activo.dato[s.clave])} etiqueta={s.etiqueta} />)}
            </Globo>
          )}
        </div>
      )}
    </TarjetaGrafico>
  );
}
