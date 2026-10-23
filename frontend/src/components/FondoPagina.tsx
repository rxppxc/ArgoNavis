import { useState } from "react";
import { IconoPausa, IconoReproducir } from "./Iconos";
import styles from "./FondoPagina.module.css";

/** Fondo de todas las páginas, entre la cabecera y el pie: la «carta celeste»
 *  (elegida por el usuario el 2026-10-22). Un astrolabio que ocupa todo el
 *  fondo —anillos, meridianos y graduación— con la constelación Argo encima y
 *  las coordenadas del SNM. Es decorativo: va detrás del contenido y no recibe
 *  clics. Los colores salen del tema (claro y oscuro). */

/** Constelaciones que cruzan el fondo. */
const RUTAS = [
  "120,760 260,690 420,720 560,610 720,650 860,540",
  "560,610 610,760 760,800 720,650",
  "980,210 1110,150 1260,190 1380,90 1520,130",
  "1110,150 1150,300 1300,320 1260,190",
  "60,140 210,90 330,170 470,120",
];
/** Una estrella por vértice; las que comparten dos rutas, una sola vez. */
const ESTRELLAS = [...new Set(RUTAS.flatMap((r) => r.split(" ")))].map((p) => p.split(",").map(Number));

/** Graduación del anillo exterior: una marca cada 2°, más larga cada 10° y cada 90°. */
const GRADUACION = Array.from({ length: 180 }, (_, i) => {
  const grados = i * 2;
  const a = (grados * Math.PI) / 180;
  const largo = grados % 90 === 0 ? 48 : grados % 10 === 0 ? 27 : 13;
  return {
    clave: grados,
    x1: 800 + 600 * Math.sin(a), y1: 450 - 600 * Math.cos(a),
    x2: 800 + (600 - largo) * Math.sin(a), y2: 450 - (600 - largo) * Math.cos(a),
  };
});

const MERIDIANOS = Array.from({ length: 12 }, (_, i) => {
  const a = (i * 30 * Math.PI) / 180;
  return { clave: i, x: 800 + 900 * Math.sin(a), y: 450 - 900 * Math.cos(a) };
});

/** La pausa se recuerda en el navegador (como el tema). */
const CLAVE_PAUSA = "fondo-pausado";

function leerPausa(): boolean {
  try {
    return localStorage.getItem(CLAVE_PAUSA) === "1";
  } catch {
    return false; // Almacenamiento bloqueado: arranca en movimiento.
  }
}

interface Props {
  /** El login ya las muestra bajo el logo: ahí no se repiten. */
  coordenadas?: boolean;
  /** Solo en el login, «rutas vivas» (elegida por el usuario el 2026-10-23):
   *  las rutas se trazan al entrar, las recorren luces doradas y las estrellas
   *  laten. En las pantallas de trabajo queda quieto, para no distraer.
   *  Sin haz ni giro del astrolabio: mueven capas del tamaño de la pantalla y,
   *  en equipos sin tarjeta gráfica, el login caía a 22 cuadros por segundo
   *  (con las rutas vivas, 60; ~13 % de un núcleo mientras está abierto).
   *  Se mueve aunque el equipo pida «reducir movimiento» (decisión del usuario
   *  del 2026-10-23: muchos equipos del SNM traen las animaciones de Windows
   *  apagadas por rendimiento). A cambio lleva un botón para pausarlo, que pide
   *  la WCAG 2.2.2 para lo que se mueve solo más de 5 segundos. */
  animado?: boolean;
}

export function FondoPagina({ coordenadas = true, animado = false }: Props) {
  const [pausado, setPausado] = useState(leerPausa);

  function alternarPausa() {
    const nuevo = !pausado;
    setPausado(nuevo);
    try {
      if (nuevo) localStorage.setItem(CLAVE_PAUSA, "1");
      else localStorage.removeItem(CLAVE_PAUSA);
    } catch {
      // Sin almacenamiento: la pausa dura mientras la página esté abierta.
    }
  }

  return (
    <>
      <div className={styles.franja} />
      {/* data-movimiento: globals.css no lo frena con «reducir movimiento». */}
      <div className={`${styles.capa} ${pausado ? styles.pausado : ""}`} data-movimiento={animado ? "" : undefined}>
        <svg className={`${styles.carta} ${animado ? styles.animado : ""}`} viewBox="0 0 1600 900"
          preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <g className={styles.astrolabio} fill="none" stroke="currentColor">
            {[600, 470, 340, 210].map((r) => <circle key={r} cx="800" cy="450" r={r} strokeWidth={r === 600 ? 2 : 1} />)}
            {MERIDIANOS.map((m) => <line key={m.clave} x1="800" y1="450" x2={m.x} y2={m.y} strokeWidth="1" strokeDasharray="2 8" />)}
            {GRADUACION.map((m) => <line key={m.clave} x1={m.x1} y1={m.y1} x2={m.x2} y2={m.y2} strokeWidth="1.2" />)}
          </g>
          <g className={styles.constelacion} fill="none" stroke="currentColor" strokeWidth="1.4">
            {RUTAS.map((r) => <polyline key={r} points={r} pathLength={1} />)}
          </g>
          {/* Luces que recorren cada ruta, como barcos en su derrota. */}
          {animado && (
            <g className={styles.estelas} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
              {RUTAS.map((r) => <polyline key={r} points={r} pathLength={1} />)}
            </g>
          )}
          {ESTRELLAS.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="3" className={styles.estrella} />)}
        </svg>
      </div>
      {coordenadas && <div className={styles.coordenadas} aria-hidden="true">09° 01′ N<br />079° 32′ O</div>}
      {animado && (
        <button type="button" className={styles.pausa} onClick={alternarPausa}>
          {pausado ? <IconoReproducir /> : <IconoPausa />}
          {pausado ? "Reanudar animación" : "Pausar animación"}
        </button>
      )}
    </>
  );
}
