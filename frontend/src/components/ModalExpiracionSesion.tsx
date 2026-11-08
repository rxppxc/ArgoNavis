import { useEffect, useState } from "react";
import { useAtraparFoco } from "../hooks/useAtraparFoco";
import { IconoReloj } from "./Iconos";
import styles from "./ModalExpiracionSesion.module.css";

interface Props {
  /** Hora (ms desde epoch) a la que se cierra la sesión. */
  venceEn: number;
  onContinuar: () => void;
  onCerrarSesion: () => void;
}

export function ModalExpiracionSesion({ venceEn, onContinuar, onCerrarSesion }: Props) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const reloj = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(reloj);
  }, []);

  const segundos = Math.max(0, Math.ceil((venceEn - ahora) / 1000));
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
        {/* El ícono de la aplicación y no un emoji, que cambia según el sistema. */}
        <div className={styles.icono} aria-hidden="true"><IconoReloj tamano={30} /></div>
        <h2 id="expiracion-titulo" className={styles.titulo}>Sesión por expirar</h2>
        <p id="expiracion-texto" className={styles.texto}>
          Tu sesión se cerrará automáticamente por inactividad en:
        </p>
        <div className={styles.cuenta}>{cuenta}</div>
        <div className={styles.botones}>
          <button type="button" className={styles.btnContinuar} onClick={onContinuar} data-focus-inicial>
            Continuar sesión
          </button>
          <button type="button" className={styles.btnSalir} onClick={onCerrarSesion}>
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
  );
}
