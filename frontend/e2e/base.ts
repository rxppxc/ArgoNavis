/**
 * El `test` de Playwright con una vigilancia de la consola en cada recorrido:
 * un error de JavaScript sin atrapar, un console.error (también los avisos de
 * React, que en desarrollo salen así) o una respuesta 5xx del servidor hacen
 * fallar la prueba. Los 4xx no cuentan: varias pruebas los provocan a propósito
 * (un código de verificación falso, una ruta sin sesión...).
 *
 * Cubre todos los contextos: el de `page` y los que abren las pruebas con
 * `browser.newContext()` (una sesión por rol, en datos.ts).
 */
import { test as base, expect, type Browser, type BrowserContext } from "@playwright/test";

export { expect };

export const test = base.extend<{ vigilarConsola: void }>({
  // «usar» y no «use»: con ese nombre, la regla de hooks de React lo confunde con React.use.
  vigilarConsola: [async ({ browser, context }, usar) => {
    const problemas: string[] = [];
    const vigilar = (contexto: BrowserContext) => {
      contexto.on("weberror", (e) => problemas.push(`Error sin atrapar: ${e.error().message}`));
      contexto.on("console", (mensaje) => {
        if (mensaje.type() !== "error") return;
        const texto = mensaje.text();
        const estado = /status of (\d{3})/.exec(texto);
        if (estado && Number(estado[1]) < 500) return;
        problemas.push(`console.error (${mensaje.location().url}): ${texto}`);
      });
      contexto.on("response", (r) => { if (r.status() >= 500) problemas.push(`${r.status()} en ${r.url()}`); });
    };
    vigilar(context);
    const original = browser.newContext.bind(browser);
    const conVigilancia: Browser["newContext"] = async (opciones) => {
      const contexto = await original(opciones);
      vigilar(contexto);
      return contexto;
    };
    browser.newContext = conVigilancia;
    try {
      await usar();
    } finally {
      browser.newContext = original;
    }
    expect(problemas, "errores en la consola del navegador o del servidor").toEqual([]);
  }, { auto: true }],
});
