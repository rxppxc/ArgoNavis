/**
 * Teclado, lector de pantalla y despliegues (revisión del 2026-10-27): el
 * enlace «Saltar al contenido», los controles que no tenían nombre y la
 * recarga cuando, tras un despliegue, falta un archivo de la versión anterior.
 */
import { expect, test } from "@playwright/test";
import { CUENTAS, entrar } from "./datos";

test("teclado, nombres de los controles y recarga tras un despliegue", async ({ browser, page }) => {
  await test.step("el primer Tab ofrece saltar al contenido", async () => {
    // Página pública con el marco común, sin campo con foco automático.
    await page.goto("/verificar/codigo-de-prueba");
    await page.keyboard.press("Tab");
    const saltar = page.getByRole("link", { name: "Saltar al contenido" });
    await expect(saltar).toBeFocused();
    await expect(saltar).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(page.locator("main#contenido")).toBeFocused();
  });

  await test.step("si falta un archivo de la versión anterior, recarga una sola vez", async () => {
    const preloadError = () => page.evaluate(() => {
      (window as unknown as { marca: boolean }).marca = true;
      // Fuera del evaluate: la recarga destruiría el contexto que lo corre.
      setTimeout(() => window.dispatchEvent(new Event("vite:preloadError", { cancelable: true })));
    });
    const recarga = page.waitForEvent("load");
    await preloadError();
    await recarga;
    expect(await page.evaluate(() => "marca" in window), "recargó la página").toBe(false);

    await preloadError();
    await page.waitForTimeout(1000);
    expect(await page.evaluate(() => "marca" in window), "dentro del minuto no vuelve a recargar").toBe(true);
  });

  await test.step("los controles se anuncian con su nombre", async () => {
    const admin = await entrar(browser, CUENTAS.admin);
    await admin.goto("/admin");
    await expect(admin.getByRole("combobox", { name: /^Rol de / }).first()).toBeVisible();
    await admin.goto("/admin/catalogos");
    await expect(admin.getByRole("checkbox", { name: /^Activo: / }).first()).toBeAttached();

    const agencia = await entrar(browser, CUENTAS.agencia);
    await agencia.getByRole("link", { name: "Nueva solicitud" }).first().click();
    await agencia.getByRole("button", { name: /^Embarque/ }).click();
    await expect(agencia.getByLabel("Agencia naviera")).not.toHaveValue("");
    await expect(agencia.getByLabel("Fecha y hora de solicitud")).not.toHaveValue("");
    await expect(agencia.getByRole("textbox", { name: "Observaciones", exact: true })).toBeVisible();
  });
});
