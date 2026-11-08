import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { usePendientes } from "../hooks/usePendientes";
import { ETIQUETA_EVENTO, formatearFechaHora } from "../modulos/solicitudes/presentacion";
import { IconoCampana } from "./Iconos";
import styles from "./CampanaPendientes.module.css";

const cuantos = (n: number, uno: string, varios: string) => (n === 1 ? `1 ${uno}` : `${n} ${varios}`);

/** Notificaciones internas (reunión del 30/10/2026): lo que le toca hacer al
 *  usuario, con enlace a su bandeja, y las novedades de sus solicitudes. El
 *  número es el de pendientes; el punto, novedades sin leer. Abrirla las deja
 *  leídas. El SysAdmin no trabaja solicitudes: no la ve. */
export function CampanaPendientes() {
  const { datos, total, marcarVistas } = usePendientes();
  const [abierto, setAbierto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const refBoton = useRef<HTMLButtonElement>(null);

  // Como el menú: clic afuera cierra; Escape cierra y devuelve el foco al botón.
  useEffect(() => {
    if (!abierto) return;
    function clickFuera(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false);
    }
    function alTeclear(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setAbierto(false);
      refBoton.current?.focus();
    }
    document.addEventListener("mousedown", clickFuera);
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("mousedown", clickFuera);
      document.removeEventListener("keydown", alTeclear);
    };
  }, [abierto]);

  if (!datos?.disponible) return null;
  const sinLeer = datos.no_leidas;
  const conPendientes = datos.pendientes.filter((p) => p.cantidad > 0);
  const etiqueta = `Notificaciones: ${cuantos(total, "pendiente", "pendientes")}`
    + (sinLeer > 0 ? `, ${cuantos(sinLeer, "novedad sin leer", "novedades sin leer")}` : "");

  function alternar() {
    const abrir = !abierto;
    setAbierto(abrir);
    if (abrir && sinLeer > 0) void marcarVistas();
  }
  const cerrar = () => setAbierto(false);

  return (
    // Al salir con Tab del panel, se cierra (como el menú).
    <div className={styles.dropdown} ref={ref}
      onBlur={(e) => { if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setAbierto(false); }}>
      <button ref={refBoton} type="button" className={`${styles.boton} ${abierto ? styles.botonAbierto : ""}`}
        onClick={alternar} aria-expanded={abierto} aria-controls="panel-notificaciones" aria-label={etiqueta}
        title="Notificaciones">
        <IconoCampana />
        {total > 0 && <span className={styles.numero} aria-hidden="true">{total > 99 ? "99+" : total}</span>}
        {sinLeer > 0 && <span className={styles.punto} aria-hidden="true" />}
      </button>

      {abierto && (
        <div className={styles.panel} id="panel-notificaciones">
          <h2 className={styles.titulo}>Pendientes</h2>
          {conPendientes.length === 0 ? <p className={styles.vacio}>No tienes pendientes.</p> : (
            <ul className={styles.lista}>
              {conPendientes.map((p) => (
                <li key={p.clave}>
                  <Link to={`/dashboard?bandeja=${p.bandeja}&estado=${p.estado}`} className={styles.item} onClick={cerrar}>
                    <span className={styles.itemFila}>
                      <span className={styles.itemTitulo}>{p.texto}</span>
                      <span className={styles.cantidad}>{p.cantidad}</span>
                    </span>
                    {p.vence_en && <span className={styles.detalle}>La más próxima vence el {formatearFechaHora(p.vence_en)}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <div className={styles.sep} />
          <h2 className={styles.titulo}>Novedades</h2>
          {datos.novedades.length === 0 ? <p className={styles.vacio}>Nada nuevo en los últimos 30 días.</p> : (
            <ul className={styles.lista}>
              {datos.novedades.map((n) => (
                <li key={n.id}>
                  <Link to={`/solicitudes/${n.solicitud_id}`} className={`${styles.item} ${n.no_leida ? styles.noLeida : ""}`}
                    onClick={cerrar}>
                    <span className={styles.itemTitulo}>
                      {n.no_leida && <span className="sr-only">Sin leer: </span>}
                      {n.numero ?? `Solicitud ${n.solicitud_id}`} · {ETIQUETA_EVENTO[n.tipo]}
                    </span>
                    <span className={styles.detalle}>{n.titulo}</span>
                    {n.comentario && <span className={styles.comentario}>{n.comentario}</span>}
                    <span className={styles.detalle}>
                      {formatearFechaHora(n.creado_en)}{n.usuario_nombre && ` · ${n.usuario_nombre}`}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
