import { useCallback, useEffect, useRef, useState } from "react";
import { vencimientoDelToken } from "../api/client";
import {
  AVISO_INACTIVIDAD_MS as AVISO_MS,
  LOGOUT_INACTIVIDAD_MS as LOGOUT_MS,
  ANOTAR_ACTIVIDAD_MS,
  MARGEN_RENOVACION_MS,
  REVISION_RENOVACION_MS,
} from "../constants/sesion";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { CLAVE_ACTIVIDAD, anotarActividad, leerActividad } from "../utils/actividad";
import { ModalExpiracionSesion } from "./ModalExpiracionSesion";

/** Cierre de sesión por inactividad (con aviso y cuenta regresiva) y renovación
 *  del token mientras el usuario trabaja. Solo existe con la sesión abierta: al
 *  cerrarse (también desde otra pestaña) se desmonta, y no queda un aviso de
 *  la sesión anterior esperando a la siguiente. */
export function GestorSesion({ children }: { children: React.ReactNode }) {
  const { estaAutenticado } = useAutenticacion();
  return <>{children}{estaAutenticado && <VigilanteSesion />}</>;
}

/** La inactividad es la de todas las pestañas (utils/actividad.ts): mientras se
 *  trabaja en una, las demás no avisan ni cierran la sesión. */
function VigilanteSesion() {
  const { cerrarSesion, extenderSesion } = useAutenticacion();
  // Hora a la que se cierra la sesión mientras se muestra el aviso (null = sin aviso).
  const [venceEn, setVenceEn] = useState<number | null>(null);
  // Lo mismo para los manejadores de eventos, que no esperan al siguiente render.
  const conAviso = useRef(false);

  // Renueva el token mientras el usuario trabaja: sin esto, quien no hacía
  // pausas perdía la sesión (y lo que estuviera llenando) al vencer el token.
  const renovacion = useRef({ enCurso: false, ultimaRevision: 0 });
  const renovarSiVence = useCallback(() => {
    const r = renovacion.current;
    const instante = Date.now();
    if (r.enCurso || instante - r.ultimaRevision < REVISION_RENOVACION_MS) return;
    r.ultimaRevision = instante;
    const vence = vencimientoDelToken();
    if (vence === null || vence - instante > MARGEN_RENOVACION_MS) return;
    r.enCurso = true;
    extenderSesion()
      .catch(() => { /* si el token ya no sirve, el interceptor cierra la sesión */ })
      .finally(() => { r.enCurso = false; });
  }, [extenderSesion]);

  useEffect(() => {
    let revision: ReturnType<typeof setTimeout> | undefined;

    /** Según la última actividad, de cualquier pestaña: sigue, avisa o cierra;
     *  y deja programada la próxima revisión. */
    function revisar() {
      clearTimeout(revision);
      const ahora = Date.now();
      const ultima = leerActividad();
      if (ahora - ultima >= LOGOUT_MS) {
        conAviso.current = false;
        setVenceEn(null);
        cerrarSesion(true, true);
        return;
      }
      conAviso.current = ahora - ultima >= AVISO_MS;
      setVenceEn(conAviso.current ? ultima + LOGOUT_MS : null);
      revision = setTimeout(revisar, ultima + (conAviso.current ? LOGOUT_MS : AVISO_MS) - ahora);
    }

    function enActividad() {
      if (conAviso.current) return;   // con el aviso abierto, solo cuenta «Continuar sesión»
      if (Date.now() - leerActividad() >= ANOTAR_ACTIVIDAD_MS) anotarActividad();
      renovarSiVence();
    }

    // Actividad en otra pestaña (o «Continuar sesión» allá): se revisa ya, y el
    // aviso de esta, si lo había, se quita.
    function enOtraPestana(e: StorageEvent) {
      if (e.key === CLAVE_ACTIVIDAD) revisar();
    }

    anotarActividad();   // entrar o abrir una página también es actividad
    revision = setTimeout(revisar, AVISO_MS);
    const eventos = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    eventos.forEach(ev => window.addEventListener(ev, enActividad, { passive: true }));
    window.addEventListener("storage", enOtraPestana);
    return () => {
      clearTimeout(revision);
      eventos.forEach(ev => window.removeEventListener(ev, enActividad));
      window.removeEventListener("storage", enOtraPestana);
    };
  }, [cerrarSesion, renovarSiVence]);

  const alContinuar = useCallback(async () => {
    conAviso.current = false;
    setVenceEn(null);
    anotarActividad();   // las demás pestañas quitan su aviso
    try { await extenderSesion(); } catch { /* el interceptor cerrará sesión si el token expiró */ }
  }, [extenderSesion]);

  const alSalir = useCallback(() => {
    conAviso.current = false;
    setVenceEn(null);
    cerrarSesion(true, false);
  }, [cerrarSesion]);

  return venceEn === null ? null : (
    <ModalExpiracionSesion venceEn={venceEn} onContinuar={alContinuar} onCerrarSesion={alSalir} />
  );
}
