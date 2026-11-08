import { useEffect, useLayoutEffect, useRef } from "react";
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
const PUNTOS = RUTAS.map((r) => r.split(" ").map((p) => p.split(",").map(Number)));
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

// ─── Luces de las rutas (solo el login) ─────────────────────────────────────

/** Segundos que tarda cada luz en recorrer su ruta, y desfase de cada ruta. */
const DURACIONES = [4, 3, 4.6, 3.4, 3.8];
const RETRASOS = [0, -2, -3, -1, -2.5];
const OPACIDAD_LUZ = 0.85;
/** Cada luz mide el 5 % de su ruta y 3 unidades de ancho (el trazo de antes). */
const LARGO_LUZ = 0.05;
const ANCHO_LUZ = 3;
/** La luz aparece y se apaga en el 4 % de cada punta de la ruta. */
const PUNTA = 0.04;
/** Unidades antes y después de cada vértice en las que la luz gira hacia el tramo siguiente. */
const GIRO = 10;

interface Luz {
  largo: number;
  cuadros: Keyframe[];
  duracion: number;
  retraso: number;
}

interface Recorrido {
  largo: number;
  cuadros: Keyframe[];
}

/** Cuadros clave para recorrer una ruta: posición y ángulo en cada vértice, en
 *  el sistema de la carta (viewBox 1600×900). Entre cuadros el navegador
 *  interpola en línea recta, así que la luz sigue la ruta exacta. */
function recorrido(puntos: number[][]): Recorrido {
  const tramos = puntos.slice(1).map(([x1, y1], i) => {
    const [x0, y0] = puntos[i];
    return { x0, y0, dx: x1 - x0, dy: y1 - y0, largo: Math.hypot(x1 - x0, y1 - y0), angulo: (Math.atan2(y1 - y0, x1 - x0) * 180) / Math.PI };
  });
  // Ángulos sin saltos de 360°: de 170° a -170° gira 20°, no 340°.
  for (let i = 1; i < tramos.length; i++) {
    while (tramos[i].angulo - tramos[i - 1].angulo > 180) tramos[i].angulo -= 360;
    while (tramos[i].angulo - tramos[i - 1].angulo < -180) tramos[i].angulo += 360;
  }
  const inicios = tramos.map((_, i) => tramos.slice(0, i).reduce((s, t) => s + t.largo, 0));
  const total = inicios[inicios.length - 1] + tramos[tramos.length - 1].largo;
  const tramoEn = (d: number) => inicios.reduce((k, inicio, j) => (inicio <= d ? j : k), 0);
  const largo = total * LARGO_LUZ;

  const marcas: { d: number; i: number }[] = [
    { d: 0, i: 0 },
    { d: PUNTA * total, i: tramoEn(PUNTA * total) },
    { d: (1 - PUNTA) * total, i: tramoEn((1 - PUNTA) * total) },
    { d: total, i: tramos.length - 1 },
  ];
  for (let i = 1; i < tramos.length; i++) {
    const giro = Math.min(GIRO, tramos[i - 1].largo / 2, tramos[i].largo / 2);
    marcas.push({ d: inicios[i] - giro, i: i - 1 }, { d: inicios[i] + giro, i });
  }
  marcas.sort((a, b) => a.d - b.d);

  const cuadros = marcas.map(({ d, i }) => {
    const t = tramos[i];
    const avance = (d - inicios[i]) / t.largo;
    const punta = Math.min(d, total - d) / (PUNTA * total);
    return {
      offset: d / total,
      opacity: OPACIDAD_LUZ * Math.min(1, punta),
      // La luz se centra en su punto, gira y va a su lugar. En píxeles y no en
      // porcentajes, para que la animación la mueva la tarjeta gráfica.
      transform: `translate(${t.x0 + t.dx * avance}px, ${t.y0 + t.dy * avance}px) rotate(${t.angulo}deg) `
        + `translate(${-largo / 2}px, ${-ANCHO_LUZ / 2}px)`,
    };
  });
  return { largo, cuadros };
}

/** Dos luces por ruta, a media vuelta una de la otra. */
const LUCES: Luz[] = PUNTOS.flatMap((puntos, r) => {
  const { largo, cuadros } = recorrido(puntos);
  const duracion = DURACIONES[r] * 1000;
  return [0, 0.5].map((fase) => ({ largo, cuadros, duracion, retraso: RETRASOS[r] * 1000 - fase * duracion }));
});

/** Estrellas que laten y luces que recorren las rutas, en HTML y no en el SVG:
 *  cada una es una capa chica que la tarjeta gráfica mueve (transform y
 *  opacity) sin volver a dibujar la carta. Dentro del SVG, el navegador
 *  redibujaba toda la pantalla en cada cuadro: el login usaba más de un núcleo
 *  entero (medido el 2026-10-26). */
function RutasVivas() {
  const marco = useRef<HTMLDivElement>(null);
  const lienzo = useRef<HTMLDivElement>(null);

  // El mismo encuadre que el SVG (viewBox 1600×900, «xMidYMid slice»).
  useLayoutEffect(() => {
    const m = marco.current;
    const l = lienzo.current;
    if (!m || !l) return;
    const encuadrar = () => {
      const { width, height } = m.getBoundingClientRect();
      const escala = Math.max(width / 1600, height / 900);
      l.style.transform = `translate(${(width - 1600 * escala) / 2}px, ${(height - 900 * escala) / 2}px) scale(${escala})`;
    };
    encuadrar();
    if (typeof ResizeObserver === "undefined") return;
    const observador = new ResizeObserver(encuadrar);
    observador.observe(m);
    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    const elementos = Array.from(lienzo.current?.querySelectorAll<HTMLElement>(`.${styles.luz}`) ?? []);
    const animaciones = elementos.flatMap((el, i) =>
      typeof el.animate === "function"
        ? [el.animate(LUCES[i].cuadros, { duration: LUCES[i].duracion, delay: LUCES[i].retraso, iterations: Infinity })]
        : []);
    return () => animaciones.forEach((a) => a.cancel());
  }, []);

  return (
    <div ref={marco} className={styles.marcoVivo} aria-hidden="true">
      <div ref={lienzo} className={styles.lienzo}>
        <div>
          {ESTRELLAS.map(([x, y]) => <span key={`${x}-${y}`} className={styles.estrellaViva} style={{ left: x - 3, top: y - 3 }} />)}
        </div>
        <div>
          {LUCES.map((luz, i) => <span key={i} className={styles.luz} style={{ width: luz.largo }} />)}
        </div>
      </div>
    </div>
  );
}

interface Props {
  /** El login ya las muestra bajo el logo: ahí no se repiten. */
  coordenadas?: boolean;
  /** Solo en el login, «rutas vivas» (elegida por el usuario el 2026-10-23):
   *  las rutas se trazan al entrar, las recorren luces doradas y las estrellas
   *  laten. En las pantallas de trabajo queda quieto, para no distraer.
   *  Sin haz ni giro del astrolabio: mueven capas del tamaño de la pantalla y,
   *  en equipos sin tarjeta gráfica, el login caía a 22 cuadros por segundo.
   *  Se mueve aunque el equipo pida «reducir movimiento» (decisión del usuario
   *  del 2026-10-23: muchos equipos del SNM traen las animaciones de Windows
   *  apagadas por rendimiento). Sin botón de pausa: el usuario lo quitó el
   *  mismo día (la WCAG 2.2.2 pide uno para lo que se mueve solo más de 5 s;
   *  se acepta porque es solo el login, que se ve unos segundos). */
  animado?: boolean;
}

export function FondoPagina({ coordenadas = true, animado = false }: Props) {
  return (
    <>
      <div className={styles.franja} />
      {/* data-movimiento: globals.css no lo frena con «reducir movimiento». */}
      <div className={styles.capa} data-movimiento={animado ? "" : undefined}>
        {/* El astrolabio, aparte: no se vuelve a dibujar mientras se trazan las rutas. */}
        <svg className={styles.carta} viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <g className={styles.astrolabio} fill="none" stroke="currentColor">
            {[600, 470, 340, 210].map((r) => <circle key={r} cx="800" cy="450" r={r} strokeWidth={r === 600 ? 2 : 1} />)}
            {MERIDIANOS.map((m) => <line key={m.clave} x1="800" y1="450" x2={m.x} y2={m.y} strokeWidth="1" strokeDasharray="2 8" />)}
            {GRADUACION.map((m) => <line key={m.clave} x1={m.x1} y1={m.y1} x2={m.x2} y2={m.y2} strokeWidth="1.2" />)}
          </g>
        </svg>
        <svg className={`${styles.carta} ${animado ? styles.animado : ""}`} viewBox="0 0 1600 900"
          preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <g className={styles.constelacion} fill="none" stroke="currentColor" strokeWidth="1.4">
            {RUTAS.map((r) => <polyline key={r} points={r} pathLength={1} />)}
          </g>
          {!animado && ESTRELLAS.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="3" className={styles.estrella} />)}
        </svg>
        {animado && <RutasVivas />}
      </div>
      {coordenadas && <div className={styles.coordenadas} aria-hidden="true">09° 01′ N<br />079° 32′ O</div>}
    </>
  );
}
