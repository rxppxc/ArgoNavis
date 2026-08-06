import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { usePermisos } from "../hooks/usePermisos";
import { useTema } from "../context/ContextoTema";
import {
  IconoUsuarios, IconoEstadisticas, IconoEscudo,
  IconoSol, IconoLuna, IconoSalir, IconoChevronAbajo,
} from "./Iconos";
import styles from "./MenuCabecera.module.css";

export function MenuCabecera() {
  const { cerrarSesion } = useAutenticacion();
  const { tiene, esAdmin } = usePermisos();
  const { tema, alternar } = useTema();
  const navegar = useNavigate();
  const [abierto, setAbierto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const esPacifico = !esAdmin && tiene("T-PROCESAR-PACIFICO");
  const esOscuro   = tema === "dark";

  useEffect(() => {
    function clickFuera(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false);
    }
    if (abierto) document.addEventListener("mousedown", clickFuera);
    return () => document.removeEventListener("mousedown", clickFuera);
  }, [abierto]);

  function salir() {
    setAbierto(false);
    cerrarSesion(true, false);
    navegar("/login");
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.dropdown} ref={ref}>
        <button
          className={`${styles.menuBtn} ${abierto ? styles.menuBtnOpen : ""}`}
          onClick={() => setAbierto(v => !v)}
          aria-haspopup="menu"
          aria-expanded={abierto}
        >
          Menú
          <span className={`${styles.chevron} ${abierto ? styles.chevronOpen : ""}`}>
            <IconoChevronAbajo />
          </span>
        </button>

        {abierto && (
          <div className={styles.panel}>
            {esAdmin && (
              <>
                <Link to="/admin" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoUsuarios />Usuarios
                </Link>
                <Link to="/admin/roles" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoEscudo />Roles y permisos
                </Link>
                <Link to="/admin/stats" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoEstadisticas />Estadísticas
                </Link>
                <div className={styles.sep} />
              </>
            )}
            {esPacifico && (
              <>
                <Link to="/admin/stats" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoEstadisticas />Estadísticas
                </Link>
                <div className={styles.sep} />
              </>
            )}
            <button className={styles.item} onClick={() => { alternar(); setAbierto(false); }}>
              {esOscuro ? <IconoSol /> : <IconoLuna />}
              {esOscuro ? "Modo claro" : "Modo oscuro"}
            </button>
            <div className={styles.sep} />
            <button className={`${styles.item} ${styles.itemSalir}`} onClick={salir}>
              <IconoSalir />Salir
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
