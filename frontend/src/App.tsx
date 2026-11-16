import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { RUTA_CAMBIAR_CONTRASENA } from "./api/client";
import { CapturadorErrores } from "./components/CapturadorErrores";
import { CargandoRuta } from "./components/EstadoCarga";
import { RutaHistorico, RutaPrivada, RutaRol, RutaSolicitudes, RutaStats } from "./components/RutasProtegidas";
import { GestorSesion } from "./components/VigilanteSesion";
import { VigilanteVersion } from "./components/VigilanteVersion";
import { ProveedorNotificaciones } from "./components/Notificaciones";
import { ProveedorConfirmacion } from "./components/ModalConfirmacion";
import { ProveedorTema } from "./context/ContextoTema";
import { ProveedorAutenticacion } from "./context/ProveedorAutenticacion";
import { ProveedorPendientes } from "./context/ProveedorPendientes";
import { ProveedorPermisos } from "./context/ProveedorPermisos";
import PaginaLogin                from "./modulos/autenticacion/PaginaLogin";
import PaginaCambiarContrasena    from "./modulos/autenticacion/PaginaCambiarContrasena";
import PaginaPanel                from "./modulos/solicitudes/bandejas/PaginaPanel";
import PaginaVerificacion         from "./modulos/solicitudes/verificacion/PaginaVerificacion";
import PaginaNoEncontrada         from "./modulos/general/PaginaNoEncontrada";
// Letras de la identidad «pase oficial» (elegida por el usuario el 2026-11-11):
// van en el paquete compilado y las sirve el propio servidor, como pide la CSP
// (font-src 'self'): nada de CDN. Archivo con el eje de ancho (títulos extendidos).
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource-variable/public-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./styles/globals.css";

// El login, las bandejas y las páginas chicas van en el paquete inicial. La
// verificación del QR la abre el público en el teléfono: sin un archivo más
// que pedir. El formulario y el expediente, los más pesados (~40 KB cada uno),
// se cargan al entrar, para que el login no espere lo que todavía no usa (por
// la VPN, el paquete inicial pesaba 440 KB). Si falta un archivo tras un
// despliegue, main.tsx recarga la página (vite:preloadError).
const PaginaSolicitud         = lazy(() => import("./modulos/solicitudes/formulario/PaginaSolicitud"));
const PaginaDetalleSolicitud  = lazy(() => import("./modulos/solicitudes/expediente/PaginaDetalleSolicitud"));
const PaginaConsultaHistorica = lazy(() => import("./modulos/solicitudes/historico/PaginaConsultaHistorica"));
// Solo admin (y UCVMM, las estadísticas) visita estas.
const PaginaUsuarios        = lazy(() => import("./modulos/administracion/PaginaUsuarios"));
const PaginaRoles           = lazy(() => import("./modulos/administracion/PaginaRoles"));
const PaginaEstadisticas    = lazy(() => import("./modulos/administracion/PaginaEstadisticas"));
const PaginaTramites        = lazy(() => import("./modulos/administracion/PaginaTramites"));
const PaginaCatalogos       = lazy(() => import("./modulos/administracion/PaginaCatalogos"));
const PaginaBitacora        = lazy(() => import("./modulos/administracion/PaginaBitacora"));

export default function App() {
  return (
    <CapturadorErrores>
      <ProveedorTema>
        <ProveedorNotificaciones>
          {/* Una versión nueva desplegada con la página abierta: avisa y ofrece recargar. */}
          <VigilanteVersion />
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
                          <Route path="/historico"         element={<RutaHistorico><PaginaConsultaHistorica /></RutaHistorico>} />
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
