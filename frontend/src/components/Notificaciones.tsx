/**
 * Avisos emergentes («toasts») de toda la aplicación, con el diseño «sello centrado»
 * (elegido por el usuario el 2026-11-11): una cinta centrada bajo la cabecera, del ancho
 * de su mensaje, con el sello de tinta del resultado a la izquierda, como los de las
 * bandejas (InsigniaEstado).
 *
 *  - El sello dice qué pasó: el estado al que pasó la solicitud (ENVIADA, REENVIADA,
 *    DEVUELTA, APROBADA, DENEGADA o FINALIZADA, en el color de su insignia) o, si no, el
 *    tipo: LISTO, REVISA (validación: tinta con el amarillo de la franja), NO SE PUDO y AVISO.
 *  - Una barra muestra el tiempo que queda y se detiene con el mouse encima o con el foco
 *    adentro: el aviso se cierra cuando termina su animación.
 *  - Como mucho tres a la vez, y uno repetido no se apila (avisos.ts).
 *  - Errores y validaciones van en una región `alert` (se anuncian enseguida); los éxitos,
 *    en una `status` (sin interrumpir). Las dos están siempre: una región que aparece junto
 *    con su texto no siempre se lee.
 *
 * Uso:
 *   const { mostrar } = useNotificacion();
 *   mostrar("Cambios guardados.", "exito");
 *   mostrar("Escribe el motivo.", "aviso");
 *   mostrar(`Solicitud ${numero} enviada a revisión.`, "exito", { sello: "enviada" });
 *   mostrar("Procesando…", "info", 0);   // 0 = no se cierra solo
 */
import {
  Fragment, createContext, useCallback, useContext, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";
import { IconoX } from "./Iconos";
import {
  agregarAviso, duracionDe, esUrgente, partesDelTexto, textoDelSello,
  type SelloSolicitud, type TipoNotificacion,
} from "./avisos";
import styles from "./Notificaciones.module.css";

export type { SelloSolicitud, TipoNotificacion } from "./avisos";

interface OpcionesAviso {
  /** 0 = no se cierra solo. Por defecto, según el tipo y el sello (avisos.ts). */
  duracionMs?: number;
  /** El estado al que pasó la solicitud: su sello, en lugar del del tipo. */
  sello?: SelloSolicitud;
}

interface Mensaje {
  id: number;
  texto: string;
  tipo: TipoNotificacion;
  sello?: SelloSolicitud;
  duracionMs: number;
}

interface ContextoNotificaciones {
  mostrar: (texto: string, tipo?: TipoNotificacion, opciones?: number | OpcionesAviso) => void;
}

const Contexto = createContext<ContextoNotificaciones | null>(null);

/** El color de cada sello de solicitud: el de la insignia del estado al que pasó. */
const CLASE_SELLO: Record<SelloSolicitud, string> = {
  enviada: styles.enRevision, reenviada: styles.enRevision, devuelta: styles.devuelta,
  aprobada: styles.aprobada, denegada: styles.denegada, finalizada: styles.finalizada,
};

/** Justo bajo la cabecera, que cambia de alto con el ancho de la pantalla; si ya se
 *  desplazó fuera de la vista (o no hay, como en el login), arriba. */
function debajoDeLaCabecera(): number {
  const borde = document.querySelector("[data-cabecera]")?.getBoundingClientRect().bottom ?? 0;
  return Math.max(12, Math.round(borde) + 10);
}

// eslint-disable-next-line react-refresh/only-export-components -- el hook va junto a su proveedor; separarlos solo cambiaría las rutas de import
export function useNotificacion(): ContextoNotificaciones {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useNotificacion debe usarse dentro de <ProveedorNotificaciones>");
  return ctx;
}

export function ProveedorNotificaciones({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Mensaje[]>([]);
  const [arriba, setArriba] = useState(12);
  const idRef = useRef(1);

  const cerrar = useCallback((id: number) => {
    setItems((prev) => prev.filter((m) => m.id !== id));
  }, []);

  const mostrar = useCallback(
    (texto: string, tipo: TipoNotificacion = "info", opciones?: number | OpcionesAviso) => {
      const { duracionMs, sello }: OpcionesAviso = typeof opciones === "number" ? { duracionMs: opciones } : opciones ?? {};
      const nuevo: Mensaje = { id: idRef.current++, texto, tipo, sello, duracionMs: duracionMs ?? duracionDe(tipo, sello) };
      setArriba(debajoDeLaCabecera());
      setItems((prev) => agregarAviso(prev, nuevo));
    },
    [],
  );

  const valor = useMemo(() => ({ mostrar }), [mostrar]);

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className={styles.contenedor} style={{ top: arriba }}>
        <div role="alert" aria-atomic="false" className={styles.grupo}>
          {items.filter((m) => esUrgente(m.tipo)).map((m) => (
            <Aviso key={m.id} mensaje={m} onCerrar={() => cerrar(m.id)} />
          ))}
        </div>
        <div role="status" aria-atomic="false" className={styles.grupo}>
          {items.filter((m) => !esUrgente(m.tipo)).map((m) => (
            <Aviso key={m.id} mensaje={m} onCerrar={() => cerrar(m.id)} />
          ))}
        </div>
      </div>
    </Contexto.Provider>
  );
}

function Aviso({ mensaje, onCerrar }: { mensaje: Mensaje; onCerrar: () => void }) {
  const clases = [styles.cinta, styles[mensaje.tipo], mensaje.sello ? CLASE_SELLO[mensaje.sello] : ""].join(" ");
  return (
    <div className={clases}>
      <span className={styles.columnaSello}>
        <span className={styles.sello}>{textoDelSello(mensaje.tipo, mensaje.sello)}</span>
      </span>
      <span className={styles.texto}>
        {partesDelTexto(mensaje.texto).map((parte, i) => (
          parte.numero ? <b key={i}>{parte.texto}</b> : <Fragment key={i}>{parte.texto}</Fragment>
        ))}
      </span>
      <button type="button" className={styles.cerrar} onClick={onCerrar} aria-label="Cerrar aviso">
        <span className={styles.cerrarTexto} aria-hidden="true">Cerrar</span>
        <IconoX tamano={15} />
      </button>
      {mensaje.duracionMs > 0 && (
        // Se cierra cuando la barra termina: así se detiene con el mouse encima o el foco
        // adentro. data-movimiento: corre aunque el equipo pida reducir movimiento (la
        // regla global la dejaría en 0 s y el aviso se cerraría al aparecer).
        <span className={styles.tiempo} data-movimiento="" aria-hidden="true"
          style={{ animationDuration: `${mensaje.duracionMs}ms` }} onAnimationEnd={onCerrar} />
      )}
    </div>
  );
}
