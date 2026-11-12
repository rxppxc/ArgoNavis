import { Fragment, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import type { EstadisticasSolicitudes } from "../../../api/solicitudes";
import { IconoChevronDerecha } from "../../../components/Iconos";
import { formatearFechaHora } from "../../solicitudes/presentacion";
import { estadoParaVolver } from "../../../utils/volver";
import {
  DIAS_SEMANA, HORA_FIN_LABORAL, HORA_INICIO_LABORAL, NIVELES_CALOR, cifra, dosDigitos, horarioDeCasilla,
  nivelCalor, porcentaje, segun, textoHora,
} from "./calculos";
import { Globo, Medidor, TarjetaGrafico } from "./Graficos";
import { useGlobo } from "./useGlobo";
import styles from "./Graficos.module.css";

const HORAS = Array.from({ length: 24 }, (_, h) => h);
/** En el celular solo se rotulan estas horas: el día, el horario laboral y el mediodía. */
const HORAS_CLAVE = new Set([0, HORA_INICIO_LABORAL, 12, HORA_FIN_LABORAL, 23]);

interface Casilla { dia: number; hora: number }

/** Cómo cae cada casilla, en la tabla y en el globo. La de las 15 (de lunes a
 *  viernes) es fuera del horario salvo su primer minuto: las 15:00 en punto son laborales. */
const HORARIO_TABLA = { laboral: "Laboral", fuera: "Fuera del horario", borde: "Fuera desde las 15:01" };
const HORARIO_GLOBO = {
  laboral: "En horario laboral",
  fuera: "Fuera del horario laboral",
  borde: "Fuera del horario desde las 15:01 (las 15:00 en punto son laborales)",
};

/** Hora de aprobación de UCVMM. Una semana en casillas de una hora, más intensa
 *  (en oscuro, más brillante) cuantas más se aprobaron, con el horario laboral
 *  recuadrado: lo de afuera es fuera del horario (las 15:00 en punto cuentan
 *  dentro: lo dice el globo de esa casilla). Debajo, la lista de las aprobadas
 *  fuera del horario, con enlace al expediente. Hasta el 2026-11-06 contaba la
 *  finalización del puesto de control. */
export default function MapaHoras({ datos }: { datos: EstadisticasSolicitudes }) {
  const totales = new Map(datos.aprobadas_por_hora.map((c) => [`${c.dia}-${c.hora}`, c.total]));
  const total = (c: Casilla) => totales.get(`${c.dia}-${c.hora}`) ?? 0;
  const maximo = Math.max(0, ...datos.aprobadas_por_hora.map((c) => c.total));
  const { lienzo, activo, mostrar, ocultar, alSalir } = useGlobo<Casilla>();
  // La casilla que recorre el teclado (con las flechas, dentro del mapa).
  const [conTeclado, setConTeclado] = useState<Casilla | null>(null);
  const fuera = datos.aprobadas_fuera_horario;
  const lista = datos.operaciones_fuera_horario;

  const elementoDe = (c: Casilla) => lienzo.current?.querySelector(`[data-casilla="${c.dia}-${c.hora}"]`) ?? null;

  function mostrarCasilla(c: Casilla) {
    const elemento = elementoDe(c);
    if (elemento) mostrar(c, elemento);
  }

  function alEnfocar() {
    // Empieza por la casilla con más aprobaciones (o el lunes a las 07:00).
    const inicio = datos.aprobadas_por_hora.reduce<Casilla | null>(
      (mayor, c) => (!mayor || c.total > total(mayor) ? { dia: c.dia, hora: c.hora } : mayor), null,
    ) ?? { dia: 1, hora: HORA_INICIO_LABORAL };
    const actual = conTeclado ?? inicio;
    setConTeclado(actual);
    mostrarCasilla(actual);
  }

  function alTeclear(e: KeyboardEvent) {
    const movimientos: Record<string, [number, number]> = {
      ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0],
    };
    const paso = movimientos[e.key];
    if (!paso) return;
    e.preventDefault();
    if (!conTeclado) { alEnfocar(); return; }   // enfocado con el mouse: la primera flecha arranca
    const nueva = {
      dia: Math.min(7, Math.max(1, conTeclado.dia + paso[0])),
      hora: Math.min(23, Math.max(0, conTeclado.hora + paso[1])),
    };
    setConTeclado(nueva);
    mostrarCasilla(nueva);
  }

  const descripcionCasilla = (c: Casilla) => {
    const dia = DIAS_SEMANA[c.dia - 1].largo, n = total(c);
    return `${dia}, ${textoHora(c.hora)}: ${cifra(n)} ${segun(n, "aprobada", "aprobadas")}, `
      + HORARIO_GLOBO[horarioDeCasilla(c.dia, c.hora)].toLowerCase();
  };

  const tabla = (
    <table className={styles.tabla}>
      <thead>
        <tr><th>Día</th><th className={styles.izquierda}>Hora</th><th>Aprobadas</th><th className={styles.izquierda}>Horario</th></tr>
      </thead>
      <tbody>
        {[...datos.aprobadas_por_hora].sort((a, b) => a.dia - b.dia || a.hora - b.hora).map((c) => (
          <tr key={`${c.dia}-${c.hora}`}>
            <td>{DIAS_SEMANA[c.dia - 1].largo}</td>
            <td>{textoHora(c.hora)}</td>
            <td className={styles.numero}>{cifra(c.total)}</td>
            <td>{HORARIO_TABLA[horarioDeCasilla(c.dia, c.hora)]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <TarjetaGrafico
      ancha
      titulo="Hora de aprobación de UCVMM"
      // Una línea (antes eran cinco): el detalle de cada casilla, en su globo y en «Ver tabla».
      descripcion={`El recuadro es el horario laboral: ${datos.horario_laboral}.`}
      tabla={datos.aprobadas_por_hora.length > 0 ? tabla : undefined}
    >
      <div className={styles.fueraResumen}>
        <p>
          {datos.aprobadas === 0 ? "Ninguna autorización aprobada en el periodo." : (
            <><strong>{cifra(fuera)}</strong> fuera del horario · {porcentaje(fuera, datos.aprobadas)} de
              las {cifra(datos.aprobadas)} aprobadas</>
          )}
        </p>
        <Medidor valor={fuera} total={datos.aprobadas} serie="fuera" />
      </div>

      {datos.aprobadas > 0 && (
        <div className={styles.lienzo} ref={lienzo}>
          <div
            className={styles.mapa}
            tabIndex={0}
            role="group"
            aria-label="Mapa de horas: recórrelo con las flechas. Las mismas cifras están en «Ver tabla»."
            // Solo con el teclado: un toque también enfoca el mapa, y ahí manda la casilla tocada.
            onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) alEnfocar(); }}
            onBlur={() => { setConTeclado(null); ocultar(); }}
            onKeyDown={alTeclear}
          >
            <span aria-hidden="true" />
            {HORAS.map((h) => (
              <span key={h} className={`${styles.horaEje} ${HORAS_CLAVE.has(h) ? styles.horaClave : ""}`} aria-hidden="true">
                {dosDigitos(h)}
              </span>
            ))}
            {DIAS_SEMANA.map((d) => (
              <Fragment key={d.dia}>
                <span className={styles.diaEje} aria-hidden="true">{d.corto}</span>
                {HORAS.map((h) => {
                  const casilla = { dia: d.dia, hora: h };
                  const elegida = conTeclado?.dia === d.dia && conTeclado.hora === h;
                  return (
                    <span
                      key={h}
                      data-casilla={`${d.dia}-${h}`}
                      className={`${styles.celda} ${styles[`nivel${nivelCalor(total(casilla), maximo)}`] ?? ""} ${elegida ? styles.celdaActiva : ""}`}
                      onPointerEnter={(e) => mostrar(casilla, e.currentTarget)}
                      onPointerLeave={alSalir}
                    />
                  );
                })}
              </Fragment>
            ))}
            <span
              className={styles.recuadro}
              style={{ gridColumn: `${HORA_INICIO_LABORAL + 2} / ${HORA_FIN_LABORAL + 2}` }}
              aria-hidden="true"
            />
          </div>
          <p className="sr-only" aria-live="polite">{conTeclado ? descripcionCasilla(conTeclado) : ""}</p>
          {activo && (
            <Globo x={activo.x} y={activo.y}>
              <p className={styles.globoTitulo}>{DIAS_SEMANA[activo.dato.dia - 1].largo}, {textoHora(activo.dato.hora)}</p>
              <p><strong>{cifra(total(activo.dato))}</strong> {segun(total(activo.dato), "aprobada", "aprobadas")}</p>
              <p className={styles.globoNota}>{HORARIO_GLOBO[horarioDeCasilla(activo.dato.dia, activo.dato.hora)]}</p>
            </Globo>
          )}
          <div className={styles.escala} aria-hidden="true">
            <span className={styles.escalaPasos}>
              Menos
              {Array.from({ length: NIVELES_CALOR + 1 }, (_, n) => <span key={n} className={`${styles.celda} ${styles[`nivel${n}`] ?? ""}`} />)}
              Más
            </span>
            <span className={styles.escalaRecuadro}>Horario laboral</span>
          </div>
        </div>
      )}

      {lista.length > 0 && (
        <details className={styles.desplegable}>
          <summary>
            <IconoChevronDerecha tamano={14} className={styles.chevron} />
            Ver {segun(fuera, "la aprobada", `las ${cifra(fuera)} aprobadas`)} fuera del horario
          </summary>
          <div className={styles.envoltorioTabla}>
            <table className={styles.tabla}>
              <thead>
                <tr>
                  <th>Solicitud</th><th className={styles.izquierda}>Trámite</th>
                  <th className={styles.izquierda}>Puesto</th><th>Aprobada</th>
                  <th className={styles.izquierda}>Aprobada por</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((o) => (
                  <tr key={o.id}>
                    <td><Link to={`/solicitudes/${o.id}`} state={estadoParaVolver("/admin/stats")} className={styles.enlace}>{o.numero ?? `#${o.id}`}</Link></td>
                    <td>{o.tipo_tramite}</td>
                    <td>{o.puesto}</td>
                    <td className={styles.numero}>
                      {new Date(o.aprobada_en).toLocaleDateString("es-PA", { weekday: "short" })}{" "}
                      {formatearFechaHora(o.aprobada_en)}
                    </td>
                    <td>{o.aprobada_por ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {fuera > lista.length && <p className={styles.notaLista}>Se muestran las {cifra(lista.length)} más recientes.</p>}
        </details>
      )}
    </TarjetaGrafico>
  );
}
