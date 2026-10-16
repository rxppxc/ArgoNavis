/**
 * Tema visual (claro/oscuro) compartido por toda la aplicación.
 *
 * El usuario elige una preferencia: claro, oscuro o "sistema" (sigue al del
 * sistema operativo y cambia en vivo si el usuario lo cambia en su equipo).
 * Se guarda en localStorage["tema"] ("light" | "dark" | "system"); sin valor
 * guardado vale "system".
 *
 * `public/tema-inicial.js` aplica la misma lógica antes de que cargue React,
 * para que la primera pintada ya salga en el tema correcto: si cambias una,
 * cambia la otra.
 *
 * Uso:
 *   const { tema, preferencia, elegirPreferencia } = useTema();
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Tema = "dark" | "light";
export type PreferenciaTema = Tema | "system";

interface CtxTema {
  /** Tema efectivo (ya resuelto si la preferencia es "system"). */
  tema: Tema;
  preferencia: PreferenciaTema;
  elegirPreferencia: (preferencia: PreferenciaTema) => void;
}

const CLAVE = "tema";
const CONSULTA_CLARO = "(prefers-color-scheme: light)";
/** Color de la barra del navegador en móviles: el de la cabecera. */
const COLOR_BARRA: Record<Tema, string> = { dark: "#0F1218", light: "#FFFFFF" };

const ContextoTema = createContext<CtxTema>({ tema: "dark", preferencia: "system", elegirPreferencia: () => {} });

function leerPreferencia(): PreferenciaTema {
  try {
    const guardada = localStorage.getItem(CLAVE);
    if (guardada === "light" || guardada === "dark" || guardada === "system") return guardada;
  } catch {
    // Almacenamiento bloqueado: se sigue al sistema.
  }
  return "system";
}

function temaDelSistema(): Tema {
  return window.matchMedia(CONSULTA_CLARO).matches ? "light" : "dark";
}

function aplicar(tema: Tema) {
  const raiz = document.documentElement;
  if (raiz.getAttribute("data-theme") === tema) return;
  // Sin transiciones durante el cambio: los colores cambian de golpe en vez
  // de animarse componente por componente.
  raiz.classList.add("sin-transiciones");
  raiz.setAttribute("data-theme", tema);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", COLOR_BARRA[tema]);
  requestAnimationFrame(() => requestAnimationFrame(() => raiz.classList.remove("sin-transiciones")));
}

export function ProveedorTema({ children }: { children: ReactNode }) {
  const [preferencia, setPreferencia] = useState<PreferenciaTema>(leerPreferencia);
  const [sistema, setSistema] = useState<Tema>(temaDelSistema);
  const tema: Tema = preferencia === "system" ? sistema : preferencia;

  // Sigue al sistema operativo en vivo (solo se nota con la preferencia "system").
  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_CLARO);
    const cambiar = () => setSistema(consulta.matches ? "light" : "dark");
    consulta.addEventListener("change", cambiar);
    return () => consulta.removeEventListener("change", cambiar);
  }, []);

  useEffect(() => { aplicar(tema); }, [tema]);

  const elegirPreferencia = useCallback((nueva: PreferenciaTema) => {
    setPreferencia(nueva);
    try {
      localStorage.setItem(CLAVE, nueva);
    } catch {
      // Sin almacenamiento: la elección dura mientras la pestaña esté abierta.
    }
  }, []);

  const valor = useMemo(() => ({ tema, preferencia, elegirPreferencia }), [tema, preferencia, elegirPreferencia]);

  return <ContextoTema.Provider value={valor}>{children}</ContextoTema.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- el hook va junto a su proveedor; separarlos solo cambiaría las rutas de import
export const useTema = () => useContext(ContextoTema);
