import type { ReactNode } from "react";
import { FondoPagina } from "./FondoPagina";
import { BotonVolver } from "./BotonVolver";
import { CabeceraInstitucional } from "./CabeceraInstitucional";
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
 *  del login, con el menú del usuario a la derecha; "Volver" va arriba del contenido. */
export function MarcoPagina({ children, volverA, publica = false, ancho = "normal" }: Props) {
  const claseAncho = ancho === "amplio" ? styles.amplio : ancho === "angosto" ? styles.angosto : "";
  return (
    <div className={styles.pagina}>
      <CabeceraInstitucional derecha={!publica && <MenuCabecera />} inicio={publica ? undefined : "/dashboard"} />

      <div className={styles.medio}>
        <FondoPagina />
        <main className={`${styles.contenido} ${claseAncho}`}>
          {volverA && <div className={styles.volver}><BotonVolver to={volverA} /></div>}
          {children}
        </main>
      </div>

      <PieInstitucional />
    </div>
  );
}
