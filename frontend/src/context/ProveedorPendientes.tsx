import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { apiPendientes, type Pendientes } from "../api/pendientes";
import { CONSULTA_PENDIENTES_MS } from "../constants/sesion";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { ContextoPendientes, type ValorPendientes } from "../hooks/usePendientes";

/** Avisa a las otras pestañas que se abrió la campana (evento `storage`). */
const CLAVE_NOVEDADES_VISTAS = "novedades-vistas";
const PREFIJO_TITULO = /^\(\d+\) /;

interface Cargados {
  usuarioId: number;
  valor: Pendientes;
}

/** Notificaciones internas (la campana de la cabecera). Consulta /pendientes
 *  al entrar, al cambiar de página, cada minuto con la pestaña a la vista y al
 *  volver a ella. La consulta no cuenta como actividad (la anotan el mouse y
 *  el teclado, App.tsx): no impide el cierre de la sesión por inactividad.
 *  Con pendientes, la pestaña del navegador dice "(N) …". */
export function ProveedorPendientes({ children }: { children: ReactNode }) {
  const { usuario } = useAutenticacion();
  // Con el cambio de contraseña pendiente la API no responde nada más.
  const usuarioId = usuario && !usuario.debe_cambiar_password ? usuario.id : null;
  const { pathname } = useLocation();
  const [cargados, setCargados] = useState<Cargados | null>(null);
  // Si dos consultas se cruzan, vale la última que se pidió.
  const secuencia = useRef(0);

  const refrescar = useCallback(() => {
    if (usuarioId === null) return;
    const mia = ++secuencia.current;
    apiPendientes.consultar()
      .then((valor) => { if (mia === secuencia.current) setCargados({ usuarioId, valor }); })
      .catch(() => { /* se reintenta en la próxima vuelta; un 401 ya cierra la sesión (api/client.ts) */ });
  }, [usuarioId]);

  // Al entrar y al cambiar de página (llegar a una bandeja, volver de un expediente).
  useEffect(() => { refrescar(); }, [refrescar, pathname]);

  useEffect(() => {
    if (usuarioId === null) return;
    const aLaVista = () => document.visibilityState === "visible";
    const reloj = setInterval(() => { if (aLaVista()) refrescar(); }, CONSULTA_PENDIENTES_MS);
    const alVolver = () => { if (aLaVista()) refrescar(); };
    // Otra pestaña abrió la campana: sus novedades también quedan leídas aquí.
    const enOtraPestana = (e: StorageEvent) => { if (e.key === CLAVE_NOVEDADES_VISTAS) refrescar(); };
    document.addEventListener("visibilitychange", alVolver);
    window.addEventListener("storage", enOtraPestana);
    return () => {
      clearInterval(reloj);
      document.removeEventListener("visibilitychange", alVolver);
      window.removeEventListener("storage", enOtraPestana);
    };
  }, [usuarioId, refrescar]);

  const marcarVistas = useCallback(async () => {
    try {
      await apiPendientes.marcarVistas();
    } catch {
      return;   // quedan sin leer: se marcan la próxima vez que abra la campana
    }
    try { localStorage.setItem(CLAVE_NOVEDADES_VISTAS, String(Date.now())); } catch { /* las otras pestañas se enteran en su próxima consulta */ }
    // El punto se apaga ya; cada novedad conserva su marca hasta la próxima consulta,
    // para que en el panel abierto se sigan distinguiendo las que llegaron.
    setCargados((c) => (c ? { ...c, valor: { ...c.valor, no_leidas: 0 } } : c));
  }, []);

  // Solo los datos del usuario actual (los de una sesión anterior no se muestran).
  const datos = cargados && cargados.usuarioId === usuarioId ? cargados.valor : null;
  const total = datos?.pendientes.reduce((suma, p) => suma + p.cantidad, 0) ?? 0;

  // "(N) " delante del título de la pestaña. Cada página pone el suyo
  // (useTituloDocumento): se vuelve a poner el prefijo cuando el título cambia.
  useEffect(() => {
    const prefijo = total > 0 ? `(${total}) ` : "";
    const aplicar = () => {
      const deseado = prefijo + document.title.replace(PREFIJO_TITULO, "");
      if (document.title !== deseado) document.title = deseado;
    };
    aplicar();
    const titulo = document.querySelector("title");
    const observador = new MutationObserver(aplicar);
    if (titulo) observador.observe(titulo, { childList: true, characterData: true, subtree: true });
    return () => {
      observador.disconnect();
      document.title = document.title.replace(PREFIJO_TITULO, "");
    };
  }, [total]);

  const valor = useMemo<ValorPendientes>(
    () => ({ datos, total, refrescar, marcarVistas }),
    [datos, total, refrescar, marcarVistas],
  );
  return <ContextoPendientes.Provider value={valor}>{children}</ContextoPendientes.Provider>;
}
