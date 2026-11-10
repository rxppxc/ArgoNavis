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
  const ucvmm = await entrar(browser, CUENTAS.ucvmm);
  await ucvmm.goto("/admin/stats");
  await expect(ucvmm.getByRole("heading", { name: "Estadísticas", level: 1 })).toBeVisible();

  await test.step("«Mes pasado» se ve por día y «Este año», por mes", async () => {
    await ucvmm.getByRole("button", { name: "Mes pasado" }).click();
    await expect(ucvmm.getByRole("heading", { name: "Solicitudes por día" })).toBeVisible();
    await expect(ucvmm.getByRole("button", { name: "Día", exact: true })).toHaveAttribute("aria-pressed", "true");
    await ucvmm.getByRole("button", { name: "Este año" }).click();
    await expect(ucvmm.getByRole("heading", { name: "Solicitudes por mes" })).toBeVisible();
  });

  await test.step("Excel, PDF y CSV del periodo elegido", async () => {
    const grupo = ucvmm.getByRole("group", { name: "Exportar las estadísticas del periodo" });
    for (const { boton, extension, empieza } of FORMATOS) {
      const descarga = ucvmm.waitForEvent("download");
      await grupo.getByRole("button", { name: boton, exact: true }).click();
      const archivo = await descarga;
      const nombre = archivo.suggestedFilename();
      expect(nombre).toMatch(new RegExp(`^Estadisticas-autorizaciones-\\d{4}-01-01_\\d{4}-\\d{2}-\\d{2}\\.${extension}$`));
      const contenido = await readFile(await archivo.path());
      expect(contenido.subarray(0, Buffer.byteLength(empieza)).toString(), nombre).toBe(empieza);
      await expect(ucvmm.getByText(`Se descargó «${nombre}».`)).toBeVisible();
    }
  });
});
