/** Cuentas y catálogos que siembra backend/tests/servidor_e2e.py (solo existen
 *  en su BD temporal). Si cambias uno, cambia el otro. */
import type { Browser, Page } from "@playwright/test";

export const CLAVE = "Prueba-E2e-2026!";
export const PUESTO = "Puesto E2E";
export const CUENTAS = {
  agencia: "e2e.agencia",
  ucvmm:   "e2e.ucvmm",
  puesto:  "e2e.puesto",
  admin:   "e2e.admin",
} as const;
/** Nombre completo del revisor de UCVMM: la agencia no debe verlo. */
export const NOMBRE_REVISOR = "Ricardo Revisor";

/** Una sesión propia por rol: cada contexto del navegador tiene su localStorage. */
export async function entrar(navegador: Browser, usuario: string): Promise<Page> {
  const pagina = await (await navegador.newContext()).newPage();
  await pagina.goto("/login");
  await pagina.getByLabel("Usuario").fill(usuario);
  await pagina.getByLabel("Contraseña", { exact: true }).fill(CLAVE);
  await pagina.getByRole("button", { name: "Iniciar sesión" }).click();
  await pagina.waitForURL(/\/(dashboard|admin)$/);
  return pagina;
}

/** Fecha AAAA-MM-DD en Panamá, desplazada `dias` desde hoy. */
export function fechaPanama(dias = 0): string {
  const fecha = new Date(Date.now() + dias * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Panama" }).format(fecha);
}

/** Un PDF mínimo: el backend comprueba la firma %PDF- y el tamaño. */
export function pdf(nombre: string) {
  return { name: nombre, mimeType: "application/pdf", buffer: Buffer.from(`%PDF-1.4\n% ${nombre}\n%%EOF\n`) };
}
