import { useEffect, useRef, useState, useCallback, Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAutenticacion } from "./hooks/useAutenticacion";
import { usePermisos } from "./hooks/usePermisos";
import { CapturadorErrores } from "./components/CapturadorErrores";
import { ModalExpiracionSesion } from "./components/ModalExpiracionSesion";
import { ProveedorNotificaciones } from "./components/Notificaciones";
import { ProveedorConfirmacion } from "./components/ModalConfirmacion";
import { ProveedorTema } from "./context/ContextoTema";
import PaginaLogin                from "./modulos/autenticacion/PaginaLogin";
import PaginaPanel                from "./modulos/transferencias/PaginaPanel";
import PaginaSubida               from "./modulos/transferencias/PaginaSubida";
import PaginaTransferencia        from "./modulos/transferencias/PaginaTransferencia";
import {
  AVISO_INACTIVIDAD_MS as AVISO_MS,
  LOGOUT_INACTIVIDAD_MS as LOGOUT_MS,
  CUENTA_REGRESIVA_SEG as CUENTA_SEG,
} from "./constants/sesion";
import "./styles/globals.css";

// Solo admin visita estas — se cargan en un chunk aparte para no pesarle
// el bundle inicial a Naviera/Sector Pacífico, que nunca las ven.
const PaginaUsuarios        = lazy(() => import("./modulos/administracion/PaginaUsuarios"));
const PaginaRoles           = lazy(() => import("./modulos/administracion/PaginaRoles"));
const PaginaEstadisticas    = lazy(() => import("./modulos/administracion/PaginaEstadisticas"));

function CargandoRuta() {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--ink)",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        border: "3px solid rgba(245,200,0,.25)", borderTopColor: "var(--y)",
        animation: "girar .7s linear infinite",
      }} />
      <style>{"@keyframes girar { to { transform: rotate(360deg); } }"}</style>
    </div>
  );
}

function RutaPrivada({ children }: { children: React.ReactNode }) {
  const { estaAutenticado } = useAutenticacion();
  return estaAutenticado ? <>{children}</> : <Navigate to="/login" replace />;
}

function RutaAdmin({ children }: { children: React.ReactNode }) {
  const { estaAutenticado } = useAutenticacion();
  const { esAdmin } = usePermisos();
  if (!estaAutenticado) return <Navigate to="/login" replace />;
  if (!esAdmin) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function RutaStats({ children }: { children: React.ReactNode }) {
  const { estaAutenticado } = useAutenticacion();
  const { tiene, esAdmin } = usePermisos();
  if (!estaAutenticado) return <Navigate to="/login" replace />;
  if (!esAdmin && !tiene("T-PROCESAR-PACIFICO")) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function GestorSesion({ children }: { children: React.ReactNode }) {
  const { estaAutenticado, cerrarSesion, extenderSesion } = useAutenticacion();
  const [mostrarModal, setMostrarModal] = useState(false);
  const [segundos, setSegundos] = useState(CUENTA_SEG);

  const timers = useRef<{
    aviso:  ReturnType<typeof setTimeout>  | null;
    logout: ReturnType<typeof setTimeout>  | null;
    cuenta: ReturnType<typeof setInterval> | null;
  }>({ aviso: null, logout: null, cuenta: null });

  const mostrandoRef = useRef(false);

  const limpiar = useCallback(() => {
    const t = timers.current;
    if (t.aviso)  { clearTimeout(t.aviso);   t.aviso  = null; }
    if (t.logout) { clearTimeout(t.logout);  t.logout = null; }
    if (t.cuenta) { clearInterval(t.cuenta); t.cuenta = null; }
  }, []);

  const iniciar = useCallback(() => {
    limpiar();
    mostrandoRef.current = false;
    setMostrarModal(false);

    timers.current.aviso = setTimeout(() => {
      mostrandoRef.current = true;
      setMostrarModal(true);
      setSegundos(CUENTA_SEG);
      timers.current.cuenta = setInterval(() => {
        setSegundos(prev => {
          if (prev <= 1) {
            limpiar();
            cerrarSesion(true, true);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, AVISO_MS);

    timers.current.logout = setTimeout(() => {
      limpiar();
      cerrarSesion(true, true);
    }, LOGOUT_MS);
  }, [cerrarSesion, limpiar]);

  const enActividad = useCallback(() => {
    if (!mostrandoRef.current) iniciar();
  }, [iniciar]);

  useEffect(() => {
    if (!estaAutenticado) { limpiar(); return; }
    iniciar();
    const eventos = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    eventos.forEach(ev => window.addEventListener(ev, enActividad, { passive: true }));
    return () => {
      limpiar();
      eventos.forEach(ev => window.removeEventListener(ev, enActividad));
    };
  }, [estaAutenticado, iniciar, limpiar, enActividad]);

  const alContinuar = useCallback(async () => {
    try { await extenderSesion(); } catch { /* el interceptor cerrará sesión si el token expiró */ }
    iniciar();
  }, [extenderSesion, iniciar]);

  const alSalir = useCallback(() => {
    limpiar();
    cerrarSesion(true, false);
  }, [cerrarSesion, limpiar]);

  return (
    <>
      {children}
      {mostrarModal && (
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
            <BrowserRouter>
              <GestorSesion>
              <Routes>
              <Route path="/login"      element={<PaginaLogin />} />
              <Route path="/t/:token"   element={<PaginaTransferencia />} />
              <Route path="/dashboard"  element={<RutaPrivada><PaginaPanel /></RutaPrivada>} />
              <Route path="/new"        element={<RutaPrivada><PaginaSubida /></RutaPrivada>} />
              <Route path="/admin"        element={<RutaAdmin><Suspense fallback={<CargandoRuta />}><PaginaUsuarios /></Suspense></RutaAdmin>} />
              <Route path="/admin/roles"  element={<RutaAdmin><Suspense fallback={<CargandoRuta />}><PaginaRoles /></Suspense></RutaAdmin>} />
              <Route path="/admin/stats"  element={<RutaStats><Suspense fallback={<CargandoRuta />}><PaginaEstadisticas /></Suspense></RutaStats>} />
              <Route path="*"           element={<Navigate to="/dashboard" replace />} />
              </Routes>
              </GestorSesion>
            </BrowserRouter>
          </ProveedorConfirmacion>
        </ProveedorNotificaciones>
      </ProveedorTema>
    </CapturadorErrores>
  );
}
