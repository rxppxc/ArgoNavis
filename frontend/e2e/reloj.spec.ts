/**
 * El reloj del inicio (2026-11-24): la hora de Panamá y si es horario laboral, en el inicio de
 * cada rol. El reloj del navegador se fija (clock): el lunes a las 15:00 todavía es laboral y,
 * al pasar el minuto, el reloj cambia solo a «fuera del horario», sin recargar la página.
 */
import type { Locator } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, iniciarSesion } from "./datos";

// Lunes 16 de noviembre de 2026, 15:00:05 en Panamá (UTC−5). El reloj del navegador corre
// desde ahí: entrar toma unos segundos y sigue siendo las 15:00.
const LUNES_A_LAS_15 = new Date("2026-11-16T20:00:05Z");

test("el inicio muestra la hora de Panamá y cambia solo al salir del horario laboral", async ({ browser }) => {
  const contexto = await browser.newContext();
  await contexto.clock.install({ time: LUNES_A_LAS_15 });
  const agencia = await contexto.newPage();
  await iniciarSesion(agencia, CUENTAS.agencia);

  const reloj = agencia.getByRole("group", { name: "Hora de Panamá" });
  await expect(reloj).toContainText("15:00");
  await expect(reloj).toContainText("lunes, 16 de noviembre de 2026");
  await expect(reloj).toContainText("Horario laboral hasta las 15:00");
  await expect(reloj).toContainText("Horario: lunes a viernes, de 07:00 a 15:00");
  await expect(reloj).not.toContainText("recargo");

  await test.step("a las 15:01 ya es fuera del horario: lo que se apruebe lleva recargo", async () => {
    await contexto.clock.runFor(60_000);
    await expect(reloj).toContainText("15:01");
    await expect(reloj).toContainText("Fuera del horario hasta mañana a las 07:00");
    await expect(reloj).toContainText("Lo que se apruebe ahora lleva recargo.");
  });

  await test.step("solo en el inicio", async () => {
    await agencia.getByRole("link", { name: "Nueva solicitud" }).first().click();
    await expect(agencia).toHaveURL(/\/new$/);
    await expect(agencia.getByRole("group", { name: "Tipo de trámite" })).toBeVisible();
    await expect(reloj).toHaveCount(0);
  });

  await contexto.close();
});

test("el reloj va bajo el encabezado, de borde a borde, y los botones junto al título", async ({ browser }) => {
  // Hasta el 2026-11-27 iba entre las acciones del encabezado: con los botones no cabía junto al
  // título, saltaba a otra línea pegado a la izquierda y cada rol veía un encabezado distinto.
  const contexto = await browser.newContext({ viewport: { width: 1024, height: 800 } });
  const pagina = await contexto.newPage();
  await iniciarSesion(pagina, CUENTAS.agencia);
  const caja = async (elemento: Locator) => {
    await expect(elemento).toBeVisible();
    const medida = await elemento.boundingBox();
    if (!medida) throw new Error("sin medida");
    return { ...medida, derecha: medida.x + medida.width, abajo: medida.y + medida.height };
  };

  const encabezado = await caja(pagina.locator("header", { has: pagina.locator("h1") }));
  const descripcion = await caja(pagina.getByText("Solicitudes de autorización marítima de tu agencia"));
  const nueva = await caja(pagina.getByRole("link", { name: "Nueva solicitud" }).first());
  const reloj = await caja(pagina.getByRole("group", { name: "Hora de Panamá" }));
  const pestanas = await caja(pagina.getByRole("tablist", { name: "Estado" }));

  expect(reloj.y, "el reloj, debajo del encabezado").toBeGreaterThanOrEqual(encabezado.abajo);
  expect(Math.abs(reloj.x - pestanas.x), "de borde a borde: el izquierdo").toBeLessThanOrEqual(1);
  expect(Math.abs(reloj.derecha - pestanas.derecha), "de borde a borde: el derecho").toBeLessThanOrEqual(1);
  expect(Math.abs(nueva.derecha - pestanas.derecha), "el botón, en el borde derecho").toBeLessThanOrEqual(1);
  expect(nueva.y, "el botón, en la fila del título").toBeLessThan(descripcion.abajo);
  await contexto.close();
});

test("el reloj está en el inicio de todos los roles que ven solicitudes", async ({ browser }) => {
  for (const cuenta of [CUENTAS.ucvmm, CUENTAS.puesto, CUENTAS.supervisor, CUENTAS.admin]) {
    const contexto = await browser.newContext();
    const pagina = await contexto.newPage();
    await iniciarSesion(pagina, cuenta);
    await expect(pagina.getByRole("group", { name: "Hora de Panamá" }), cuenta).toBeVisible();
    await contexto.close();
  }
});
