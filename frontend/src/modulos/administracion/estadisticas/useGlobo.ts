import { useRef, useState, type PointerEvent } from "react";

/** El globo con el detalle de un gráfico: qué dato muestra y dónde, en píxeles
 *  relativos al lienzo (el contenedor con `position: relative` del gráfico). */
export function useGlobo<T>() {
  const lienzo = useRef<HTMLDivElement>(null);
  const [activo, setActivo] = useState<{ dato: T; x: number; y: number } | null>(null);

  /** Lo pone sobre `marca`: centrado, o en su extremo derecho (`fin`, las barras
   *  horizontales). `arriba` (en píxeles de pantalla) reemplaza su borde superior. */
  function mostrar(dato: T, marca: Element, { alinear = "centro", arriba }: { alinear?: "centro" | "fin"; arriba?: number } = {}) {
    const contenedor = lienzo.current;
    if (!contenedor) return;
    const m = marca.getBoundingClientRect(), c = contenedor.getBoundingClientRect();
    const x = alinear === "fin" ? m.right : m.left + m.width / 2;
    setActivo({ dato, x: x - c.left, y: (arriba ?? m.top) - c.top });
  }

  function ocultar() {
    setActivo(null);
  }

  /** Al salir el puntero. Con el dedo no: el toque deja el foco en la marca y el
   *  globo se va al tocar en otro lado (blur). */
  function alSalir(e: PointerEvent) {
    if (e.pointerType !== "touch") ocultar();
  }

  return { lienzo, activo, mostrar, ocultar, alSalir };
}
