import { fechaEnPalabras } from "./presentacion";
import styles from "./PaginaSolicitud.module.css";

/** La fecha elegida, en palabras, bajo su campo («jueves, 13 de noviembre de 2026»).
 *  aria-hidden: el lector de pantalla ya anuncia el campo de fecha en su idioma, y
 *  así no se suma al nombre del campo. */
export function FechaEnPalabras({ iso }: { iso: string | null | undefined }) {
  const texto = fechaEnPalabras(iso);
  return texto ? <small className={styles.fechaEnPalabras} aria-hidden="true">{texto}</small> : null;
}
