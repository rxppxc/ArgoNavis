/**
 * Recorrido completo de una autorización, como en la demo: la agencia envía,
 * UCVMM la ve en su campana, la verifica y la devuelve, la agencia lo ve en la
 * suya y corrige, UCVMM aprueba, la agencia descarga el PDF, un tercero
 * verifica el QR, el puesto verifica los impedimentos y finaliza, y el
 * Administrador lo ve en la bitácora.
 */
import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { expect, test } from "./base";
import { CUENTAS, NOMBRE_REVISOR, PUESTO, entrar, fechaPanama, pdf } from "./datos";

const TRIPULANTE = "Juan Carlos Pérez Gómez";
/** Una «palabra» más larga que cualquier caja, como el «pruebasssss…» que se
 *  salía de las observaciones y del historial (2026-11-08). */
const SIN_ESPACIOS = `prueba${"s".repeat(300)}`;

/** La insignia de estado del expediente. */
const estado = (pagina: Page, texto: string) => pagina.getByText(texto, { exact: true }).first();

/** Ningún texto que contenga SIN_ESPACIOS se sale de su caja. No basta con mirar
 *  si la página se desborda: el área central recorta lo que sobresale (overflow:
 *  clip), así que se revisa caja por caja (la más interna que lo contiene). */
async function sinTextoDesbordado(pagina: Page) {
  const desbordadas = await pagina.evaluate((pedazo) => {
    const fuera: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("body *"))) {
      if (!el.textContent?.includes(pedazo)) continue;
      if (Array.from(el.children).some((hijo) => hijo.textContent?.includes(pedazo))) continue;
      const estilo = getComputedStyle(el);
      // Una línea en línea no tiene ancho propio; lo recortado a propósito (…) no cuenta.
      const caja = estilo.display === "inline" ? el.parentElement : el;
      if (!caja || getComputedStyle(caja).overflowX !== "visible") continue;
      if (caja.scrollWidth > caja.clientWidth + 1) fuera.push(`${caja.tagName}.${caja.className}`);
    }
    return fuera;
  }, SIN_ESPACIOS.slice(0, 40));
  expect(desbordadas, "texto largo sin espacios que se sale de su caja").toEqual([]);
}

/** Nada de lo que ve la agencia nombra a las unidades internas (2026-11-11): ni en el
 *  texto ni en los atributos (title, aria-label, placeholder) de lo que hay en pantalla. */
async function sinUnidadesInternas(pagina: Page) {
  expect(await pagina.locator("body").innerHTML(), "la agencia no ve unidades internas del SNM")
    .not.toMatch(/UCVMM|Sector (Pacífico|Atlántico)/i);
}

/** Marca al tripulante «Sin impedimento» y guarda la verificación (de UCVMM o del puesto). */
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
    await agencia.getByRole("textbox", { name: "Observaciones", exact: true })
      .fill(`Se sube la documentación, ${SIN_ESPACIOS}`);
    await sinUnidadesInternas(agencia);   // el formulario, con su checklist
    await agencia.getByRole("button", { name: "Enviar solicitud" }).click();
    await agencia.waitForURL(/\/solicitudes\/\d+$/);
    id = agencia.url().split("/").pop() ?? "";
    await expect(estado(agencia, "En revisión")).toBeVisible();
    await sinTextoDesbordado(agencia);   // las observaciones y el historial
    await expect(agencia.getByText(/^En revisión por el Servicio Nacional de Migración/)).toBeVisible();
    await sinUnidadesInternas(agencia);
  });

  await test.step("UCVMM la ve en su campana y el enlace abre «Por revisar»", async () => {
    await ucvmm.goto("/dashboard");
    await expect(ucvmm).toHaveTitle(/^\(\d+\) /);   // los pendientes, también en la pestaña del navegador
    await ucvmm.getByRole("button", { name: /^Notificaciones:/ }).click();
    await expect(ucvmm.locator(`#panel-notificaciones a[href="/solicitudes/${id}"]`)).toContainText("Enviada · En revisión");
    await ucvmm.locator("#panel-notificaciones").getByRole("link", { name: /^Por revisar/ }).click();
    await expect(ucvmm).toHaveURL(/bandeja=revision&estado=review/);
    await expect(ucvmm.getByRole("tab", { name: /^Por revisar/ })).toHaveAttribute("aria-selected", "true");
  });

  await test.step("UCVMM verifica los impedimentos y la devuelve", async () => {
    await ucvmm.goto(`/solicitudes/${id}`);
    await verificarSinImpedimento(ucvmm);
    await ucvmm.getByRole("button", { name: "Devolver a corrección" }).click();
    const modal = ucvmm.getByRole("dialog");
    await modal.locator("textarea").fill(`La visa especial de marino está ilegible. ${SIN_ESPACIOS}`);
    await modal.getByRole("button", { name: "Devolver" }).click();
    await expect(estado(ucvmm, "En corrección")).toBeVisible();
    // El aviso lleva el sello del estado al que pasó, el número y el plazo (2026-11-11).
    const aviso = ucvmm.getByRole("status").locator("> div").filter({ hasText: "Devuelta" });
    await expect(aviso.getByText("Devuelta", { exact: true })).toBeVisible();
    await expect(aviso).toContainText(/AM-\d{4}-\d+ devuelta a la agencia\. Tiene hasta el .+ para corregirla\./);
    // Con el mouse encima, su tiempo se detiene; y se cierra con «Cerrar aviso».
    await aviso.hover();
    const barra = aviso.locator("[data-movimiento]");
    const tiempo = () => barra.evaluate((e) => Number(e.getAnimations()[0]?.currentTime ?? -1));
    await ucvmm.waitForTimeout(150);
    const antes = await tiempo();
    await ucvmm.waitForTimeout(600);
    expect(await tiempo(), "con el mouse encima, el tiempo del aviso no corre").toBe(antes);
    await aviso.getByRole("button", { name: "Cerrar aviso" }).click();
    await expect(aviso).toHaveCount(0);
    await sinTextoDesbordado(ucvmm);   // el motivo, en el aviso y en el historial
  });

  await test.step("la agencia ve la devolución en su campana y, al abrirla, queda leída", async () => {
    await agencia.goto("/dashboard");
    const campana = agencia.getByRole("button", { name: /^Notificaciones:/ });
    await expect(campana).toHaveAccessibleName(/sin leer/);
    await campana.click();
    const panel = agencia.locator("#panel-notificaciones");
    await expect(panel.getByRole("link", { name: /^Por corregir/ })).toBeVisible();
    const novedad = panel.locator(`a[href="/solicitudes/${id}"]`);
    await expect(novedad).toContainText("Devuelta a corrección");
    await expect(novedad).toContainText("La visa especial de marino está ilegible.");
    await expect(novedad).toContainText("Servicio Nacional de Migración");   // quién la devolvió, sin nombres
    await sinUnidadesInternas(agencia);   // la bandeja y la campana abierta
    await expect(campana).not.toHaveAccessibleName(/sin leer/);
    await agencia.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
  });

  await test.step("la agencia corrige: reemplaza la visa y reenvía", async () => {
    await agencia.goto(`/solicitudes/${id}`);
    // El motivo sale en el aviso de la devolución y en el historial.
    await expect(agencia.getByText("La visa especial de marino está ilegible.").first()).toBeVisible();
    await sinTextoDesbordado(agencia);
    await sinUnidadesInternas(agencia);   // el expediente devuelto, con su historial
    await agencia.getByRole("link", { name: "Corregir solicitud" }).click();
    await expect(agencia.getByText("Corrige lo indicado en la devolución y reenvía.", { exact: false })).toBeVisible();
    await sinUnidadesInternas(agencia);   // el formulario de la corrección
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

  await test.step("la agencia ve a la institución, no al funcionario ni a UCVMM, y descarga el PDF", async () => {
    await agencia.goto(`/solicitudes/${id}`);
    await expect(estado(agencia, "Aprobada")).toBeVisible();
    await expect(agencia.getByText(/por el Servicio Nacional de Migración\. Vigente hasta/)).toBeVisible();
    await expect(agencia.getByText(NOMBRE_REVISOR)).toHaveCount(0);
    await sinUnidadesInternas(agencia);
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

  await test.step("el puesto de control verifica los impedimentos y finaliza", async () => {
    const puesto = await entrar(browser, CUENTAS.puesto);
    await puesto.goto(`/solicitudes/${id}`);
    await puesto.getByLabel("Comentario de la operación *").fill("Embarque realizado sin novedad.");
    // Sin la verificación del puesto no se finaliza (la de UCVMM no cuenta).
    await expect(puesto.getByRole("button", { name: "Finalizar", exact: true })).toBeDisabled();
    await verificarSinImpedimento(puesto);
    await puesto.getByRole("button", { name: "Finalizar", exact: true }).click();
    await puesto.getByRole("dialog").getByRole("button", { name: "Finalizar" }).click();
    await expect(estado(puesto, "Finalizada")).toBeVisible();

    const tercero = await (await browser.newContext()).newPage();
    await tercero.goto(`/verificar/${codigo}`);
    await expect(tercero.getByText("Autorización auténtica — operación finalizada")).toBeVisible();
  });

  await test.step("sectores: UCVMM del Atlántico no la ve y la supervisión general la ve sin decidir", async () => {
    // El puesto de las pruebas es del Sector Pacífico (servidor_e2e.py).
    const atlantico = await entrar(browser, CUENTAS.atlantico);
    await atlantico.goto(`/solicitudes/${id}`);
    await expect(atlantico.getByText("No tienes acceso a esta solicitud.")).toBeVisible();
    await atlantico.goto("/dashboard?bandeja=revision&estado=todas");
    await expect(atlantico.getByText("No hay solicitudes aquí")).toBeVisible();

    const supervisor = await entrar(browser, CUENTAS.supervisor);
    await supervisor.goto("/dashboard");
    await expect(supervisor.getByText("Solicitudes de los dos sectores, en solo lectura")).toBeVisible();
    await supervisor.goto(`/solicitudes/${id}`);
    await expect(estado(supervisor, "Finalizada")).toBeVisible();
    await expect(supervisor.getByText("Sector Pacífico", { exact: true })).toBeVisible();
    await expect(supervisor.getByRole("button", { name: /^(Aprobar|Devolver|Denegar|Finalizar|Guardar verificación)/ }))
      .toHaveCount(0);
  });

  await test.step("UCVMM la encuentra en la consulta histórica por el pasajero y la exporta a Excel", async () => {
    await ucvmm.goto("/dashboard");
    await ucvmm.getByRole("link", { name: "Consulta histórica" }).click();
    await expect(ucvmm.getByRole("heading", { name: "Consulta histórica" })).toBeVisible();
    await ucvmm.getByLabel("Pasajero").fill("Pérez Gómez");
    await ucvmm.getByLabel("Año").selectOption(String(new Date().getFullYear()));
    await ucvmm.getByRole("tab", { name: /^Finalizadas/ }).click();
    const fila = ucvmm.locator(`a[href="/solicitudes/${id}"]`);
    await expect(fila).toBeVisible();
    await expect(ucvmm).toHaveURL(/pasajero=P%C3%A9rez/);   // la búsqueda queda en la URL
    const [descarga] = await Promise.all([
      ucvmm.waitForEvent("download"),
      ucvmm.getByRole("button", { name: "Exportar a Excel" }).click(),
    ]);
    expect(descarga.suggestedFilename()).toMatch(/^Consulta-historica-\d{4}-\d{2}-\d{2}\.xlsx$/);
    // Un pasajero que no está: sin resultados.
    await ucvmm.getByLabel("Pasajero").fill("Nadie Inexistente");
    await expect(ucvmm.getByText("Ninguna solicitud coincide con los filtros.")).toBeVisible();
    // La agencia usa su bandeja: la consulta es del personal del SNM.
    await agencia.goto("/historico");
    await expect(agencia).toHaveURL(/\/dashboard/);
    await agencia.goto(`/solicitudes/${id}`);
    await expect(estado(agencia, "Finalizada")).toBeVisible();
    await sinUnidadesInternas(agencia);   // el expediente ya finalizado
  });

  await test.step("el Administrador ve usuarios y la bitácora", async () => {
    const admin = await entrar(browser, CUENTAS.admin);
    await admin.goto("/admin");
    await expect(admin.getByText(`@${CUENTAS.agencia}`)).toBeVisible();
    await admin.goto("/admin/bitacora");
    await expect(admin.getByRole("cell", { name: "Solicitud finalizada" }).first()).toBeVisible();
  });
});
