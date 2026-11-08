import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";

// Tras un despliegue, las páginas que se cargan aparte cambian de nombre: quien
// tenía ARGO NAVIS abierto pedía un archivo que ya no existe y veía la pantalla
// de error. Se recarga para tomar la versión nueva, como mucho una vez por
// minuto (si el servidor de verdad falla, no queda recargando sin fin).
const CLAVE_RECARGA = "recarga-por-version";
window.addEventListener("vite:preloadError", (evento) => {
  try {
    const ultima = Number(sessionStorage.getItem(CLAVE_RECARGA)) || 0;
    if (Date.now() - ultima < 60_000) return;   // ya se intentó: que lo muestre CapturadorErrores
    sessionStorage.setItem(CLAVE_RECARGA, String(Date.now()));
  } catch {
    // Sin almacenamiento: se recarga igual (no hay cómo recordar el intento).
  }
  evento.preventDefault();
  window.location.reload();
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
