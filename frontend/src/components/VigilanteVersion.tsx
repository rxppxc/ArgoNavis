import { useEffect } from "react";
import { esVersionNueva, huellaDeHtml, huellaDelDocumento } from "../utils/version";
import { useNotificacion } from "./Notificaciones";

/** La huella de la página cargada: se toma al cargar este módulo, que va en el paquete
 *  inicial, antes de que se pida ninguna página aparte (utils/version.ts). */
const HUELLA_CARGADA = typeof document === "undefined" ? "" : huellaDelDocumento(document);

/** Cada cuánto se revisa con la pestaña a la vista, y lo mínimo entre dos revisiones
 *  (volver a la pestaña varias veces seguidas no pide el index.html cada vez). */
const REVISAR_CADA_MS = 5 * 60_000;
const MINIMO_ENTRE_REVISIONES_MS = 60_000;

const TEXTO_VERSION_NUEVA =
  "Hay una versión nueva de ARGO NAVIS. Termina o guarda lo que estés haciendo y recarga la página.";

/**
 * Avisa cuando se desplegó una versión nueva con la página abierta (2026-11-11): antes se
 * seguía con la anterior hasta recargar, y lo nuevo (los avisos, por ejemplo) no se veía.
 * Revisa cada 5 minutos con la pestaña a la vista y al volver a ella. El aviso no se cierra
 * solo y la recarga la decide el usuario, que puede estar a mitad de un formulario. Cada
 * versión se avisa una vez: si lo cierra, no vuelve a salir hasta la siguiente.
 */
export function VigilanteVersion() {
  const { mostrar } = useNotificacion();

  useEffect(() => {
    if (!HUELLA_CARGADA) return;   // desarrollo: Vite sirve el código sin empaquetar
    let avisada = "";
    let ultima = 0;
    let activo = true;

    async function revisar() {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - ultima < MINIMO_ENTRE_REVISIONES_MS) return;
      ultima = Date.now();
      try {
        // Sin caché: el index.html no lleva hash en el nombre.
        const respuesta = await fetch("/", { cache: "no-store", credentials: "same-origin" });
        if (!respuesta.ok) return;
        const servida = huellaDeHtml(await respuesta.text());
        if (!activo || !esVersionNueva(HUELLA_CARGADA, servida) || servida === avisada) return;
        avisada = servida;
        mostrar(TEXTO_VERSION_NUEVA, "info", {
          sello: "version", duracionMs: 0,
          accion: { texto: "Recargar", alHacer: () => window.location.reload() },
        });
      } catch {
        // Sin conexión (VPN caída, servidor reiniciándose): se vuelve a probar en la próxima vuelta.
      }
    }

    const intervalo = window.setInterval(revisar, REVISAR_CADA_MS);
    document.addEventListener("visibilitychange", revisar);
    return () => {
      activo = false;
      window.clearInterval(intervalo);
      document.removeEventListener("visibilitychange", revisar);
    };
  }, [mostrar]);

  return null;
}
