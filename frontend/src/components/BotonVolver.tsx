import { Link, useNavigate } from "react-router-dom";
import { IconoAtras } from "./Iconos";
import styles from "./BotonVolver.module.css";

/** `estado`: lo que le devuelve a la página de origen (el tripulante buscado en la consulta histórica). */
export function BotonVolver({ to, estado, onClick }: { to?: string; estado?: unknown; onClick?: () => void }) {
  const navegar = useNavigate();
  if (to)      return <Link to={to} state={estado} className={styles.btn}><IconoAtras />Volver</Link>;
  if (onClick) return <button className={styles.btn} onClick={onClick}><IconoAtras />Volver</button>;
  return        <button className={styles.btn} onClick={() => navegar(-1)}><IconoAtras />Volver</button>;
}
