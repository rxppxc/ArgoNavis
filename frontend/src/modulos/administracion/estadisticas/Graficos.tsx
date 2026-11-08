/**
 * Piezas comunes de los gráficos de Estadísticas: la tarjeta (título, qué mide
 * y su vista en tabla), el globo con el detalle, la leyenda, el medidor y las
 * barras horizontales.
 *
 * Hechos a mano en HTML y CSS, sin librería de gráficos: la CSP no admite las
 * que usan eval, y así toman los colores del tema (`--graf-*`) en claro y en
 * oscuro. Cada gráfico tiene su tabla con las mismas cifras (para lectores de
 * pantalla y para quien prefiera los números) y el globo sale igual con el
 * mouse, con el foco del teclado y con el dedo.
 */
import { useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { IconoTabla } from "../../../components/Iconos";
import { cifra, proporcion, type Serie } from "./calculos";
import { useGlobo } from "./useGlobo";
import styles from "./Graficos.module.css";

interface PropsTarjeta {
  titulo: string;
  /** Qué mide, en palabras de todos los días. */
  descripcion?: ReactNode;
  /** Las mismas cifras en una tabla: el botón «Ver tabla» alterna entre las dos. */
  tabla?: ReactNode;
  /** A todo el ancho de la grilla. */
  ancha?: boolean;
  children: ReactNode;
}

export function TarjetaGrafico({ titulo, descripcion, tabla, ancha = false, children }: PropsTarjeta) {
  const id = useId();
  const [enTabla, setEnTabla] = useState(false);
  return (
    <section className={`${styles.tarjeta} ${ancha ? styles.ancha : ""}`} aria-labelledby={id}>
      <div className={styles.cabecera}>
        <div className={styles.titulos}>
          <h3 id={id}>{titulo}</h3>
          {descripcion && <p>{descripcion}</p>}
        </div>
        {tabla && (
          <button type="button" className={styles.botonTabla} aria-pressed={enTabla} onClick={() => setEnTabla((v) => !v)}>
            <IconoTabla />Ver tabla
          </button>
        )}
      </div>
      {enTabla ? <div className={styles.envoltorioTabla}>{tabla}</div> : children}
    </section>
  );
}

/** El detalle de una marca, encima de ella; se corre hacia adentro si no cabe.
 *  Es solo visual: la marca lleva el mismo texto en su aria-label. */
export function Globo({ x, y, children }: { x: number; y: number; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const globo = ref.current, lienzo = globo?.parentElement;
    if (!globo || !lienzo) return;
    const mitad = globo.offsetWidth / 2;
    globo.style.left = `${Math.min(Math.max(x, mitad), Math.max(mitad, lienzo.clientWidth - mitad))}px`;
  }, [x, y, children]);
  return <div ref={ref} className={styles.globo} style={{ top: y }} aria-hidden="true">{children}</div>;
}

/** Una línea del globo: la cifra primero (es lo que se busca) y la serie después. */
export function FilaGlobo({ serie, valor, etiqueta }: { serie?: Serie; valor: string; etiqueta: string }) {
  return (
    <div className={styles.globoFila}>
      <span className={serie ? `${styles.clave} ${styles[serie]}` : styles.clave} />
      <strong>{valor}</strong>
      <span>{etiqueta}</span>
    </div>
  );
}

export function Leyenda({ items }: { items: { serie: Serie; etiqueta: string }[] }) {
  return (
    <ul className={styles.leyenda}>
      {items.map((i) => (
        <li key={i.serie}><span className={`${styles.muestra} ${styles[i.serie]}`} aria-hidden="true" />{i.etiqueta}</li>
      ))}
    </ul>
  );
}

const COLOR_ICONO: Record<Serie, string> = {
  revision: styles.iconoRevision, correccion: styles.iconoCorreccion, aprobada: styles.iconoAprobada,
  denegada: styles.iconoDenegada, finalizada: styles.iconoFinalizada, expirada: styles.iconoExpirada, fuera: styles.iconoFuera,
};

interface PropsIndicador {
  icono: ReactNode;
  /** El color del ícono; sin él, neutro (lo que no es un estado). */
  tono?: Serie;
  etiqueta: string;
  valor: string;
  /** Qué parte es de qué: el medidor va en el color de su serie. */
  medidor?: { valor: number; total: number; serie: Serie };
  nota?: ReactNode;
}

/** Una cifra suelta (la forma correcta para un número: no hace falta un gráfico). */
export function Indicador({ icono, tono, etiqueta, valor, medidor, nota }: PropsIndicador) {
  return (
    <div className={styles.indicador}>
      <div className={styles.indicadorCabeza}>
        <span className={`${styles.indicadorIcono} ${tono ? COLOR_ICONO[tono] : ""}`}>{icono}</span>
        <span className={styles.indicadorEtiqueta}>{etiqueta}</span>
      </div>
      <span className={styles.indicadorValor}>{valor}</span>
      {medidor && <Medidor {...medidor} />}
      {nota && <span className={styles.indicadorNota}>{nota}</span>}
    </div>
  );
}

/** Una proporción contra su total: el relleno en el color de la serie y la pista
 *  en un tono más claro del mismo. Decorativo: la cifra va escrita al lado. */
export function Medidor({ valor, total, serie }: { valor: number; total: number; serie: Serie }) {
  return (
    <div className={`${styles.medidor} ${styles[serie]}`} aria-hidden="true">
      <div className={styles.medidorRelleno} style={{ width: `${proporcion(valor, total) * 100}%` }} />
    </div>
  );
}

export interface FilaBarras {
  clave: string;
  nombre: string;
  /** En orden; el largo de la barra es la suma. */
  segmentos: { serie: Serie; valor: number }[];
  /** Para lectores de pantalla: la fila completa en palabras. */
  descripcion: string;
}

/** Una barra por fila, con la cifra en la punta; partida en segmentos si la fila
 *  tiene varios. Toda la fila responde al mouse, al foco y al dedo. */
export function BarrasHorizontales({ filas, globo }: { filas: FilaBarras[]; globo: (clave: string) => ReactNode }) {
  const { lienzo, activo, mostrar, ocultar, alSalir } = useGlobo<string>();
  const total = (f: FilaBarras) => f.segmentos.reduce((suma, s) => suma + s.valor, 0);
  const maximo = Math.max(1, ...filas.map(total));

  function enfocar(clave: string, fila: Element) {
    mostrar(clave, fila.querySelector("[data-barra]") ?? fila, { alinear: "fin" });
  }

  return (
    <div className={styles.lienzo} ref={lienzo}>
      <ul className={styles.barras}>
        {filas.map((f) => (
          <li
            key={f.clave}
            className={`${styles.filaBarra} ${activo?.dato === f.clave ? styles.filaActiva : ""}`}
            tabIndex={0}
            aria-label={f.descripcion}
            onPointerEnter={(e) => enfocar(f.clave, e.currentTarget)}
            onPointerLeave={alSalir}
            onFocus={(e) => enfocar(f.clave, e.currentTarget)}
            onBlur={ocultar}
          >
            <span className={styles.nombreBarra}>{f.nombre}</span>
            <span className={styles.pista}>
              <span className={styles.barra} style={{ width: `${proporcion(total(f), maximo) * 100}%` }} data-barra>
                <span className={styles.segmentos}>
                  {f.segmentos.filter((s) => s.valor > 0).map((s) => (
                    <span key={s.serie} className={`${styles.segmento} ${styles[s.serie]}`} style={{ flexGrow: s.valor }} />
                  ))}
                </span>
                <span className={styles.valorPunta}>{cifra(total(f))}</span>
              </span>
            </span>
          </li>
        ))}
      </ul>
      {activo && <Globo x={activo.x} y={activo.y}>{globo(activo.dato)}</Globo>}
    </div>
  );
}
