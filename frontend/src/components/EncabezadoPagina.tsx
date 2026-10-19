import type { ReactNode } from "react";
import styles from "./EncabezadoPagina.module.css";

interface Props {
  titulo: ReactNode;
  descripcion?: ReactNode;
  /** Botones a la derecha (p. ej. "Nueva solicitud"). */
  acciones?: ReactNode;
}

/** Encabezado común de las páginas: título y descripción a la izquierda y las
 *  acciones a la derecha. Antes cada página armaba el suyo (centrado, con
 *  ícono, sin ícono). El expediente lleva el propio (número y estado). */
export function EncabezadoPagina({ titulo, descripcion, acciones }: Props) {
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
