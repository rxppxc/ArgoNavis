/**
 * El formulario de «Nueva solicitud», sin enviarlo: lo que hace con los
 * documentos al quitar un pasajero, cambiarle el rango (el Pasajero presenta lo
 * del Marino sin la Libreta, 2026-11-13) o cambiar de trámite, el cambio de
 * puerto, el resumen de lo que falta, los adicionales y el aviso de lo que hay que revisar.
 */
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import {
  CUENTAS, PUESTO, PUESTO_MISMO_SECTOR, PUESTO_OTRO_SECTOR, elegirPais, entrar, fechaPanama, opcionesDe, pdf,
} from "./datos";

const tarjeta = (pagina: Page, indice: number) => pagina.locator('[id^="tripulante-"]').nth(indice);

async function marinoPanameno(pagina: Page, indice: number, nombre: string) {
  await tarjeta(pagina, indice).getByLabel("Nombre(s) *", { exact: true }).fill(nombre);
  await elegirPais(tarjeta(pagina, indice).getByRole("combobox", { name: "Nacionalidad *" }), "Panamá");
}

test("el formulario cuida los documentos al quitar un pasajero o cambiar de trámite", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  await agencia.goto("/new");
  await agencia.getByRole("button", { name: /^Embarque/ }).click();

  // Dos marinos panameños: Embarque pide tres documentos a cada uno, en su tarjeta,
  // y el Formulario No. 3 a la solicitud (2026-11-13).
  await marinoPanameno(agencia, 0, "Ana");
  await agencia.getByRole("button", { name: "Agregar pasajero" }).click();
  await marinoPanameno(agencia, 1, "Beto");
  await expect(agencia.getByText("Faltan 7 documentos por adjuntar")).toBeVisible();

  await agencia.getByLabel("Adjuntar Visa Especial de Marino de Ana").setInputFiles(pdf("visa-ana.pdf"));
  await agencia.getByLabel("Adjuntar Visa Especial de Marino de Beto").setInputFiles(pdf("visa-beto.pdf"));
  await expect(agencia.getByText("Faltan 5 documentos por adjuntar")).toBeVisible();

  await test.step("al quitar un pasajero se van sus archivos", async () => {
    await expect(agencia.getByText("visa-beto.pdf")).toBeVisible();
    await agencia.getByRole("button", { name: "Quitar pasajero 2" }).click();
    await expect(agencia.getByText("Faltan 3 documentos por adjuntar")).toBeVisible();
    await expect(agencia.getByText("visa-beto.pdf")).toHaveCount(0);
  });

  await test.step("en Embarque: Marino, Pasajero o Militar; los técnicos van por su trámite", async () => {
    const rango = tarjeta(agencia, 0).getByLabel("Rango *");
    // 2026-11-13: los técnicos, supernumerarios y superintendentes van por el trámite de Técnico.
    await expect(rango.locator("option")).toHaveText(["Marino", "Pasajero", "Militar"]);

    // Al militar, Generales y boleto (reunión del 2026-10-30).
    await rango.selectOption("militar");
    await expect(agencia.getByLabel("Adjuntar Copia de Boleto Aéreo de Ana")).toBeAttached();
    await expect(agencia.getByText("visa-ana.pdf")).toHaveCount(0);
    await expect(agencia.getByText("Faltan 3 documentos por adjuntar")).toBeVisible();

    // Al Pasajero, lo del Marino sin la Libreta: la visa vuelve a su casilla.
    await rango.selectOption("pasajero");
    await expect(agencia.getByText("visa-ana.pdf")).toBeVisible();
    await expect(agencia.getByLabel("Adjuntar Libreta de Marino de Ana")).toHaveCount(0);
    await expect(tarjeta(agencia, 0).getByLabel(/seamanbook/)).toHaveCount(0);
    await expect(agencia.getByText("Faltan 2 documentos por adjuntar")).toBeVisible();

    await rango.selectOption("marino");
    await expect(agencia.getByText("visa-ana.pdf")).toBeVisible();
    await expect(agencia.getByLabel("Adjuntar Libreta de Marino de Ana")).toBeAttached();
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

  await test.step("en Desembarque, el Pasajero presenta lo del Marino sin la Libreta", async () => {
    await tarjeta(agencia, 0).getByLabel("Rango *").selectOption("pasajero");
    await expect(agencia.getByLabel("Adjuntar Libreta de Marino de Ana")).toHaveCount(0);
    await agencia.getByLabel("Adjuntar Generales de Pasaporte de Ana").setInputFiles(pdf("generales.pdf"));
    await agencia.getByLabel("Adjuntar Copia de Boleto Aéreo de Ana").setInputFiles(pdf("boleto.pdf"));
    // Su tarjeta queda completa: solo faltan los de la solicitud, la Lista de Tripulantes y
    // el Formulario No. 3.
    await expect(tarjeta(agencia, 0).getByText("2/2 documentos")).toBeVisible();
    await expect(agencia.getByText("Faltan 2 documentos por adjuntar")).toBeVisible();
    await agencia.getByLabel("Adjuntar Formulario No. 3").setInputFiles(pdf("formulario-3.pdf"));
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
    // Muchos equipos del SNM traen las animaciones de Windows apagadas: el aviso igual tiene
    // que durar (su barra de tiempo lleva data-movimiento; sin eso, se cerraba al aparecer).
    await agencia.emulateMedia({ reducedMotion: "reduce" });
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await expect(agencia.getByRole("alert").filter({ hasText: "Revisa antes de enviar" })).toBeVisible();
    await expect(agencia).toHaveURL(/\/new$/);
    const aviso = agencia.getByText("Revisa los datos marcados antes de enviar.");
    await expect(aviso).toBeVisible();
    await agencia.waitForTimeout(1500);
    await expect(aviso, "con «reducir movimiento», el aviso no se cierra solo al aparecer").toBeVisible();
  });
});

test("el cambio de puerto ofrece solo los puestos del mismo sector", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  await agencia.goto("/new");
  await agencia.getByRole("button", { name: /^Embarque/ }).click();

  const cambio = agencia.getByLabel("¿Cambio de puerto? *");
  await expect(cambio).toHaveValue("no");
  const nuevo = agencia.getByLabel("Nuevo puesto de control *");
  await expect(nuevo).toHaveCount(0);

  await cambio.selectOption("si");
  await expect(nuevo).toBeDisabled();   // primero, el puesto de control

  const puesto = agencia.getByLabel("Puesto de Control Migratorio *");
  await puesto.selectOption({ label: PUESTO });
  await expect(nuevo).toBeEnabled();
  const opciones = await nuevo.locator("option").allTextContents();
  expect(opciones).toContain(PUESTO_MISMO_SECTOR);
  expect(opciones, "del otro sector va una solicitud nueva").not.toContain(PUESTO_OTRO_SECTOR);
  expect(opciones).not.toContain(PUESTO);
  await nuevo.selectOption({ label: PUESTO_MISMO_SECTOR });
  await expect(agencia.getByText(/si el nuevo puerto no está en la lista, presenta una nueva solicitud/)).toBeVisible();
  expect(await agencia.locator("body").innerHTML(), "a la agencia no se le nombran los sectores")
    .not.toMatch(/UCVMM|Sector (Pacífico|Atlántico)/i);

  // Si el primer puesto pasa a ser el elegido como nuevo, el nuevo se quita.
  await puesto.selectOption({ label: PUESTO_MISMO_SECTOR });
  await expect(nuevo).toHaveValue("");
  await expect(nuevo.locator("option", { hasText: PUESTO_MISMO_SECTOR })).toHaveCount(0);

  // Con «Sí» y sin el nuevo puesto no se envía: dice qué falta.
  await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
  await expect(agencia.getByRole("alert").filter({ hasText: "Elige el nuevo puesto de control del cambio de puerto." }))
    .toBeVisible();

  await cambio.selectOption("no");
  await expect(nuevo).toHaveCount(0);
});

test("el pasaporte con 3 meses de vigencia; el seamanbook vencido solo avisa", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  await agencia.goto("/new");
  await agencia.getByRole("button", { name: /^Embarque/ }).click();
  await agencia.getByLabel("Fecha de la operación en puerto *").fill(fechaPanama(2));
  const ficha = tarjeta(agencia, 0);

  await test.step("con menos de 3 meses desde la operación, no se envía", async () => {
    await ficha.getByLabel("Vence el pasaporte *").fill(fechaPanama(62));
    await expect(ficha.getByText(/^El pasaporte debe tener al menos 3 meses de vigencia a partir de la operación/))
      .toBeVisible();
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await expect(agencia.getByRole("alert").filter({ hasText: "al menos 3 meses de vigencia" }).first()).toBeVisible();

    await ficha.getByLabel("Vence el pasaporte *").fill(fechaPanama(200));
    await expect(ficha.getByText(/meses de vigencia/)).toHaveCount(0);
  });

  await test.step("el seamanbook vencido se avisa, pero no impide enviar", async () => {
    await ficha.getByLabel("Vence el seamanbook *").fill(fechaPanama(0));
    await expect(ficha.getByText(/^El seamanbook vence el .*Puedes enviar la solicitud igual/)).toBeVisible();
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    // La lista de lo que falta sigue (el resto de la ficha está vacío), pero sin el seamanbook.
    const pendientes = agencia.getByRole("alert").filter({ hasText: "Elige el puesto de Control Migratorio." }).first();
    await expect(pendientes).toBeVisible();
    await expect(pendientes).not.toContainText("seamanbook vence");
  });
});

test("bandera, país de nacimiento y nacionalidad se eligen con buscador", async ({ browser }) => {
  const agencia = await entrar(browser, CUENTAS.agencia);
  await agencia.goto("/new");
  await agencia.getByRole("button", { name: /^Embarque/ }).click();

  const bandera = agencia.getByRole("combobox", { name: "Bandera *" });
  const opciones = await opcionesDe(bandera);

  await test.step("sin tildes ni mayúsculas, y lo que empieza por lo escrito va primero", async () => {
    await bandera.fill("PAN");
    await expect(bandera).toHaveAttribute("aria-expanded", "true");
    // El código exacto, después lo que contiene «pan» (España, Japón no: «japon»).
    await expect(opciones).toHaveText([/^Panamá/, /^España/]);
    await bandera.fill("japon");
    await expect(opciones).toHaveText([/^Japón/]);
    await bandera.fill("xyz");
    await expect(opciones).toHaveCount(0);
    await expect(agencia.getByText("Sin coincidencias con «xyz»")).toBeVisible();
  });

  await test.step("con el teclado: escribir, flechas y Enter; Escape no cambia nada", async () => {
    await bandera.fill("pa");
    await agencia.keyboard.press("ArrowDown");   // de Panamá a la siguiente
    const segunda = await opciones.nth(1).innerText();
    await agencia.keyboard.press("Enter");
    await expect(bandera).toHaveValue(segunda);
    await expect(bandera).toHaveAttribute("aria-expanded", "false");

    await bandera.fill("alem");
    await agencia.keyboard.press("Escape");
    await expect(bandera).toHaveValue(segunda);
  });

  await test.step("al salir sin elegir, vale lo escrito solo si no hay duda", async () => {
    await elegirPais(bandera, "Panamá");
    await bandera.fill("es");                      // varias: queda la que había
    await agencia.getByLabel("Nombre del buque *").click();
    await expect(bandera).toHaveValue("Panamá");
    await bandera.fill("venezu");                  // una sola: vale
    await agencia.getByLabel("Nombre del buque *").click();
    await expect(bandera).toHaveValue("Venezuela");
  });

  await test.step("los del pasajero, con Tab", async () => {
    const nacimiento = tarjeta(agencia, 0).getByRole("combobox", { name: "País de nacimiento *" });
    await nacimiento.fill("colom");
    await agencia.keyboard.press("Tab");
    await expect(nacimiento).toHaveValue("Colombia");
    // El foco pasó al campo siguiente, la nacionalidad.
    const nacionalidad = tarjeta(agencia, 0).getByRole("combobox", { name: "Nacionalidad *" });
    await expect(nacionalidad).toBeFocused();
    await agencia.keyboard.type("filip");
    await agencia.keyboard.press("Enter");
    await expect(nacionalidad).toHaveValue("Filipinas");
  });
});
