import { defineConfig } from "vitest/config";

// Pruebas unitarias de las reglas del frontend (npm test). El recorrido
// completo en el navegador va aparte, con Playwright (npm run test:e2e).
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
