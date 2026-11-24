/**
 * Guarda el borrador de una solicitud nueva mientras se llena (2026-11-23): los datos un momento
 * después de cada cambio y los archivos solo cuando cambian (cada guardado copia el archivo
 * entero). Si el formulario queda vacío, borra lo guardado. Sin clave (al corregir), no hace nada.
 *
 * - Lo recuperado no se vuelve a guardar hasta que cambie algo: las 24 horas cuentan desde el
 *   último cambio, no desde que se abrió la página.
 * - Al salir de la página («Volver», el menú) lo que esperaba su momento se guarda enseguida.
 * - `descartar` (al enviar o al empezar de nuevo) borra el borrador y cancela lo pendiente: sin
 *   eso, salir justo después lo volvería a guardar.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { borrarBorrador, guardarBorrador } from "./almacenBorradores";
import { cuandoSeGuardo, tieneContenido, type ArchivosBorrador, type DatosBorrador } from "./borradorSolicitud";

const ESPERA_GUARDADO_MS = 700;

export interface EstadoBorrador {
  /** Cuándo se guardó por última vez («hoy a las 10:42 a. m.»), o null si no se ha guardado. */
  guardado:  string | null;
  /** Borra el borrador y cancela lo pendiente. */
  descartar: () => Promise<void>;
}

/** `datos` y `archivos` tienen que ser estables entre cambios (useMemo): cada objeto nuevo
 *  vuelve a programar el guardado. `yaGuardado`: el formulario empezó con un borrador recuperado. */
export function useBorradorSolicitud(
  clave: string | null, datos: DatosBorrador, archivos: ArchivosBorrador, yaGuardado: boolean,
): EstadoBorrador {
  const [guardado, setGuardado] = useState<string | null>(null);
  // Los archivos de lo recuperado se guardan otra vez con el primer cambio: llevan las claves
  // nuevas de los tripulantes (restaurar), y datos y archivos tienen que coincidir.
  const archivosGuardados = useRef<ArchivosBorrador | null>(null);
  const hayGuardado = useRef(yaGuardado);
  const primera = useRef(true);
  const pendiente = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!clave) return;
    // Lo que se ve al abrir (vacío o recuperado) ya está como está guardado.
    if (primera.current) {
      primera.current = false;
      return;
    }
    const guardar = () => {
      if (pendiente.current !== guardar) return; // ya se guardó o se descartó
      pendiente.current = null;
      if (!tieneContenido(datos, archivos)) {
        if (hayGuardado.current) {
          hayGuardado.current = false;
          archivosGuardados.current = null;
          void borrarBorrador(clave);
          setGuardado(null);
        }
        return;
      }
      const ahora = Date.now();
      hayGuardado.current = true;
      const anteriores = archivosGuardados.current;
      const cambiaron = anteriores?.nuevos !== archivos.nuevos || anteriores?.adicionales !== archivos.adicionales;
      if (cambiaron) archivosGuardados.current = archivos;
      void guardarBorrador(clave, datos, cambiaron ? archivos : null, ahora).then((ok) => {
        if (ok) setGuardado(cuandoSeGuardo(ahora, new Date(ahora)));
        // Si no se pudo, los archivos se intentan otra vez con el próximo guardado.
        else if (cambiaron && archivosGuardados.current === archivos) archivosGuardados.current = null;
      });
    };
    pendiente.current = guardar;
    const espera = setTimeout(guardar, ESPERA_GUARDADO_MS);
    return () => clearTimeout(espera);
  }, [clave, datos, archivos]);

  // Al desmontarse (se salió de la página), lo pendiente se guarda ya.
  useEffect(() => () => pendiente.current?.(), []);

  const descartar = useCallback(async () => {
    pendiente.current = null;
    hayGuardado.current = false;
    archivosGuardados.current = null;
    setGuardado(null);
    if (clave) await borrarBorrador(clave);
  }, [clave]);

  return { guardado, descartar };
}
