/**
 * Página 404: una dirección que no existe en ARGO NAVIS (un enlace incompleto o
 * escrito a mano). Antes cualquier ruta desconocida llevaba en silencio a las
 * bandejas y no se notaba que el enlace estaba mal. Con sesión o sin ella.
 */
import { Link, useLocation } from "react-router-dom";
import { IconoAncla } from "../../components/Iconos";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { useTituloDocumento } from "../../hooks/useTituloDocumento";
import styles from "./PaginaNoEncontrada.module.css";

export default function PaginaNoEncontrada() {
  const { usuario } = useAutenticacion();
  const { pathname } = useLocation();
  useTituloDocumento("Página no encontrada");
  const conSesion = !!usuario;

  return (
    <MarcoPagina publica={!conSesion} ancho="angosto">
      <div className={styles.tarjeta}>
        <div className={styles.icono}><IconoAncla tamano={34} /></div>
        <h1 className={styles.titulo}>No encontramos esta página</h1>
        <p className={styles.texto}>
          La dirección <code className={styles.ruta}>{pathname}</code> no existe en ARGO NAVIS. Puede que el
          enlace esté incompleto o que se haya copiado mal.
        </p>
        <Link to={conSesion ? "/dashboard" : "/login"} className={styles.boton}>
          {conSesion ? "Ir al inicio" : "Ir a iniciar sesión"}
        </Link>
      </div>
    </MarcoPagina>
  );
}
