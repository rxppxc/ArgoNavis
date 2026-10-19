import { useEffect } from "react";
import { useAtraparFoco } from "../hooks/useAtraparFoco";
import styles from "./ModalExpiracionSesion.module.css";

interface Props {
  segundos: number;
  onContinuar: () => void;
  onCerrarSesion: () => void;
}

export function ModalExpiracionSesion({ segundos, onContinuar, onCerrarSesion }: Props) {
  const min = Math.floor(segundos / 60);
  const seg = segundos % 60;
  const cuenta = min > 0
    ? `${min}:${seg.toString().padStart(2, "0")}`
    : `${segundos}s`;

  const refModal = useAtraparFoco(true);

  // Escape = continuar la sesión (la acción menos destructiva), nunca cerrarla.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onContinuar();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onContinuar]);

  return (
    <div className={styles.overlay}>
      <div
        ref={refModal}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="expiracion-titulo"
        aria-describedby="expiracion-texto"
      >
        <div className={styles.icono}>⏱</div>
        <h2 id="expiracion-titulo" className={styles.titulo}>Sesión por expirar</h2>
        <p id="expiracion-texto" className={styles.texto}>
          Tu sesión se cerrará automáticamente por inactividad en:
        </p>
        <div className={styles.cuenta}>{cuenta}</div>
        <div className={styles.botones}>
          <button className={styles.btnContinuar} onClick={onContinuar} data-focus-inicial>
            Continuar sesión
          </button>
          <button className={styles.btnSalir} onClick={onCerrarSesion}>
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
  );
}
