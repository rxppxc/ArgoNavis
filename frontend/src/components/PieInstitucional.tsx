import styles from "./PieInstitucional.module.css";

/** Pie de todas las páginas, el mismo del login. */
export function PieInstitucional() {
  return (
    <footer className={styles.pie}>
      <span>© {new Date().getFullYear()} Servicio Nacional de Migración · República de Panamá</span>
    </footer>
  );
}
