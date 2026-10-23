import { defineConfig } from "@playwright/test";

// Recorrido completo en el navegador (npm run test:e2e) contra un backend de
// prueba con su propia BD temporal (backend/tests/servidor_e2e.py). Usa puertos
// propios para no chocar con los servidores de desarrollo (8000 y 5173).
const PUERTO_API = 8001;
const PUERTO_WEB = 5174;
export const PYTHON = process.platform === "win32" ? "venv\\Scripts\\python" : "venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  globalTeardown: "./e2e/limpiar.ts",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PUERTO_WEB}`,
    locale: "es-PA",
    timezoneId: "America/Panama",
    // El Chrome instalado en el equipo. En un servidor sin Chrome:
    // `npx playwright install chromium` y PLAYWRIGHT_CHROMIUM=1.
    channel: process.env.PLAYWRIGHT_CHROMIUM ? undefined : "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `${PYTHON} tests/servidor_e2e.py`,
      cwd: "../backend",
      url: `http://127.0.0.1:${PUERTO_API}/api/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { E2E_PUERTO_API: String(PUERTO_API), E2E_URL_WEB: `http://localhost:${PUERTO_WEB}` },
    },
    {
      command: `npx vite --port ${PUERTO_WEB} --strictPort`,
      url: `http://localhost:${PUERTO_WEB}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${PUERTO_API}` },
    },
  ],
});
