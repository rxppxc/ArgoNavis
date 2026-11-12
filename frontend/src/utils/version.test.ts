import { describe, expect, it } from "vitest";
import { esVersionNueva, huellaDeHtml, huellaDeRutas } from "./version";

/** Un index.html como el que arma Vite al compilar. */
const indice = (js: string, css: string) => `<!doctype html>
<html lang="es">
  <head>
    <link rel="icon" href="/favicon.svg" />
    <script src="/tema-inicial.js"></script>
    <script type="module" crossorigin src="/assets/index-${js}.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-${css}.css">
  </head>
  <body><div id="root"></div></body>
</html>`;

describe("la versión desplegada", () => {
  it("la huella son los archivos de /assets/, en orden y sin repetir", () => {
    expect(huellaDeHtml(indice("BlTrVMA6", "fhUtI9Ry"))).toBe("/assets/index-BlTrVMA6.js /assets/index-fhUtI9Ry.css");
    expect(huellaDeRutas(["/assets/b.js", "/tema-inicial.js", "/assets/a.css", "/assets/b.js"]))
      .toBe("/assets/a.css /assets/b.js");
  });

  it("la página cargada y el index.html dan la misma huella", () => {
    // Lo que huellaDelDocumento lee de los atributos de la página cargada.
    const atributos = ["/favicon.svg", "/tema-inicial.js", "/assets/index-BlTrVMA6.js", "/assets/index-fhUtI9Ry.css"];
    expect(huellaDeRutas(atributos)).toBe(huellaDeHtml(indice("BlTrVMA6", "fhUtI9Ry")));
  });

  it("cambia el código o solo los estilos: versión nueva", () => {
    const cargada = huellaDeHtml(indice("BlTrVMA6", "fhUtI9Ry"));
    expect(esVersionNueva(cargada, huellaDeHtml(indice("BlTrVMA6", "fhUtI9Ry")))).toBe(false);
    expect(esVersionNueva(cargada, huellaDeHtml(indice("Xy12_-ab", "fhUtI9Ry")))).toBe(true);
    expect(esVersionNueva(cargada, huellaDeHtml(indice("BlTrVMA6", "Zz99Qq00")))).toBe(true);
  });

  it("sin huella no avisa: desarrollo, o una respuesta que no es el index.html", () => {
    const desarrollo = huellaDeHtml(`<script type="module" src="/src/main.tsx"></script>`);
    expect(desarrollo).toBe("");
    expect(esVersionNueva(desarrollo, huellaDeHtml(indice("a", "b")))).toBe(false);
    expect(esVersionNueva(huellaDeHtml(indice("a", "b")), huellaDeHtml("<html>502 Bad Gateway</html>"))).toBe(false);
  });
});
