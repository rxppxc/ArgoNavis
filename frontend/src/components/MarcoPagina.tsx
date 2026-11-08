import type { ReactNode } from "react";
import { FondoPagina } from "./FondoPagina";
import { BotonVolver } from "./BotonVolver";
import { CabeceraInstitucional } from "./CabeceraInstitucional";
import { CampanaPendientes } from "./CampanaPendientes";
import { MenuCabecera } from "./MenuCabecera";
import { PieInstitucional } from "./PieInstitucional";
import styles from "./MarcoPagina.module.css";

interface Props {
  children: ReactNode;
  /** Ruta del botón "Volver" (sin botón si no se indica). */
  volverA?: string;
  /** Página pública (sin sesión): no muestra el menú. */
  publica?: boolean;
  /** angosto: una sola tarjeta (cambiar contraseña); el "Volver" queda alineado con ella. */
  ancho?: "angosto" | "normal" | "amplio";
}

/** Estructura común de página: la misma franja institucional y el mismo pie
 *  del login, con la campana de notificaciones y el menú del usuario a la
 *  derecha; "Volver" va arriba del contenido. */
export function MarcoPagina({ children, volverA, publica = false, ancho = "normal" }: Props) {
  const claseAncho = ancho === "amplio" ? styles.amplio : ancho === "angosto" ? styles.angosto : "";
  return (
    <div className={styles.pagina}>
      {/* Con el teclado, el primer Tab ofrece saltar la cabecera (globals.css). */}
      <a href="#contenido" className="saltar-contenido">Saltar al contenido</a>
      <CabeceraInstitucional derecha={!publica && <><CampanaPendientes /><MenuCabecera /></>}
        inicio={publica ? undefined : "/dashboard"} />

      <div className={styles.medio}>
        <FondoPagina />
        <main id="contenido" tabIndex={-1} className={`${styles.contenido} ${claseAncho}`}>
          {volverA && <div className={styles.volver}><BotonVolver to={volverA} /></div>}
          {children}
        </main>
      </div>

      <PieInstitucional />
    </div>
  );
}
