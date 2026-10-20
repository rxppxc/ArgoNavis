import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { usePermisos } from "../hooks/usePermisos";
import { RUTA_CAMBIAR_CONTRASENA } from "../api/client";
import {
  IconoUsuarios, IconoEstadisticas, IconoEscudo, IconoArchivo, IconoAncla, IconoActividad,
  IconoSalir, IconoChevronAbajo, IconoLlave,
} from "./Iconos";
import { SelectorTema } from "./SelectorTema";
import styles from "./MenuCabecera.module.css";

export function MenuCabecera() {
  const { usuario, cerrarSesion } = useAutenticacion();
  const { tiene, esAdmin, esSysAdmin } = usePermisos();
  const navegar = useNavigate();
  const [abierto, setAbierto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const esPacifico = !esAdmin && tiene("T-PROCESAR-PACIFICO");
  // Quién está en la sesión y con qué rol: se ve junto al menú (escritorio) y arriba del panel.
  const nombre = usuario?.full_name?.trim() || usuario?.username || "";
  const detalle = [usuario?.rol_personalizado?.nombre, usuario?.agencia?.nombre].filter(Boolean).join(" · ");

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
      {nombre && (
        <div className={styles.identidad}>
          <span className={styles.identidadNombre} title={nombre}>{nombre}</span>
          {detalle && <span className={styles.identidadDetalle} title={detalle}>{detalle}</span>}
        </div>
      )}
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
            {nombre && (
              <>
                <div className={styles.cuenta}>
                  <span className={styles.cuentaNombre}>{nombre}</span>
                  {detalle && <span className={styles.cuentaDetalle}>{detalle}</span>}
                </div>
                <div className={styles.sep} />
              </>
            )}
            {/* El Administrador ve todo; el SysAdmin, usuarios, roles y bitácora. */}
            {(esAdmin || esSysAdmin) && (
              <>
                <Link to="/admin" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoUsuarios />Usuarios
                </Link>
                <Link to="/admin/roles" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoEscudo />Roles y permisos
                </Link>
                {esAdmin && (
                  <>
                    <Link to="/admin/tramites" className={styles.item} onClick={() => setAbierto(false)}>
                      <IconoArchivo />Catálogo de trámites
                    </Link>
                    <Link to="/admin/catalogos" className={styles.item} onClick={() => setAbierto(false)}>
                      <IconoAncla />Agencias, puestos y países
                    </Link>
                    <Link to="/admin/stats" className={styles.item} onClick={() => setAbierto(false)}>
                      <IconoEstadisticas />Estadísticas
                    </Link>
                  </>
                )}
                <Link to="/admin/bitacora" className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoActividad />Bitácora
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
            {usuario?.user_type === "local" && (
              <>
                <Link to={RUTA_CAMBIAR_CONTRASENA} className={styles.item} onClick={() => setAbierto(false)}>
                  <IconoLlave />Cambiar contraseña
                </Link>
                <div className={styles.sep} />
              </>
            )}
            <div className={styles.tema}>
              <span className={styles.temaTitulo} aria-hidden="true">Tema</span>
              <SelectorTema />
            </div>
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
