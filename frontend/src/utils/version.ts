/**
 * ¿Se desplegó una versión nueva mientras la página estaba abierta? (2026-11-11)
 *
 * Cada compilación cambia el nombre de los archivos de /assets/ (llevan un hash del
 * contenido: index-BlTrVMA6.js). La «huella» de una versión es la lista de los que pide su
 * index.html: se compara la del index.html de hoy con la de la página que se cargó. Así no
 * hace falta un número de versión que alguien tenga que acordarse de subir.
 *
 * En desarrollo, Vite sirve el código sin empaquetar (/src/main.tsx): la huella queda vacía
 * y no se revisa nada.
 */

/** Los archivos de /assets/ que pide un HTML (scripts, hojas de estilo y precargas). */
const ARCHIVO_DE_ASSETS = /\b(?:src|href)=["'](\/assets\/[^"']+)["']/g;

/** La huella de una lista de rutas: las de /assets/, sin repetir y en orden. */
export function huellaDeRutas(rutas: Iterable<string>): string {
  return [...new Set([...rutas].filter((r) => r.startsWith("/assets/")))].sort().join(" ");
}

/** La huella del index.html que sirve hoy el servidor. */
export function huellaDeHtml(html: string): string {
  return huellaDeRutas([...html.matchAll(ARCHIVO_DE_ASSETS)].map((m) => m[1]));
}

/** La huella de la página cargada. Se toma al arrancar, antes de que Vite agregue las
 *  hojas y precargas de las páginas que se cargan aparte (que el index.html no tiene). */
export function huellaDelDocumento(doc: Document): string {
  const elementos = doc.querySelectorAll("script[src], link[href]");
  return huellaDeRutas([...elementos].map((e) => e.getAttribute("src") ?? e.getAttribute("href") ?? ""));
}

/** Hay versión nueva si las dos huellas existen y son distintas. Sin huella (desarrollo, o
 *  una respuesta que no es el index.html, como la página de error de un proxy), no. */
export function esVersionNueva(cargada: string, servida: string): boolean {
  return cargada !== "" && servida !== "" && servida !== cargada;
}
