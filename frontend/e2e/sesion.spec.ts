/**
 * La sesión con varias pestañas abiertas (revisión del 2026-10-27): la
 * inactividad es la de todas, y salir en una saca a las demás. Antes, una
 * pestaña olvidada cerraba a los 15 minutos la sesión de la que se usaba.
 * El reloj del navegador se adelanta (clock): 15 minutos pasan en un instante.
 */
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, iniciarSesion } from "./datos";

const MINUTO = 60_000;

test("la inactividad y el cierre de sesión valen para todas las pestañas", async ({ browser }) => {
  const contexto = await browser.newContext();
  await contexto.clock.install();
  const a = await contexto.newPage();
  const b = await contexto.newPage();
  await iniciarSesion(a, CUENTAS.agencia);
  await b.goto("/dashboard");
  await expect(b.getByRole("button", { name: "Menú" })).toBeVisible();

  const aviso = (p: Page) => p.getByRole("dialog", { name: "Sesión por expirar" });
  let x = 100;
  const moverMouse = (p: Page) => p.mouse.move((x += 10), 200);   // cada vez a otro punto: si no, no hay evento

  await test.step("mientras se trabaja en una, la otra no avisa ni cierra la sesión", async () => {
    for (let i = 0; i < 4; i++) {
      await moverMouse(a);
      await contexto.clock.runFor(4 * MINUTO);
    }
    // B lleva 16 minutos sin que nadie la toque.
    await expect(aviso(b)).toHaveCount(0);
    await expect(b).toHaveURL(/\/dashboard$/);
    await expect(a).toHaveURL(/\/dashboard$/);
  });

  await test.step("sin actividad en ninguna, avisan las dos; «Continuar» en una quita el aviso de la otra", async () => {
    await moverMouse(a);
    await contexto.clock.runFor(13 * MINUTO + 1000);
    await expect(aviso(a)).toBeVisible();
    await expect(aviso(b)).toBeVisible();
    await b.getByRole("button", { name: "Continuar sesión" }).click();
    await expect(aviso(a)).toHaveCount(0);
    await expect(aviso(b)).toHaveCount(0);
  });

  await test.step("a los 15 minutos sin actividad, las dos vuelven al login", async () => {
    await contexto.clock.runFor(15 * MINUTO + 1000);
    await expect(a).toHaveURL(/\/login/);
    await expect(b).toHaveURL(/\/login/);
  });

  await test.step("al salir en una pestaña, la otra vuelve al login sin esperar", async () => {
    await iniciarSesion(a, CUENTAS.agencia);
    await b.goto("/dashboard");
    await expect(b.getByRole("button", { name: "Menú" })).toBeVisible();
    // Ningún pedido con el token ya revocado: antes, la campana consultaba
    // /pendientes al cambiar de ruta mientras salía el aviso del cierre (401).
    const rechazados: string[] = [];
    for (const p of [a, b]) p.on("response", (r) => { if (r.status() === 401) rechazados.push(r.url()); });
    await a.getByRole("button", { name: "Menú" }).click();
    await a.getByRole("button", { name: "Salir" }).click();
    // Sin «?siguiente=»: la sacó el aviso de la otra pestaña, no un 401 de un pedido suyo.
    await expect(b).toHaveURL(/\/login$/);
    await expect(a).toHaveURL(/\/login$/);
    await a.waitForTimeout(1000);   // por si un pedido rezagado vuelve después
    expect(rechazados, "pedidos rechazados al cerrar sesión").toEqual([]);
  });

  await contexto.close();
});
