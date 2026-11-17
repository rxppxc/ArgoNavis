/**
 * Contraste de los tokens de globals.css, en los dos temas (rediseño visual del 2026-11-17).
 * Antes había que recalcularlo a mano cada vez que cambiaba un color: ahora, si un token
 * baja del mínimo, esta prueba falla. Texto: 4.5:1 (WCAG AA); borde de campos: 3:1.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// Con fs y no con `?raw`: Vitest no entrega el texto de los .css importados.
const css = readFileSync(new URL("./globals.css", import.meta.url), "utf-8").replace(/\r\n/g, "\n");

type Tokens = Record<string, string>;

function bloque(selector: string): Tokens {
  const inicio = css.indexOf(`${selector} {`);
  if (inicio < 0) throw new Error(`no está el bloque ${selector}`);
  const cuerpo = css.slice(inicio, css.indexOf("\n}", inicio));
  const tokens: Tokens = {};
  for (const [, nombre, valor] of cuerpo.matchAll(/--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\b/g)) tokens[nombre] = valor;
  return tokens;
}

const OSCURO = bloque(":root");
// El claro redefine solo lo que cambia: lo demás lo hereda del oscuro.
const CLARO = { ...OSCURO, ...bloque('[data-theme="light"]') };

function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

const ESTADOS = ["revision", "correccion", "aprobada", "finalizada", "denegada", "expirada"];

describe.each([["oscuro", OSCURO], ["claro", CLARO]] as const)("tema %s", (_, t) => {
  function exigir(texto: string, fondo: string, minimo: number) {
    expect(t[texto], `falta --${texto}`).toBeDefined();
    expect(t[fondo], `falta --${fondo}`).toBeDefined();
    const valor = contraste(t[texto], t[fondo]);
    expect(valor, `--${texto} sobre --${fondo}: ${valor.toFixed(2)}:1`).toBeGreaterThanOrEqual(minimo);
  }

  it.each(["bg", "card", "surface-2"])("los textos se leen sobre --%s", (fondo) => {
    for (const texto of ["text", "text-2", "muted"]) exigir(texto, fondo, 4.5);
  });

  it("el borde de los campos se ve sobre la tarjeta", () => exigir("input-border", "card", 3));

  it("los títulos de sección (barra marino) se leen, también su número sobre la franja", () => {
    exigir("seccion-texto", "seccion-fondo", 4.5);
    exigir("seccion-fondo", "franja", 4.5);
  });

  it("las notas (azules) dejan leer el texto; lo desactivado deja leer su rótulo", () => {
    for (const texto of ["text", "text-2"]) exigir(texto, "nota-fondo", 4.5);
    exigir("muted", "desactivado-2", 4.5);
  });

  it.each(ESTADOS)("el tinte de «%s» deja leer el texto y su color se distingue de la tarjeta", (estado) => {
    exigir("text", `estado-${estado}-tinte`, 4.5);
    exigir(`estado-${estado}`, "card", 3);
  });
});
