/**
 * El reloj del inicio (2026-11-24): la hora de Panamá y si es horario laboral, en el inicio de
 * cada rol. El reloj del navegador se fija (clock): el lunes a las 15:00 todavía es laboral y,
 * al pasar el minuto, el reloj cambia solo a «fuera del horario», sin recargar la página.
 */
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

test("el reloj está en el inicio de todos los roles que ven solicitudes", async ({ browser }) => {
  for (const cuenta of [CUENTAS.ucvmm, CUENTAS.puesto, CUENTAS.supervisor, CUENTAS.admin]) {
    const contexto = await browser.newContext();
    const pagina = await contexto.newPage();
    await iniciarSesion(pagina, cuenta);
    await expect(pagina.getByRole("group", { name: "Hora de Panamá" }), cuenta).toBeVisible();
    await contexto.close();
  }
});
