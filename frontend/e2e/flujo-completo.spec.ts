/**
 * Recorrido completo de una autorización, como en la demo: la agencia envía,
 * UCVMM verifica y devuelve, la agencia corrige, UCVMM aprueba, la agencia
 * descarga el PDF, un tercero verifica el QR, el puesto finaliza y el
 * Administrador lo ve en la bitácora.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { CUENTAS, NOMBRE_REVISOR, PUESTO, entrar, fechaPanama, pdf } from "./datos";

const TRIPULANTE = "Juan Carlos Pérez Gómez";

/** La insignia de estado del expediente. */
const estado = (pagina: Page, texto: string) => pagina.getByText(texto, { exact: true }).first();

/** Marca al tripulante «Sin impedimento» y guarda la verificación. */
async function verificarSinImpedimento(pagina: Page) {
  await pagina.getByRole("radiogroup", { name: `Impedimento de ${TRIPULANTE} en SIMPLUS` })
    .getByText("Sin", { exact: true }).click();
  await pagina.getByRole("button", { name: "Guardar verificación" }).click();
  await expect(pagina.getByRole("button", { name: "Corregir verificación" })).toBeVisible();
}

test("agencia → UCVMM → corrección → aprobación → verificación → puesto → bitácora", async ({ browser }) => {
  let id = "";
  let codigo = "";

  const agencia = await entrar(browser, CUENTAS.agencia);
  const ucvmm = await entrar(browser, CUENTAS.ucvmm);

  await test.step("la agencia envía un Embarque con su checklist", async () => {
    await agencia.getByRole("link", { name: "Nueva solicitud" }).first().click();
    await agencia.getByRole("button", { name: /^Embarque/ }).click();

    await agencia.getByLabel("Puesto de Control Migratorio *").selectOption({ label: PUESTO });
    await agencia.getByLabel("Fecha de la operación en puerto *").fill(fechaPanama(2));
    await agencia.getByLabel("Nombre del buque *").fill("ESTRELLA DEL ISTMO");
    await agencia.getByLabel(/^IMO \*/).fill("IMO 9074729");
    await agencia.getByLabel("Bandera *").selectOption("PAN");

    await agencia.getByLabel("Nombre(s) *", { exact: true }).fill("Juan Carlos");
    await agencia.getByLabel("Apellido(s) *", { exact: true }).fill("Pérez Gómez");
    await agencia.getByLabel("Sexo *").selectOption("M");
    await agencia.getByLabel("Fecha de nacimiento *").fill("1988-03-14");
    await agencia.getByLabel("País de nacimiento *").selectOption("PAN");
    await agencia.getByLabel("Nacionalidad *").selectOption("PAN");
    await agencia.getByLabel("Ocupación *").fill("Primer oficial");
    await agencia.getByLabel("N° de pasaporte *").fill("PA1234567");
    await agencia.getByLabel("Vence el pasaporte *").fill("2030-05-01");
    await agencia.getByLabel("N° de seamanbook *").fill("SB-778812");
    await agencia.getByLabel("Vence el seamanbook *").fill("2029-11-30");

    for (const documento of ["Visa Especial de Marino", "Generales de Pasaporte", "Libreta de Marino"]) {
      await agencia.getByLabel(`Adjuntar ${documento} de ${TRIPULANTE}`).setInputFiles(pdf(`${documento}.pdf`));
    }
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await agencia.waitForURL(/\/solicitudes\/\d+$/);
    id = agencia.url().split("/").pop() ?? "";
    await expect(estado(agencia, "En revisión")).toBeVisible();
  });

  await test.step("UCVMM verifica los impedimentos y la devuelve", async () => {
    await ucvmm.goto(`/solicitudes/${id}`);
    await verificarSinImpedimento(ucvmm);
    await ucvmm.getByRole("button", { name: "Devolver a corrección" }).click();
    const modal = ucvmm.getByRole("dialog");
    await modal.locator("textarea").fill("La visa especial de marino está ilegible.");
    await modal.getByRole("button", { name: "Devolver" }).click();
    await expect(estado(ucvmm, "En corrección")).toBeVisible();
  });

  await test.step("la agencia corrige: reemplaza la visa y reenvía", async () => {
    await agencia.goto(`/solicitudes/${id}`);
    // El motivo sale en el aviso de la devolución y en el historial.
    await expect(agencia.getByText("La visa especial de marino está ilegible.").first()).toBeVisible();
    await agencia.getByRole("link", { name: "Corregir solicitud" }).click();
    await agencia.getByLabel(`Reemplazar Visa Especial de Marino de ${TRIPULANTE}`).setInputFiles(pdf("Visa corregida.pdf"));
    await agencia.getByRole("button", { name: "Reenviar a revisión" }).click();
    await agencia.waitForURL(/\/solicitudes\/\d+$/);
    await expect(estado(agencia, "En revisión")).toBeVisible();
  });

  await test.step("UCVMM verifica de nuevo y aprueba", async () => {
    await ucvmm.goto(`/solicitudes/${id}`);
    await verificarSinImpedimento(ucvmm);
    await ucvmm.getByRole("button", { name: "Aprobar", exact: true }).click();
    await ucvmm.getByRole("dialog").getByRole("button", { name: "Aprobar" }).click();
    await expect(estado(ucvmm, "Aprobada")).toBeVisible();
  });

  await test.step("la agencia ve «UCVMM», no al funcionario, y descarga el PDF", async () => {
    await agencia.goto(`/solicitudes/${id}`);
    await expect(estado(agencia, "Aprobada")).toBeVisible();
    await expect(agencia.getByText(NOMBRE_REVISOR)).toHaveCount(0);
    const [descarga] = await Promise.all([
      agencia.waitForEvent("download"),
      agencia.getByRole("button", { name: "Descargar autorización (PDF)" }).click(),
    ]);
    const contenido = readFileSync(await descarga.path()).toString("latin1");
    expect(contenido.startsWith("%PDF-")).toBe(true);
    codigo = contenido.match(/verificar\/([A-Za-z0-9_-]+)/)?.[1] ?? "";
    expect(codigo).not.toBe("");
  });

  await test.step("un tercero verifica el QR sin sesión", async () => {
    const tercero = await (await browser.newContext()).newPage();
    await tercero.goto(`/verificar/${codigo}`);
    await expect(tercero.getByText("Autorización auténtica y vigente")).toBeVisible();
    await expect(tercero.getByText(/PA1234567/)).toHaveCount(0);   // pasaporte enmascarado
    await tercero.goto("/verificar/codigo-que-no-existe");
    await expect(tercero.getByText("Autorización no encontrada")).toBeVisible();
  });

  await test.step("el puesto de control finaliza", async () => {
    const puesto = await entrar(browser, CUENTAS.puesto);
    await puesto.goto(`/solicitudes/${id}`);
    await puesto.getByLabel("Comentario de la operación *").fill("Embarque realizado sin novedad.");
    await puesto.getByRole("button", { name: "Finalizar", exact: true }).click();
    await puesto.getByRole("dialog").getByRole("button", { name: "Finalizar" }).click();
    await expect(estado(puesto, "Finalizada")).toBeVisible();

    const tercero = await (await browser.newContext()).newPage();
    await tercero.goto(`/verificar/${codigo}`);
    await expect(tercero.getByText("Autorización auténtica — operación finalizada")).toBeVisible();
  });

  await test.step("el Administrador ve usuarios y la bitácora", async () => {
    const admin = await entrar(browser, CUENTAS.admin);
    await admin.goto("/admin");
    await expect(admin.getByText(`@${CUENTAS.agencia}`)).toBeVisible();
    await admin.goto("/admin/bitacora");
    await expect(admin.getByRole("cell", { name: "Solicitud finalizada" }).first()).toBeVisible();
  });
});
