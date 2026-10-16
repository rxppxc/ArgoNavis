import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// El target del proxy se resuelve por variable de entorno (VITE_PROXY_TARGET).
// Si no está definida, se usa localhost:8000 — útil para desarrollo local.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Solo este equipo: el servidor de desarrollo no tiene las protecciones de
      // producción. Para probar desde otro equipo o el celular: VITE_HOST=0.0.0.0.
      host: env.VITE_HOST || "localhost",
      proxy: {
        "/api": { target: proxyTarget, changeOrigin: true },
      },
    },
  };
});
