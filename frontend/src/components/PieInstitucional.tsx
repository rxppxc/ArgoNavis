import styles from "./PieInstitucional.module.css";

/** Pie de todas las páginas, también el del login. */
export function PieInstitucional() {
  return (
    <footer className={styles.pie}>
      <span>© {new Date().getFullYear()} Servicio Nacional de Migración · República de Panamá</span>
      <span className={styles.sello}>Uso oficial · ARGO NAVIS</span>
    </footer>
  );
}
