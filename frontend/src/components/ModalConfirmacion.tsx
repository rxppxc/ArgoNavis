/**
 * Modal de confirmación no bloqueante (reemplaza `window.confirm`).
 *
 * Uso:
 *   const confirmar = useConfirmar();
 *   const ok = await confirmar({ titulo: "¿Eliminar?", mensaje: "Esta acción no se puede deshacer." });
 *   if (!ok) return;
 *
 * Beneficios sobre `confirm()`:
 *   - No bloquea el event loop ni el render del navegador.
 *   - Estilo coherente con el resto de la UI.
 *   - Accesible: Esc cancela y Enter activa el botón con el foco (al abrir,
 *     el de confirmar). Antes Enter confirmaba siempre, aunque el foco
 *     estuviera en "Cancelar": se podía eliminar algo queriendo cancelar.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";
import { useAtraparFoco } from "../hooks/useAtraparFoco";
import styles from "./ModalConfirmacion.module.css";

interface OpcionesConfirmacion {
  titulo?:        string;
  mensaje:        ReactNode;
  textoOk?:       string;
  textoCancelar?: string;
  peligroso?:     boolean;
  /** Botón verde: para confirmar una aprobación (como el botón que la inició). */
  exito?:         boolean;
  /** Otros colores de acción (Botones.module.css): verde azulado para
   *  finalizar, morado para restablecer una contraseña. */
  tono?:          "finalizar" | "clave";
}

function claseConfirmar(o: OpcionesConfirmacion): string {
  if (o.peligroso) return styles.btnPeligro;
  if (o.exito) return styles.btnExito;
  if (o.tono === "finalizar") return styles.btnFinalizar;
  if (o.tono === "clave") return styles.btnClave;
  return styles.btnConfirmar;
}

type Resolver = (decision: boolean) => void;

const Contexto = createContext<((opt: OpcionesConfirmacion) => Promise<boolean>) | null>(null);

// eslint-disable-next-line react-refresh/only-export-components -- el hook va junto a su proveedor; separarlos solo cambiaría las rutas de import
export function useConfirmar() {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useConfirmar debe usarse dentro de <ProveedorConfirmacion>");
  return ctx;
}

export function ProveedorConfirmacion({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<OpcionesConfirmacion | null>(null);
  const resolverRef = useRef<Resolver | null>(null);

  const confirmar = useCallback((opt: OpcionesConfirmacion): Promise<boolean> => {
    setEstado(opt);
    return new Promise<boolean>(resolve => { resolverRef.current = resolve; });
  }, []);

  const responder = useCallback((decision: boolean) => {
    resolverRef.current?.(decision);
    resolverRef.current = null;
    setEstado(null);
  }, []);

  useEffect(() => {
    if (!estado) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") responder(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [estado, responder]);

  const valor = useMemo(() => confirmar, [confirmar]);
  const refModal = useAtraparFoco(!!estado);

  return (
    <Contexto.Provider value={valor}>
      {children}
      {estado && (
        <div className={styles.overlay} onClick={() => responder(false)}>
          <div
            ref={refModal}
            className={styles.modal}
            onClick={e => e.stopPropagation()}
            role={estado.peligroso ? "alertdialog" : "dialog"}
            aria-modal="true"
            aria-labelledby={estado.titulo ? "confirmacion-titulo" : undefined}
            aria-describedby="confirmacion-mensaje"
          >
            {estado.titulo && <h3 id="confirmacion-titulo" className={styles.titulo}>{estado.titulo}</h3>}
            <div id="confirmacion-mensaje" className={styles.mensaje}>{estado.mensaje}</div>
            <div className={styles.acciones}>
              <button type="button" className={styles.btnCancelar} onClick={() => responder(false)}>
                {estado.textoCancelar ?? "Cancelar"}
              </button>
              <button
                type="button"
                className={claseConfirmar(estado)}
                onClick={() => responder(true)}
                data-focus-inicial
              >
                {estado.textoOk ?? "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Contexto.Provider>
  );
}
