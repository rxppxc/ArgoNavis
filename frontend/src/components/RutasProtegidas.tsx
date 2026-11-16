/** Las guardias de las rutas (hasta el 2026-11-14, en App.tsx): con sesión, y con el
 *  rol o los permisos de cada página. El backend vuelve a exigir lo mismo en cada
 *  pedido: esto solo evita mostrar una página que respondería 403. */
import { Suspense } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { RUTA_CAMBIAR_CONTRASENA } from "../api/client";
import { useAutenticacion } from "../hooks/useAutenticacion";
import { PERMISOS_PERSONAL_SNM, usePermisos } from "../hooks/usePermisos";
import { CargandoRuta } from "./EstadoCarga";

/** Con sesión. Una cuenta con cambio de contraseña pendiente solo puede ir a cambiarla.
 *  Sin sesión, al login recordando la página pedida (p. ej. el enlace de un correo). */
export function RutaPrivada({ children }: { children: React.ReactNode }) {
  const { usuario, sesionCerrada } = useAutenticacion();
  const { pathname, search } = useLocation();
  // Recuerda la página solo si se llegó sin sesión (un enlace de un correo); si la sesión
  // se acaba de cerrar aquí, al volver a entrar se va al inicio.
  if (!usuario) return <Navigate to="/login" replace state={sesionCerrada ? undefined : { desde: pathname + search }} />;
  if (usuario.debe_cambiar_password && pathname !== RUTA_CAMBIAR_CONTRASENA) {
    return <Navigate to={RUTA_CAMBIAR_CONTRASENA} replace />;
  }
  return <>{children}</>;
}

/** Bandejas y expedientes. El SysAdmin no trabaja solicitudes: su inicio es Usuarios. */
export function RutaSolicitudes({ children }: { children: React.ReactNode }) {
  const { esSysAdmin } = usePermisos();
  return <RutaPrivada>{esSysAdmin ? <Navigate to="/admin" replace /> : children}</RutaPrivada>;
}

type RolFijo = "admin" | "sysadmin";

/** Páginas de administración: solo para los roles indicados; el resto vuelve a su inicio. */
export function RutaRol({ roles, children }: { roles: RolFijo[]; children: React.ReactNode }) {
  const { esAdmin, esSysAdmin } = usePermisos();
  const permitido = (esAdmin && roles.includes("admin")) || (esSysAdmin && roles.includes("sysadmin"));
  return (
    <RutaPrivada>
      {permitido ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense> : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}

export function RutaStats({ children }: { children: React.ReactNode }) {
  const { tiene, esAdmin, cargando } = usePermisos();
  return (
    <RutaPrivada>
      {/* Recién iniciada la sesión los permisos aún no llegan: esperar en vez de rebotar. */}
      {cargando ? <CargandoRuta />
        : esAdmin || tiene("T-PROCESAR-PACIFICO") || tiene("T-SUPERVISAR-SECTOR") || tiene("T-SUPERVISAR-TODO")
          ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense>
          : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}

/** La consulta histórica (2026-11-11): el personal del SNM que trabaja solicitudes. */
export function RutaPersonalSnm({ children }: { children: React.ReactNode }) {
  const { tieneAlguno, cargando } = usePermisos();
  return (
    <RutaPrivada>
      {cargando ? <CargandoRuta />
        : tieneAlguno(...PERMISOS_PERSONAL_SNM)
          ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense>
          : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}
