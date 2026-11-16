/**
 * Boleta de recargo por atención fuera del horario laboral (2026-11-16): UCVMM la
 * genera con el número de oficio (que no se repite), se descarga el PDF y, como en un
 * talonario, la anula y genera otra. El supervisor general la ve en el trámite de
 * Técnico, sin generar ni anular. La agencia no la ve. La solicitud la siembra
 * servidor_e2e.py (NUMERO_RECARGO): de Técnico, aprobada un sábado a las 16:20.
 */
import { readFile } from "node:fs/promises";
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, entrar, NUMERO_RECARGO } from "./datos";

const PANEL = "Recargo fuera del horario";

/** Abre la solicitud sembrada desde la bandeja (su id depende del orden de la siembra). */
async function abrirSembrada(pagina: Page, bandeja: "revision" | "supervision" | "agencia"): Promise<void> {
  await pagina.goto(`/dashboard?bandeja=${bandeja}&estado=todas`);
  await pagina.getByRole("link", { name: new RegExp(NUMERO_RECARGO) }).click();
  await expect(pagina).toHaveURL(/\/solicitudes\/\d+$/);
  await expect(pagina.getByText("Autorización marítima · Formulario No. 3")).toBeVisible();
}

test("boleta de recargo: se genera con el oficio, se anula como en un talonario y la agencia no la ve", async ({ browser }) => {
  const ucvmm = await entrar(browser, CUENTAS.ucvmm);
  await abrirSembrada(ucvmm, "revision");
  const panel = ucvmm.getByRole("region", { name: PANEL });
  await expect(panel.getByText("Recargo por atención fuera del horario laboral:")).toBeVisible();
  await expect(panel.getByText("Sin boleta vigente.")).toBeVisible();

  await test.step("UCVMM la genera con el número de oficio y se descarga el PDF", async () => {
    await panel.getByRole("button", { name: "Generar boleta" }).click();
    const modal = ucvmm.getByRole("dialog", { name: "Generar boleta de recargo" });
    // Sin número no la genera: dice qué falta.
    await modal.getByRole("button", { name: "Generar y descargar" }).click();
    await expect(modal.getByText("Escribe el número de oficio.")).toBeVisible();
    await modal.getByLabel("Número de oficio").fill("  E2E-001 ");
    const descarga = ucvmm.waitForEvent("download");
    await modal.getByRole("button", { name: "Generar y descargar" }).click();
    const archivo = await descarga;
    expect(archivo.suggestedFilename()).toBe(`Boleta-recargo-${NUMERO_RECARGO}-e2e-001.pdf`);
    expect((await readFile(await archivo.path())).subarray(0, 5).toString()).toBe("%PDF-");
    await expect(ucvmm.getByText("Boleta de recargo generada (oficio N.º E2E-001).")).toBeVisible();
    await expect(panel.getByText("E2E-001", { exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: "Generar boleta" })).toHaveCount(0);
  });

  await test.step("la anula con motivo; el número anulado no se vuelve a usar", async () => {
    await panel.getByRole("button", { name: "Anular", exact: true }).click();
    const anular = ucvmm.getByRole("dialog", { name: "Anular boleta" });
    await anular.getByLabel("Motivo de la anulación").fill("Número de oficio equivocado");
    await anular.getByRole("button", { name: "Anular boleta" }).click();
    await expect(ucvmm.getByText("Boleta anulada (oficio N.º E2E-001).")).toBeVisible();
    await expect(panel.getByText("Sin boleta vigente.")).toBeVisible();
    await expect(panel.getByText("Anuladas (1)")).toBeVisible();

    await panel.getByRole("button", { name: "Generar boleta" }).click();
    const generar = ucvmm.getByRole("dialog", { name: "Generar boleta de recargo" });
    await generar.getByLabel("Número de oficio").fill("e2e-001");
    await generar.getByRole("button", { name: "Generar y descargar" }).click();
    await expect(ucvmm.getByText(/El número de oficio E2E-001 ya está en la boleta/)).toBeVisible();
    await expect(generar).toBeVisible();   // sigue abierto, para escribir otro
    await generar.getByLabel("Número de oficio").fill("E2E-002");
    const descarga = ucvmm.waitForEvent("download");
    await generar.getByRole("button", { name: "Generar y descargar" }).click();
    await descarga;
    await expect(panel.getByText("E2E-002", { exact: true })).toBeVisible();
    // Lo interno queda en el historial del SNM.
    await expect(ucvmm.getByText("Boleta de recargo anulada", { exact: true })).toBeVisible();
  });

  await test.step("el supervisor general la ve en el trámite de Técnico, sin generar ni anular", async () => {
    const supervisor = await entrar(browser, CUENTAS.supervisor);
    await abrirSembrada(supervisor, "supervision");
    await expect(supervisor.getByText("Sector Pacífico", { exact: true })).toBeVisible();
    await expect(supervisor.getByRole("button", { name: /^(Aprobar|Devolver|Denegar|Finalizar|Guardar verificación)/ }))
      .toHaveCount(0);
    const suyo = supervisor.getByRole("region", { name: PANEL });
    await expect(suyo.getByText("E2E-002", { exact: true })).toBeVisible();
    await expect(suyo.getByRole("button", { name: /^(Generar boleta|Anular)$/ })).toHaveCount(0);
    const descarga = supervisor.waitForEvent("download");
    await suyo.getByRole("button", { name: "Descargar boleta" }).click();
    expect((await descarga).suggestedFilename()).toBe(`Boleta-recargo-${NUMERO_RECARGO}-e2e-002.pdf`);
  });

  await test.step("la agencia ve el recargo, pero no la boleta ni su historial", async () => {
    const agencia = await entrar(browser, CUENTAS.agencia);
    await abrirSembrada(agencia, "agencia");
    await expect(agencia.getByText(/Recargo por atención fuera del horario laboral: B\/\.20\.00/)).toBeVisible();
    await expect(agencia.getByRole("region", { name: PANEL })).toHaveCount(0);
    await expect(agencia.getByText(/E2E-00|Boleta de recargo/)).toHaveCount(0);
  });
});
