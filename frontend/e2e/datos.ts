/** Cuentas y catálogos que siembra backend/tests/servidor_e2e.py (solo existen
 *  en su BD temporal). Si cambias uno, cambia el otro. */
import { expect, type Browser, type Locator, type Page } from "@playwright/test";

export const CLAVE = "Prueba-E2e-2026!";
export const PUESTO = "Puesto E2E";
/** Para el cambio de puerto (2026-11-13): otro puesto del mismo sector y uno del otro. */
export const PUESTO_MISMO_SECTOR = "Puesto E2E Rodman";
export const PUESTO_OTRO_SECTOR = "Puesto E2E Atlántico";
export const CUENTAS = {
  agencia:    "e2e.agencia",
  ucvmm:      "e2e.ucvmm",        // Sector Pacífico, el del puesto de las pruebas
  atlantico:  "e2e.atlantico",    // UCVMM del Sector Atlántico: no ve las del Pacífico
  supervisor: "e2e.supervisor",   // Supervisor general: ve todo, sin decidir
  puesto:     "e2e.puesto",
  admin:      "e2e.admin",
} as const;
/** Nombre completo del revisor de UCVMM: la agencia no debe verlo. */
export const NOMBRE_REVISOR = "Ricardo Revisor";

/** Una sesión propia por rol: cada contexto del navegador tiene su localStorage. */
export async function entrar(navegador: Browser, usuario: string): Promise<Page> {
  const pagina = await (await navegador.newContext()).newPage();
  await iniciarSesion(pagina, usuario);
  return pagina;
}

/** Entra en esa página; las demás pestañas de su contexto comparten la sesión. */
export async function iniciarSesion(pagina: Page, usuario: string): Promise<void> {
  await pagina.goto("/login");
  await pagina.getByLabel("Usuario").fill(usuario);
  await pagina.getByLabel("Contraseña", { exact: true }).fill(CLAVE);
  await pagina.getByRole("button", { name: "Iniciar sesión" }).click();
  await pagina.waitForURL(/\/(dashboard|admin)$/);
}

/** Fecha AAAA-MM-DD en Panamá, desplazada `dias` desde hoy. */
export function fechaPanama(dias = 0): string {
  const fecha = new Date(Date.now() + dias * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Panama" }).format(fecha);
}

/** Las opciones de un selector con buscador: las de su lista (aria-controls), no las de
 *  los <select> de la página, que también son «option». */
export async function opcionesDe(campo: Locator): Promise<Locator> {
  const lista = await campo.getAttribute("aria-controls");
  return campo.page().locator(`[id="${lista}"]`).getByRole("option");
}

/** Elige un país en un selector con buscador (bandera, país de nacimiento, nacionalidad;
 *  2026-11-13): escribe parte del nombre y pulsa su opción en la lista. El campo se
 *  busca por su rol: `getByLabel` encuentra también la lista, que lleva el mismo rótulo. */
export async function elegirPais(campo: Locator, nombre: string, buscar = nombre.slice(0, 4)): Promise<void> {
  await campo.fill(buscar);
  await (await opcionesDe(campo)).filter({ hasText: new RegExp(`^${nombre}$`) }).click();
  await expect(campo).toHaveValue(nombre);
}

/** Un PDF mínimo: el backend comprueba la firma %PDF- y el tamaño. */
export function pdf(nombre: string) {
  return { name: nombre, mimeType: "application/pdf", buffer: Buffer.from(`%PDF-1.4\n% ${nombre}\n%%EOF\n`) };
}
