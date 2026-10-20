import { useEffect, useRef, useState, useCallback, Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAutenticacion } from "./hooks/useAutenticacion";
import { usePermisos } from "./hooks/usePermisos";
import { RUTA_CAMBIAR_CONTRASENA, vencimientoDelToken } from "./api/client";
import { CapturadorErrores } from "./components/CapturadorErrores";
import { ModalExpiracionSesion } from "./components/ModalExpiracionSesion";
import { ProveedorNotificaciones } from "./components/Notificaciones";
import { ProveedorConfirmacion } from "./components/ModalConfirmacion";
import { ProveedorTema } from "./context/ContextoTema";
import { ProveedorAutenticacion } from "./context/ProveedorAutenticacion";
import { ProveedorPermisos } from "./context/ProveedorPermisos";
import PaginaLogin                from "./modulos/autenticacion/PaginaLogin";
import PaginaCambiarContrasena    from "./modulos/autenticacion/PaginaCambiarContrasena";
import PaginaPanel                from "./modulos/solicitudes/PaginaPanel";
import PaginaSolicitud            from "./modulos/solicitudes/PaginaSolicitud";
import PaginaDetalleSolicitud     from "./modulos/solicitudes/PaginaDetalleSolicitud";
import PaginaVerificacion         from "./modulos/solicitudes/PaginaVerificacion";
import {
  AVISO_INACTIVIDAD_MS as AVISO_MS,
  LOGOUT_INACTIVIDAD_MS as LOGOUT_MS,
  CUENTA_REGRESIVA_SEG as CUENTA_SEG,
  MARGEN_RENOVACION_MS,
  REVISION_RENOVACION_MS,
} from "./constants/sesion";
import "./styles/globals.css";

// Solo admin (y UCVMM, las estadísticas) visita estas — se cargan en un chunk
// aparte para no pesarle el bundle inicial a quien nunca las ve.
const PaginaUsuarios        = lazy(() => import("./modulos/administracion/PaginaUsuarios"));
const PaginaRoles           = lazy(() => import("./modulos/administracion/PaginaRoles"));
const PaginaEstadisticas    = lazy(() => import("./modulos/administracion/PaginaEstadisticas"));
const PaginaTramites        = lazy(() => import("./modulos/administracion/PaginaTramites"));
const PaginaCatalogos       = lazy(() => import("./modulos/administracion/PaginaCatalogos"));
const PaginaBitacora        = lazy(() => import("./modulos/administracion/PaginaBitacora"));

function CargandoRuta() {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--bg)",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        border: "3px solid var(--y-border)", borderTopColor: "var(--y)",
        animation: "girar .7s linear infinite",
      }} />
      <style>{"@keyframes girar { to { transform: rotate(360deg); } }"}</style>
    </div>
  );
}

/** Con sesión. Una cuenta con cambio de contraseña pendiente solo puede ir a cambiarla.
 *  Sin sesión, al login recordando la página pedida (p. ej. el enlace de un correo). */
function RutaPrivada({ children }: { children: React.ReactNode }) {
  const { usuario } = useAutenticacion();
  const { pathname, search } = useLocation();
  if (!usuario) return <Navigate to="/login" replace state={{ desde: pathname + search }} />;
  if (usuario.debe_cambiar_password && pathname !== RUTA_CAMBIAR_CONTRASENA) {
    return <Navigate to={RUTA_CAMBIAR_CONTRASENA} replace />;
  }
  return <>{children}</>;
}

/** Bandejas y expedientes. El SysAdmin no trabaja solicitudes: su inicio es Usuarios. */
function RutaSolicitudes({ children }: { children: React.ReactNode }) {
  const { esSysAdmin } = usePermisos();
  return <RutaPrivada>{esSysAdmin ? <Navigate to="/admin" replace /> : children}</RutaPrivada>;
}

type RolFijo = "admin" | "sysadmin";

/** Páginas de administración: solo para los roles indicados; el resto vuelve a su inicio. */
function RutaRol({ roles, children }: { roles: RolFijo[]; children: React.ReactNode }) {
  const { esAdmin, esSysAdmin } = usePermisos();
  const permitido = (esAdmin && roles.includes("admin")) || (esSysAdmin && roles.includes("sysadmin"));
  return (
    <RutaPrivada>
      {permitido ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense> : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}

function RutaStats({ children }: { children: React.ReactNode }) {
  const { tiene, esAdmin, cargando } = usePermisos();
  return (
    <RutaPrivada>
      {/* Recién iniciada la sesión los permisos aún no llegan: esperar en vez de rebotar. */}
      {cargando ? <CargandoRuta />
        : esAdmin || tiene("T-PROCESAR-PACIFICO")
          ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense>
          : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}

/** Cierre de sesión por inactividad (con aviso y cuenta regresiva) y renovación
 *  del token mientras el usuario trabaja. */
function GestorSesion({ children }: { children: React.ReactNode }) {
  const { estaAutenticado, cerrarSesion, extenderSesion } = useAutenticacion();
  // Hora a la que vence la sesión mientras se muestra el aviso (null = sin aviso).
  const [venceEn, setVenceEn] = useState<number | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());

  const timers = useRef<{
    aviso:  ReturnType<typeof setTimeout>  | null;
    logout: ReturnType<typeof setTimeout>  | null;
    reloj:  ReturnType<typeof setInterval> | null;
  }>({ aviso: null, logout: null, reloj: null });
  const mostrandoRef = useRef(false);

  const limpiar = useCallback(() => {
    const t = timers.current;
    if (t.aviso)  { clearTimeout(t.aviso);   t.aviso  = null; }
    if (t.logout) { clearTimeout(t.logout);  t.logout = null; }
    if (t.reloj)  { clearInterval(t.reloj);  t.reloj  = null; }
  }, []);

  /** Reprograma el aviso y el cierre desde ahora (solo timers: el estado
   *  visible cambia dentro de sus callbacks o de los manejadores). */
  const programar = useCallback(() => {
    limpiar();
    mostrandoRef.current = false;
    timers.current.aviso = setTimeout(() => {
      mostrandoRef.current = true;
      setAhora(Date.now());
      setVenceEn(Date.now() + CUENTA_SEG * 1000);
      timers.current.reloj = setInterval(() => setAhora(Date.now()), 1000);
    }, AVISO_MS);
    timers.current.logout = setTimeout(() => {
      limpiar();
      mostrandoRef.current = false;
      setVenceEn(null);
      cerrarSesion(true, true);
    }, LOGOUT_MS);
  }, [cerrarSesion, limpiar]);

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

  const enActividad = useCallback(() => {
    if (mostrandoRef.current) return;
    programar();
    renovarSiVence();
  }, [programar, renovarSiVence]);

  useEffect(() => {
    if (!estaAutenticado) { limpiar(); return; }
    programar();
    const eventos = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    eventos.forEach(ev => window.addEventListener(ev, enActividad, { passive: true }));
    return () => {
      limpiar();
      eventos.forEach(ev => window.removeEventListener(ev, enActividad));
    };
  }, [estaAutenticado, programar, limpiar, enActividad]);

  const alContinuar = useCallback(async () => {
    setVenceEn(null);
    try { await extenderSesion(); } catch { /* el interceptor cerrará sesión si el token expiró */ }
    programar();
  }, [extenderSesion, programar]);

  const alSalir = useCallback(() => {
    limpiar();
    mostrandoRef.current = false;
    setVenceEn(null);
    cerrarSesion(true, false);
  }, [cerrarSesion, limpiar]);

  const segundos = venceEn === null ? CUENTA_SEG : Math.max(0, Math.ceil((venceEn - ahora) / 1000));

  return (
    <>
      {children}
      {estaAutenticado && venceEn !== null && (
        <ModalExpiracionSesion
          segundos={segundos}
          onContinuar={alContinuar}
          onCerrarSesion={alSalir}
        />
      )}
    </>
  );
}

export default function App() {
  return (
    <CapturadorErrores>
      <ProveedorTema>
        <ProveedorNotificaciones>
          <ProveedorConfirmacion>
            <ProveedorAutenticacion>
              <ProveedorPermisos>
                <BrowserRouter>
                  <GestorSesion>
                    <Routes>
                      <Route path="/login"             element={<PaginaLogin />} />
                      <Route path="/verificar/:codigo" element={<PaginaVerificacion />} />
                      <Route path={RUTA_CAMBIAR_CONTRASENA} element={<RutaPrivada><PaginaCambiarContrasena /></RutaPrivada>} />
                      <Route path="/dashboard"         element={<RutaSolicitudes><PaginaPanel /></RutaSolicitudes>} />
                      <Route path="/new"               element={<RutaSolicitudes><PaginaSolicitud /></RutaSolicitudes>} />
                      <Route path="/solicitudes/:id"          element={<RutaSolicitudes><PaginaDetalleSolicitud /></RutaSolicitudes>} />
                      <Route path="/solicitudes/:id/corregir" element={<RutaSolicitudes><PaginaSolicitud /></RutaSolicitudes>} />
                      <Route path="/admin"             element={<RutaRol roles={["admin", "sysadmin"]}><PaginaUsuarios /></RutaRol>} />
                      <Route path="/admin/roles"       element={<RutaRol roles={["admin", "sysadmin"]}><PaginaRoles /></RutaRol>} />
                      <Route path="/admin/stats"       element={<RutaStats><PaginaEstadisticas /></RutaStats>} />
                      <Route path="/admin/tramites"    element={<RutaRol roles={["admin"]}><PaginaTramites /></RutaRol>} />
                      <Route path="/admin/catalogos"   element={<RutaRol roles={["admin"]}><PaginaCatalogos /></RutaRol>} />
                      <Route path="/admin/bitacora"    element={<RutaRol roles={["admin", "sysadmin"]}><PaginaBitacora /></RutaRol>} />
                      <Route path="*"                  element={<Navigate to="/dashboard" replace />} />
                    </Routes>
                  </GestorSesion>
                </BrowserRouter>
              </ProveedorPermisos>
            </ProveedorAutenticacion>
          </ProveedorConfirmacion>
        </ProveedorNotificaciones>
      </ProveedorTema>
    </CapturadorErrores>
  );
}
