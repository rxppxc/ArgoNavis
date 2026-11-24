import { useEffect, useState } from "react";

/** La hora actual, al minuto (el reloj del inicio, 2026-11-24): se actualiza justo al cambiar el
 *  minuto y al volver a la pestaña (en segundo plano, el navegador demora los temporizadores). */
export function useMinutoActual(): Date {
  const [ahora, setAhora] = useState(() => new Date());

  useEffect(() => {
    let espera: ReturnType<typeof setTimeout>;
    const programar = () => {
      // Un poco después del cambio de minuto, para no quedarse en el anterior.
      espera = setTimeout(() => {
        setAhora(new Date());
        programar();
      }, 60_000 - (Date.now() % 60_000) + 50);
    };
    programar();
    const alVolver = () => { if (document.visibilityState === "visible") setAhora(new Date()); };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearTimeout(espera);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, []);

  return ahora;
}
