import { describe, expect, it } from "vitest";
import { leerEspejo, type Caso } from "../pruebas/espejo";
import { problemaContrasena, requisitosContrasena } from "./contrasena";

interface CasoContrasena extends Caso {
  clave: string;
  usuario: string | null;
  problema: string | null;
}

describe("problemaContrasena (espejo de problema_de_contrasena)", () => {
  it.each(leerEspejo<CasoContrasena[]>("contrasenas.json"))("$caso", ({ clave, usuario, problema }) => {
    expect(problemaContrasena(clave, usuario ?? undefined)).toBe(problema);
  });
});

describe("requisitosContrasena", () => {
  const cumple = (clave: string) => requisitosContrasena(clave).map((r) => r.cumple);

  it("marca cada requisito bajo el campo", () => {
    expect(cumple("")).toEqual([false, false, false, false, false]);
    expect(cumple("puerto2026balboa")).toEqual([true, false, true, true, false]);
    expect(cumple("Puerto-2026-Balboa")).toEqual([true, true, true, true, true]);
  });
});
