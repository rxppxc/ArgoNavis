/**
 * Dónde vive el borrador de una solicitud nueva (2026-11-23): en IndexedDB, que guarda también
 * los archivos (localStorage solo guarda texto). Dos registros por usuario:
 * - los datos, que se guardan con cada cambio;
 * - los archivos, solo cuando cambian: cada vez que se guarda un archivo se copia entero.
 * Si el navegador no lo permite (ventana privada, datos del sitio bloqueados), no hay borrador
 * y el formulario funciona igual.
 */
import type { ArchivosBorrador, DatosBorrador } from "./borradorSolicitud";

const BASE = "argonavis-borradores";
const ALMACEN = "borradores";

interface Registro<T> {
  valor:      T;
  guardadoEn: number;
}

export interface BorradorGuardado {
  datos:      DatosBorrador;
  archivos:   ArchivosBorrador;
  guardadoEn: number;
}

let avisado = false;
function avisar(error: unknown) {
  if (avisado) return;
  avisado = true;
  console.warn("[borrador] El navegador no deja guardar el borrador de la solicitud:", error);
}

function abrir(): Promise<IDBDatabase> {
  return new Promise((resolver, rechazar) => {
    const pedido = indexedDB.open(BASE, 1);
    pedido.onupgradeneeded = () => { pedido.result.createObjectStore(ALMACEN); };
    pedido.onsuccess = () => resolver(pedido.result);
    pedido.onerror = () => rechazar(pedido.error);
    pedido.onblocked = () => rechazar(new Error("La base de borradores está bloqueada por otra pestaña."));
  });
}

/** Una transacción: resuelve cuando termina, con el resultado del pedido que se devuelva. */
async function operar<T>(modo: IDBTransactionMode, hacer: (almacen: IDBObjectStore) => IDBRequest | undefined): Promise<T | undefined> {
  const base = await abrir();
  try {
    return await new Promise<T | undefined>((resolver, rechazar) => {
      const tx = base.transaction(ALMACEN, modo);
      const pedido = hacer(tx.objectStore(ALMACEN));
      tx.oncomplete = () => resolver(pedido ? (pedido.result as T) : undefined);
      tx.onerror = () => rechazar(tx.error);
      tx.onabort = () => rechazar(tx.error);
    });
  } finally {
    base.close();
  }
}

export async function leerBorrador(clave: string): Promise<BorradorGuardado | null> {
  try {
    const datos = await operar<Registro<DatosBorrador>>("readonly", (a) => a.get(`${clave}:datos`));
    if (!datos) return null;
    const archivos = await operar<Registro<ArchivosBorrador>>("readonly", (a) => a.get(`${clave}:archivos`));
    return {
      datos: datos.valor,
      archivos: archivos?.valor ?? { nuevos: {}, adicionales: [] },
      guardadoEn: Math.max(datos.guardadoEn, archivos?.guardadoEn ?? 0),
    };
  } catch (error) {
    avisar(error);
    return null;
  }
}

/** Devuelve si se guardó. */
export async function guardarDatos(clave: string, datos: DatosBorrador, guardadoEn: number): Promise<boolean> {
  try {
    await operar("readwrite", (a) => a.put({ valor: datos, guardadoEn } satisfies Registro<DatosBorrador>, `${clave}:datos`));
    return true;
  } catch (error) {
    avisar(error);
    return false;
  }
}

export async function guardarArchivos(clave: string, archivos: ArchivosBorrador, guardadoEn: number): Promise<boolean> {
  try {
    await operar("readwrite", (a) => a.put({ valor: archivos, guardadoEn } satisfies Registro<ArchivosBorrador>, `${clave}:archivos`));
    return true;
  } catch (error) {
    avisar(error);
    return false;
  }
}

export async function borrarBorrador(clave: string): Promise<void> {
  try {
    await operar("readwrite", (a) => {
      a.delete(`${clave}:datos`);
      a.delete(`${clave}:archivos`);
      return undefined;
    });
  } catch (error) {
    avisar(error);
  }
}
