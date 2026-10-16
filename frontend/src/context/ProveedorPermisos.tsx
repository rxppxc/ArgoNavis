import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiAutenticacion } from "../api/auth";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { ContextoPermisos, type ValorPermisos } from "../hooks/usePermisos";

interface Cargados {
  usuarioId:   number | null;
  codigos:     string[];
  /** Ya respondió el servidor (o falló y se quedó con la caché). */
  confirmados: boolean;
}

function leerCache(): string[] {
  try { return JSON.parse(localStorage.getItem("permisos") ?? "[]"); }
  catch { return []; }
}

/** Carga los permisos del usuario una vez por sesión (y al cambiar de
 *  usuario). Mientras llegan, usa los cacheados en localStorage para no
 *  parpadear el menú al recargar la página. Recién iniciada la sesión la caché
 *  está vacía (iniciarSesion la borra): ahí `cargando` sigue en true hasta que
 *  responda el servidor, para que nadie decida con una lista vacía. */
export function ProveedorPermisos({ children }: { children: ReactNode }) {
  const { usuario } = useAutenticacion();
  const usuarioId = usuario?.id ?? null;
  const esAdmin = usuario?.rol_personalizado?.nombre === "Administrador";
  // El SysAdmin no tiene permisos T-*: lo que ve depende solo del nombre del rol.
  const esSysAdmin = usuario?.rol_personalizado?.nombre === "SysAdmin";

  const [cargados, setCargados] = useState<Cargados>(() => ({ usuarioId, codigos: leerCache(), confirmados: false }));

  useEffect(() => {
    if (usuarioId === null) return;
    let cancelado = false;
    apiAutenticacion.misPermisos()
      .then((lista) => {
        if (cancelado) return;
        localStorage.setItem("permisos", JSON.stringify(lista));
        setCargados({ usuarioId, codigos: lista, confirmados: true });
      })
      .catch(() => {
        // Se mantienen los cacheados (la caché es de este usuario: se borra al iniciar sesión).
        if (!cancelado) setCargados({ usuarioId, codigos: leerCache(), confirmados: true });
      });
    return () => { cancelado = true; };
  }, [usuarioId]);

  // Los códigos son del usuario actual; los de otro usuario no se usan.
  const vigentes = usuarioId !== null && cargados.usuarioId === usuarioId;
  const codigos = useMemo(() => (vigentes ? cargados.codigos : []), [vigentes, cargados.codigos]);
  const listos = esAdmin || esSysAdmin || (vigentes && (cargados.confirmados || cargados.codigos.length > 0));

  const tiene = useCallback((codigo: string) => esAdmin || codigos.includes(codigo), [codigos, esAdmin]);
  const tieneAlguno = useCallback(
    (...lista: string[]) => esAdmin || lista.some((c) => codigos.includes(c)),
    [codigos, esAdmin],
  );

  const valor = useMemo<ValorPermisos>(() => ({
    codigos, cargando: usuarioId !== null && !listos, esAdmin, esSysAdmin, tiene, tieneAlguno,
  }), [codigos, usuarioId, listos, esAdmin, esSysAdmin, tiene, tieneAlguno]);

  return <ContextoPermisos.Provider value={valor}>{children}</ContextoPermisos.Provider>;
}
