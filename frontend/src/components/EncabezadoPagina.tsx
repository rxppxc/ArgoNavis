import type { ReactNode } from "react";
import { useTituloDocumento } from "../hooks/useTituloDocumento";
import styles from "./EncabezadoPagina.module.css";

interface Props {
  titulo: ReactNode;
  /** Título de la pestaña del navegador, si `titulo` no es un texto. */
  tituloDocumento?: string;
  descripcion?: ReactNode;
  /** Botones a la derecha (p. ej. "Nueva solicitud"). */
  acciones?: ReactNode;
}

/** Encabezado común de las páginas: título y descripción a la izquierda y las
 *  acciones a la derecha, y el mismo título en la pestaña del navegador. Antes
 *  cada página armaba el suyo (centrado, con ícono, sin ícono). El expediente
 *  lleva el propio (número y estado). */
export function EncabezadoPagina({ titulo, tituloDocumento, descripcion, acciones }: Props) {
  useTituloDocumento(tituloDocumento ?? (typeof titulo === "string" ? titulo : null));
  return (
    <header className={styles.encabezado}>
      <div className={styles.texto}>
        <h1 className={styles.titulo}>{titulo}</h1>
        {descripcion && <p className={styles.descripcion}>{descripcion}</p>}
      </div>
      {acciones && <div className={styles.acciones}>{acciones}</div>}
    </header>
  );
}
