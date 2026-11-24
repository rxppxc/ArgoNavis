/**
 * Dónde vive el borrador de una solicitud nueva (2026-11-23): en IndexedDB, que guarda también
 * los archivos (localStorage solo guarda texto). Dos registros por usuario, que se escriben en la
 * misma transacción: los datos, con cada guardado, y los archivos, solo cuando cambian (cada vez
 * se copian enteros). Los archivos van como su contenido (`serializarArchivos`), no como `File`.
 *
 * Las operaciones van en fila, en el orden en que se piden: leer al volver al formulario espera a
 * que termine lo que se guardaba al salir, y borrar, a lo que se estaba guardando. En la CI, el
 * adjunto no llegaba al borrador cuando se volvía justo después de salir (2026-11-24).
 *
 * Si el navegador no lo permite (ventana privada sin IndexedDB, datos del sitio bloqueados), no
 * hay borrador y el formulario funciona igual.
 */
import {
  recuperarArchivos, serializarArchivos, type ArchivosBorrador, type ArchivosGuardados, type DatosBorrador,
} from "./borradorSolicitud";

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

let fila: Promise<unknown> = Promise.resolve();
/** Cada operación empieza cuando terminó la anterior (ninguna rechaza: atrapan sus errores). */
function enFila<T>(operacion: () => Promise<T>): Promise<T> {
  const resultado = fila.then(operacion);
  fila = resultado.catch(() => undefined);
  return resultado;
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

/** Una transacción: resuelve cuando termina, con los resultados de los pedidos que se devuelvan. */
async function operar(modo: IDBTransactionMode, hacer: (almacen: IDBObjectStore) => IDBRequest[]): Promise<unknown[]> {
  const base = await abrir();
  try {
    return await new Promise<unknown[]>((resolver, rechazar) => {
      const tx = base.transaction(ALMACEN, modo);
      const pedidos = hacer(tx.objectStore(ALMACEN));
      tx.oncomplete = () => resolver(pedidos.map((p) => p.result));
      tx.onerror = () => rechazar(tx.error);
      tx.onabort = () => rechazar(tx.error);
    });
  } finally {
    base.close();
  }
}

export function leerBorrador(clave: string): Promise<BorradorGuardado | null> {
  return enFila(async () => {
    try {
      const [datos, archivos] = await operar("readonly", (a) => [a.get(`${clave}:datos`), a.get(`${clave}:archivos`)]) as
        [Registro<DatosBorrador> | undefined, Registro<ArchivosGuardados> | undefined];
      if (!datos) return null;
      return {
        datos: datos.valor,
        archivos: archivos ? recuperarArchivos(archivos.valor) : { nuevos: {}, adicionales: [] },
        guardadoEn: Math.max(datos.guardadoEn, archivos?.guardadoEn ?? 0),
      };
    } catch (error) {
      avisar(error);
      return null;
    }
  });
}

/** Los datos y, si cambiaron (`archivos` no nulo), los archivos, juntos. Devuelve si se guardó. */
export function guardarBorrador(
  clave: string, datos: DatosBorrador, archivos: ArchivosBorrador | null, guardadoEn: number,
): Promise<boolean> {
  return enFila(async () => {
    try {
      // El contenido se lee antes de abrir la transacción: una que espera otra cosa se cierra sola.
      const guardados = archivos && await serializarArchivos(archivos);
      await operar("readwrite", (a) => [
        a.put({ valor: datos, guardadoEn } satisfies Registro<DatosBorrador>, `${clave}:datos`),
        ...(guardados ? [a.put({ valor: guardados, guardadoEn } satisfies Registro<ArchivosGuardados>, `${clave}:archivos`)] : []),
      ]);
      return true;
    } catch (error) {
      avisar(error);
      return false;
    }
  });
}

export function borrarBorrador(clave: string): Promise<void> {
  return enFila(async () => {
    try {
      await operar("readwrite", (a) => [a.delete(`${clave}:datos`), a.delete(`${clave}:archivos`)]);
    } catch (error) {
      avisar(error);
    }
  });
}
