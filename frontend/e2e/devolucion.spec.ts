/**
 * Al devolverse una solicitud, la agencia ve quiénes tienen impedimento según la revisión y que
 * la solicitud no puede avanzar con ellos (pedido del usuario del 2026-11-26). Al corregir tiene
 * que quitarlos; si va otra persona, la agrega como tripulante nuevo. Lo que lee la agencia no
 * nombra a UCVMM.
 */
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, PUESTO, elegirPais, entrar, fechaPanama, pdf } from "./datos";

const tarjeta = (pagina: Page, indice: number) => pagina.locator('[id^="tripulante-"]').nth(indice);

/** Un marino colombiano con su pasaporte; los documentos de su tarjeta, adjuntos. */
async function marino(pagina: Page, indice: number, nombre: string, apellido: string, pasaporte: string) {
  const ficha = tarjeta(pagina, indice);
  await ficha.getByLabel("Nombre(s) *", { exact: true }).fill(nombre);
  await ficha.getByLabel("Apellido(s) *", { exact: true }).fill(apellido);
  await ficha.getByLabel("Sexo *").selectOption("M");
  await ficha.getByLabel("Fecha de nacimiento *").fill("1988-03-14");
  await elegirPais(ficha.getByRole("combobox", { name: "País de nacimiento *" }), "Colombia");
  await elegirPais(ficha.getByRole("combobox", { name: "Nacionalidad *" }), "Colombia");
  await ficha.getByLabel("N° de pasaporte *").fill(pasaporte);
  await ficha.getByLabel("Vence el pasaporte *").fill("2030-05-01");
  for (const documento of ["Visa Especial de Marino", "Generales de Pasaporte", "Libreta de Marino"]) {
    await pagina.getByLabel(`Adjuntar ${documento} de ${nombre} ${apellido}`).setInputFiles(pdf(`${documento} ${nombre}.pdf`));
  }
}

test("al devolverse, la agencia ve quién tiene impedimento y tiene que quitarlo (2026-11-26)", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  const ucvmm = await entrar(browser, CUENTAS.ucvmm);
  let id = "";

  await test.step("la agencia envía un Embarque con dos marinos", async () => {
    await agencia.goto("/new");
    await agencia.getByRole("button", { name: /^Embarque/ }).click();
    await agencia.getByLabel("Puesto de Control Migratorio *").selectOption({ label: PUESTO });
    await agencia.getByLabel("Fecha de la operación en puerto *").fill(fechaPanama(2));
    await agencia.getByLabel("Nombre del buque *").fill("AURORA DEL PACÍFICO");
    await agencia.getByLabel(/^IMO \*/).fill("IMO 9074729");
    await elegirPais(agencia.getByRole("combobox", { name: "Bandera *" }), "Panamá");
    await marino(agencia, 0, "Ana", "Ríos", "PA7700001");
    await agencia.getByRole("button", { name: "Agregar tripulante" }).click();
    await marino(agencia, 1, "Beto", "Ruiz", "PA7700002");
    await agencia.getByLabel("Adjuntar Formulario No. 3").setInputFiles(pdf("Formulario No. 3.pdf"));
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await agencia.waitForURL(/\/solicitudes\/\d+$/);
    id = agencia.url().split("/").pop() ?? "";
  });

  await test.step("UCVMM marca a Beto con impedimento y la devuelve: el modal avisa que la agencia lo verá", async () => {
    await ucvmm.goto(`/solicitudes/${id}`);
    await ucvmm.getByRole("radiogroup", { name: "Impedimento de Ana Ríos en SIMPLUS" }).getByText("Sin", { exact: true }).click();
    await ucvmm.getByRole("radiogroup", { name: "Impedimento de Beto Ruiz en SIMPLUS" }).getByText("Con", { exact: true }).click();
    await ucvmm.getByRole("button", { name: "Guardar verificación" }).click();
    await expect(ucvmm.getByRole("button", { name: "Corregir verificación" })).toBeVisible();
    await ucvmm.getByRole("button", { name: "Devolver a corrección" }).click();
    const modal = ucvmm.getByRole("dialog");
    await expect(modal).toContainText("También verá que Beto Ruiz tiene impedimento");
    await modal.locator("textarea").fill("Uno de los tripulantes no puede embarcar.");
    await modal.getByRole("button", { name: "Devolver" }).click();
    await expect(ucvmm.getByText("En corrección", { exact: true }).first()).toBeVisible();
  });

  await test.step("la agencia lo ve en el expediente, sin que se nombre a UCVMM", async () => {
    await agencia.goto(`/solicitudes/${id}`);
    await expect(agencia.getByText(/^Tripulante con impedimento: Beto Ruiz\. La solicitud no puede avanzar con esa persona/))
      .toBeVisible();
    await expect(agencia.getByText("Con impedimento", { exact: true })).toBeVisible();
    expect(await agencia.locator("body").innerHTML(), "la agencia no ve unidades internas del SNM")
      .not.toMatch(/UCVMM|Sector (Pacífico|Atlántico)/i);
  });

  await test.step("al corregir no deja reenviar con Beto; sin él, sí", async () => {
    await agencia.getByRole("link", { name: "Corregir solicitud" }).click();
    await expect(agencia.getByText(/^Tripulante con impedimento: Beto Ruiz\./)).toBeVisible();
    await expect(tarjeta(agencia, 1).getByText(/Tiene impedimento según la revisión/)).toBeVisible();
    await expect(tarjeta(agencia, 0).getByText(/Tiene impedimento según la revisión/)).toHaveCount(0);

    await agencia.getByRole("button", { name: "Reenviar a revisión" }).click();
    await expect(agencia.getByText(/^Quita a Beto Ruiz: tiene impedimento/)).toBeVisible();
    await expect(agencia).toHaveURL(/\/corregir$/);

    await agencia.getByRole("button", { name: "Quitar tripulante 2" }).click();
    await agencia.getByRole("button", { name: "Reenviar a revisión" }).click();
    await agencia.waitForURL(/\/solicitudes\/\d+$/);
    await expect(agencia.getByText("En revisión", { exact: true }).first()).toBeVisible();
    // El aviso y la marca se van; en el historial queda el motivo de la devolución, con el aviso.
    await expect(agencia.getByText(/^Tripulante con impedimento/)).toHaveCount(0);
    await expect(agencia.getByText("Con impedimento", { exact: true })).toHaveCount(0);
    await expect(agencia.getByText(/Uno de los tripulantes no puede embarcar\.\s+Tripulante con impedimento: Beto Ruiz/)).toBeVisible();
  });
});
