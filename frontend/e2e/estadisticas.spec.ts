/**
 * Estadísticas (2026-11-10): la escala de la serie sigue al periodo y se exporta
 * en Excel, PDF y CSV con la identidad del SNM (los arma el backend de pruebas).
 */
import { readFile } from "node:fs/promises";
import { expect, test } from "./base";
import { CUENTAS, entrar } from "./datos";

const FORMATOS = [
  { boton: "Excel", extension: "xlsx", empieza: "PK" },              // un .xlsx es un ZIP
  { boton: "PDF",   extension: "pdf",  empieza: "%PDF-" },
  { boton: "CSV",   extension: "csv",  empieza: "﻿ARGO NAVIS" }, // con BOM, para Excel
] as const;

test("estadísticas: la escala sigue al periodo y se exporta en los tres formatos", async ({ browser }) => {
  await test.step("UCVMM no las ve (2026-11-18): ni en el menú ni por la dirección", async () => {
    const revisor = await entrar(browser, CUENTAS.ucvmm);
    await revisor.goto("/dashboard");
    await revisor.getByRole("button", { name: "Menú" }).click();
    await expect(revisor.getByRole("link", { name: "Inicio", exact: true })).toBeVisible();   // el menú abrió
    await expect(revisor.getByRole("link", { name: "Estadísticas" })).toHaveCount(0);
    await revisor.keyboard.press("Escape");
    await revisor.goto("/admin/stats");
    await expect(revisor).toHaveURL(/\/dashboard/);
  });

  // El supervisor de sector del Pacífico (desde el 2026-11-18; antes, UCVMM).
  const supervisor = await entrar(browser, CUENTAS.supsector);
  await supervisor.goto("/admin/stats");
  await expect(supervisor.getByRole("heading", { name: "Estadísticas", level: 1 })).toBeVisible();
  // Es del Sector Pacífico: ve las de su sector, y no el uso del sistema (2026-11-10).
  await expect(supervisor.getByText("Sector Pacífico", { exact: true })).toBeVisible();
  await expect(supervisor.getByRole("heading", { name: "Uso del sistema" })).toHaveCount(0);

  await test.step("«Mes pasado» se ve por día y «Este año», por mes", async () => {
    await supervisor.getByRole("button", { name: "Mes pasado" }).click();
    await expect(supervisor.getByRole("heading", { name: "Solicitudes por día" })).toBeVisible();
    await expect(supervisor.getByRole("button", { name: "Día", exact: true })).toHaveAttribute("aria-pressed", "true");
    await supervisor.getByRole("button", { name: "Este año" }).click();
    await expect(supervisor.getByRole("heading", { name: "Solicitudes por mes" })).toBeVisible();
  });

  await test.step("Excel, PDF y CSV del periodo elegido", async () => {
    const grupo = supervisor.getByRole("group", { name: "Exportar las estadísticas del periodo" });
    for (const { boton, extension, empieza } of FORMATOS) {
      const descarga = supervisor.waitForEvent("download");
      await grupo.getByRole("button", { name: boton, exact: true }).click();
      const archivo = await descarga;
      const nombre = archivo.suggestedFilename();
      expect(nombre).toMatch(
        new RegExp(`^Estadisticas-autorizaciones-sector-pacifico-\\d{4}-01-01_\\d{4}-\\d{2}-\\d{2}\\.${extension}$`));
      const contenido = await readFile(await archivo.path());
      expect(contenido.subarray(0, Buffer.byteLength(empieza)).toString(), nombre).toBe(empieza);
      await expect(supervisor.getByText(`Se descargó «${nombre}».`)).toBeVisible();
    }
  });
});
