/**
 * El formulario de «Nueva solicitud», sin enviarlo: lo que hace con los
 * documentos al quitar un pasajero, cambiarle el rango (con el boleto opcional
 * de los técnicos en Desembarque) o cambiar de trámite,
 * el resumen de lo que falta, los adicionales y el aviso de lo que hay que revisar.
 */
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, entrar, pdf } from "./datos";

const tarjeta = (pagina: Page, indice: number) => pagina.locator('[id^="tripulante-"]').nth(indice);

async function marinoPanameno(pagina: Page, indice: number, nombre: string) {
  await tarjeta(pagina, indice).getByLabel("Nombre(s) *", { exact: true }).fill(nombre);
  await tarjeta(pagina, indice).getByLabel("Nacionalidad *").selectOption("PAN");
}

test("el formulario cuida los documentos al quitar un pasajero o cambiar de trámite", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  await agencia.goto("/new");
  await agencia.getByRole("button", { name: /^Embarque/ }).click();

  // Dos marinos panameños: Embarque pide tres documentos a cada uno, en su tarjeta.
  await marinoPanameno(agencia, 0, "Ana");
  await agencia.getByRole("button", { name: "Agregar pasajero" }).click();
  await marinoPanameno(agencia, 1, "Beto");
  await expect(agencia.getByText("Faltan 6 documentos por adjuntar")).toBeVisible();

  await agencia.getByLabel("Adjuntar Visa Especial de Marino de Ana").setInputFiles(pdf("visa-ana.pdf"));
  await agencia.getByLabel("Adjuntar Visa Especial de Marino de Beto").setInputFiles(pdf("visa-beto.pdf"));
  await expect(agencia.getByText("Faltan 4 documentos por adjuntar")).toBeVisible();

  await test.step("al quitar un pasajero se van sus archivos", async () => {
    await expect(agencia.getByText("visa-beto.pdf")).toBeVisible();
    await agencia.getByRole("button", { name: "Quitar pasajero 2" }).click();
    await expect(agencia.getByText("Faltan 2 documentos por adjuntar")).toBeVisible();
    await expect(agencia.getByText("visa-beto.pdf")).toHaveCount(0);
  });

  await test.step("en Embarque, al militar se le piden Generales y boleto; al técnico, Carta, Generales y Contrato", async () => {
    await tarjeta(agencia, 0).getByLabel("Rango *").selectOption("militar");
    await expect(agencia.getByLabel("Adjuntar Copia de Boleto Aéreo de Ana")).toBeAttached();
    await expect(agencia.getByText("visa-ana.pdf")).toHaveCount(0);
    await expect(agencia.getByText("Faltan 2 documentos por adjuntar")).toBeVisible();

    await tarjeta(agencia, 0).getByLabel("Rango *").selectOption("tecnico");
    await expect(agencia.getByLabel("Adjuntar Carta de Responsabilidad (Form. No. 7) de Ana")).toBeAttached();
    await expect(agencia.getByLabel("Adjuntar Contrato de Trabajo de Ana")).toBeAttached();
    await expect(agencia.getByLabel("Adjuntar Copia de Boleto Aéreo de Ana")).toHaveCount(0);
    await expect(agencia.getByText("Faltan 3 documentos por adjuntar")).toBeVisible();

    // La visa no se pierde: vuelve a su casilla al volver a Marino.
    await tarjeta(agencia, 0).getByLabel("Rango *").selectOption("marino");
    await expect(agencia.getByText("visa-ana.pdf")).toBeVisible();
    await expect(agencia.getByLabel("Adjuntar Contrato de Trabajo de Ana")).toHaveCount(0);
  });

  await test.step("el resumen lleva a la tarjeta y la expande", async () => {
    await agencia.getByRole("button", { name: "Contraer pasajero 1" }).click();
    await expect(agencia.getByRole("button", { name: "Expandir pasajero 1" })).toBeVisible();
    await agencia.getByRole("button", { name: /^1\. Ana/ }).click();
    await expect(agencia.getByRole("button", { name: "Contraer pasajero 1" })).toBeVisible();
  });

  await test.step("cambiar de trámite con archivos adjuntos pide confirmación y los quita", async () => {
    await agencia.getByRole("button", { name: "Cambiar", exact: true }).click();
    await agencia.getByRole("button", { name: /^Desembarque/ }).click();
    // Quita archivos: es un aviso que pide respuesta (alertdialog).
    const dialogo = agencia.getByRole("alertdialog");
    // Uno solo: el de Beto se fue con él.
    await expect(dialogo).toContainText("se quitará el documento");
    await dialogo.getByRole("button", { name: "Cancelar" }).click();
    await expect(agencia.getByText("visa-ana.pdf")).toBeVisible();

    await agencia.getByRole("button", { name: /^Desembarque/ }).click();
    await agencia.getByRole("alertdialog").getByRole("button", { name: "Cambiar de trámite" }).click();
    await expect(agencia.getByRole("button", { name: "Cambiar", exact: true })).toBeVisible();
    await expect(agencia.getByText("visa-ana.pdf")).toHaveCount(0);
  });

  await test.step("en Desembarque, al técnico el boleto es opcional", async () => {
    await tarjeta(agencia, 0).getByLabel("Rango *").selectOption("tecnico");
    await expect(agencia.getByLabel("Adjuntar Copia de Boleto Aéreo de Ana (opcional)")).toBeAttached();
    await expect(tarjeta(agencia, 0).getByText("Opcional", { exact: true })).toBeVisible();
    await agencia.getByLabel("Adjuntar Generales de Pasaporte de Ana").setInputFiles(pdf("generales.pdf"));
    await agencia.getByLabel("Adjuntar Carta de Responsabilidad (Form. No. 7) de Ana").setInputFiles(pdf("responsabilidad.pdf"));
    await agencia.getByLabel("Adjuntar Contrato de Trabajo de Ana").setInputFiles(pdf("contrato.pdf"));
    // Sin el boleto, su tarjeta queda completa: solo falta la Lista de Tripulantes, que es de la solicitud.
    await expect(tarjeta(agencia, 0).getByText("3/3 documentos")).toBeVisible();
    await expect(agencia.getByText("Falta 1 documento por adjuntar")).toBeVisible();
  });

  await test.step("los documentos adicionales se agregan y se quitan", async () => {
    await agencia.getByLabel("Agregar documento").setInputFiles([pdf("carta.pdf"), pdf("oficio.pdf")]);
    await expect(agencia.getByText("carta.pdf")).toBeVisible();
    await agencia.getByRole("button", { name: "Quitar carta.pdf" }).click();
    await expect(agencia.getByText("carta.pdf")).toHaveCount(0);
    await expect(agencia.getByText("oficio.pdf")).toBeVisible();
  });

  await test.step("con datos faltantes no se envía: dice qué revisar", async () => {
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await expect(agencia.getByRole("alert").filter({ hasText: "Revisa antes de enviar" })).toBeVisible();
    await expect(agencia).toHaveURL(/\/new$/);
  });
});
