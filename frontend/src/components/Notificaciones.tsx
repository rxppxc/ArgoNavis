/**
 * Sistema de notificaciones flotantes (estilo "toast").
 *
 * Reemplaza los `alert()` y `console.error()` con mensajes no bloqueantes
 * que se apilan en la esquina superior derecha y se cierran solos a los
 * pocos segundos. Soporta tipos visuales: éxito, error, aviso, info.
 *
 * Uso:
 *   const { mostrar } = useNotificacion();
 *   mostrar("Usuario creado", "exito");
 *   mostrar("Error al guardar", "error");
 *   mostrar("Procesando…", "info", 0);  // 0 = no auto-cierre
 */
import {
  createContext, useCallback, useContext, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";
import { IconoX } from "./Iconos";
import styles from "./Notificaciones.module.css";

export type TipoNotificacion = "exito" | "error" | "info" | "aviso";

interface Mensaje {
  id: number;
  texto: string;
  tipo: TipoNotificacion;
}

interface ContextoNotificaciones {
  mostrar: (texto: string, tipo?: TipoNotificacion, duracionMs?: number) => void;
}

const Contexto = createContext<ContextoNotificaciones | null>(null);

// eslint-disable-next-line react-refresh/only-export-components -- el hook va junto a su proveedor; separarlos solo cambiaría las rutas de import
export function useNotificacion(): ContextoNotificaciones {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useNotificacion debe usarse dentro de <ProveedorNotificaciones>");
  return ctx;
}

export function ProveedorNotificaciones({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Mensaje[]>([]);
  const idRef = useRef(1);

  const cerrar = useCallback((id: number) => {
    setItems(prev => prev.filter(m => m.id !== id));
  }, []);

  const mostrar = useCallback(
    (texto: string, tipo: TipoNotificacion = "info", duracionMs = 4000) => {
      const id = idRef.current++;
      setItems(prev => [...prev, { id, texto, tipo }]);
      if (duracionMs > 0) {
        window.setTimeout(() => cerrar(id), duracionMs);
      }
    },
    [cerrar]
  );

  const valor = useMemo(() => ({ mostrar }), [mostrar]);

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className={styles.contenedor} role="status" aria-live="polite">
        {items.map(m => (
          <ItemNotificacion key={m.id} mensaje={m} onCerrar={() => cerrar(m.id)} />
        ))}
      </div>
    </Contexto.Provider>
  );
}

function ItemNotificacion({ mensaje, onCerrar }: { mensaje: Mensaje; onCerrar: () => void }) {
  return (
    <div className={`${styles.toast} ${styles[mensaje.tipo]}`}>
      <span className={styles.texto}>{mensaje.texto}</span>
      <button type="button" className={styles.cerrar} onClick={onCerrar} aria-label="Cerrar aviso">
        <IconoX tamano={14} />
      </button>
    </div>
  );
}
