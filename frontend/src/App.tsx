import { useEffect, useRef, useState, useCallback, Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAutenticacion } from "./hooks/useAutenticacion";
import { usePermisos } from "./hooks/usePermisos";
import { RUTA_CAMBIAR_CONTRASENA, vencimientoDelToken } from "./api/client";
import { CapturadorErrores } from "./components/CapturadorErrores";
import { CargandoRuta } from "./components/EstadoCarga";
import { ModalExpiracionSesion } from "./components/ModalExpiracionSesion";
import { ProveedorNotificaciones } from "./components/Notificaciones";
import { ProveedorConfirmacion } from "./components/ModalConfirmacion";
import { ProveedorTema } from "./context/ContextoTema";
import { ProveedorAutenticacion } from "./context/ProveedorAutenticacion";
import { ProveedorPendientes } from "./context/ProveedorPendientes";
import { ProveedorPermisos } from "./context/ProveedorPermisos";
import PaginaLogin                from "./modulos/autenticacion/PaginaLogin";
import PaginaCambiarContrasena    from "./modulos/autenticacion/PaginaCambiarContrasena";
import PaginaPanel                from "./modulos/solicitudes/PaginaPanel";
import PaginaVerificacion         from "./modulos/solicitudes/PaginaVerificacion";
import PaginaNoEncontrada         from "./modulos/general/PaginaNoEncontrada";
import {
  AVISO_INACTIVIDAD_MS as AVISO_MS,
  LOGOUT_INACTIVIDAD_MS as LOGOUT_MS,
  ANOTAR_ACTIVIDAD_MS,
  MARGEN_RENOVACION_MS,
  REVISION_RENOVACION_MS,
} from "./constants/sesion";
import { CLAVE_ACTIVIDAD, anotarActividad, leerActividad } from "./utils/actividad";
import "./styles/globals.css";

// El login, las bandejas y las páginas chicas van en el paquete inicial. La
// verificación del QR la abre el público en el teléfono: sin un archivo más
// que pedir. El formulario y el expediente, los más pesados (~40 KB cada uno),
// se cargan al entrar, para que el login no espere lo que todavía no usa (por
// la VPN, el paquete inicial pesaba 440 KB). Si falta un archivo tras un
// despliegue, main.tsx recarga la página (vite:preloadError).
const PaginaSolicitud         = lazy(() => import("./modulos/solicitudes/PaginaSolicitud"));
const PaginaDetalleSolicitud  = lazy(() => import("./modulos/solicitudes/PaginaDetalleSolicitud"));
// Solo admin (y UCVMM, las estadísticas) visita estas.
const PaginaUsuarios        = lazy(() => import("./modulos/administracion/PaginaUsuarios"));
const PaginaRoles           = lazy(() => import("./modulos/administracion/PaginaRoles"));
const PaginaEstadisticas    = lazy(() => import("./modulos/administracion/PaginaEstadisticas"));
const PaginaTramites        = lazy(() => import("./modulos/administracion/PaginaTramites"));
const PaginaCatalogos       = lazy(() => import("./modulos/administracion/PaginaCatalogos"));
const PaginaBitacora        = lazy(() => import("./modulos/administracion/PaginaBitacora"));

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
        : esAdmin || tiene("T-PROCESAR-PACIFICO") || tiene("T-SUPERVISAR-SECTOR") || tiene("T-SUPERVISAR-TODO")
          ? <Suspense fallback={<CargandoRuta />}>{children}</Suspense>
          : <Navigate to="/dashboard" replace />}
    </RutaPrivada>
  );
}

/** Cierre de sesión por inactividad (con aviso y cuenta regresiva) y renovación
 *  del token mientras el usuario trabaja. Solo existe con la sesión abierta: al
 *  cerrarse (también desde otra pestaña) se desmonta, y no queda un aviso de
 *  la sesión anterior esperando a la siguiente. */
function GestorSesion({ children }: { children: React.ReactNode }) {
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

export default function App() {
  return (
    <CapturadorErrores>
      <ProveedorTema>
        <ProveedorNotificaciones>
          <ProveedorConfirmacion>
            <ProveedorAutenticacion>
              <ProveedorPermisos>
                <BrowserRouter>
                  <ProveedorPendientes>
                    <GestorSesion>
                      <Suspense fallback={<CargandoRuta />}>
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
                          <Route path="/"                  element={<Navigate to="/dashboard" replace />} />
                          {/* Antes cualquier dirección desconocida llevaba en silencio a las bandejas. */}
                          <Route path="*"                  element={<PaginaNoEncontrada />} />
                        </Routes>
                      </Suspense>
                    </GestorSesion>
                  </ProveedorPendientes>
                </BrowserRouter>
              </ProveedorPermisos>
            </ProveedorAutenticacion>
          </ProveedorConfirmacion>
        </ProveedorNotificaciones>
      </ProveedorTema>
    </CapturadorErrores>
  );
}
