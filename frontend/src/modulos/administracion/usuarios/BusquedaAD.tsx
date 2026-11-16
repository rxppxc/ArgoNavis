import { useState } from "react";
import { apiAdmin, type UsuarioAD } from "../../../api/admin";
import { useNotificacion } from "../../../components/Notificaciones";
import { IconoBuscar, IconoCheck, IconoCorreo, IconoMaletin, IconoMas, IconoUsuario } from "../../../components/Iconos";
import { mensajeDeError } from "../../../utils/errores";
import styles from "../PaginaUsuarios.module.css";

interface Props {
  /** Los nombres de usuario ya registrados: esos dicen «Ya registrado». */
  registrados: Set<string>;
  /** Tras agregar a alguien, relee la lista de la página. */
  alAgregar: () => Promise<void>;
}

/** «Agregar un funcionario del Active Directory» (de PaginaUsuarios, 2026-11-14). */
export function BusquedaAD({ registrados, alAgregar }: Props) {
  const { mostrar: mostrarToast } = useNotificacion();
  const [busqueda,     setBusqueda]     = useState("");
  const [buscando,     setBuscando]     = useState(false);
  const [resultadosAD, setResultadosAD] = useState<UsuarioAD[]>([]);
  const [errorBusq,    setErrorBusq]    = useState<string | null>(null);
  const [creando,      setCreando]      = useState<string | null>(null);

  async function alBuscar(e: React.FormEvent) {
    e.preventDefault();
    const q = busqueda.trim();
    if (q.length < 2) {
      setErrorBusq("Escribe al menos 2 letras del nombre, el usuario o el correo.");
      return;
    }
    setBuscando(true);
    setErrorBusq(null);
    setResultadosAD([]);
    try {
      const { data } = await apiAdmin.buscarEnAD(q);
      setResultadosAD(data);
      if (data.length === 0) setErrorBusq("No se encontraron usuarios con ese criterio.");
    } catch (err) {
      setErrorBusq(mensajeDeError(err, "No se pudo consultar el Active Directory."));
    } finally {
      setBuscando(false);
    }
  }

  async function alCrear(username: string) {
    setCreando(username);
    try {
      await apiAdmin.crearUsuario(username);
      setResultadosAD(prev => prev.filter(u => u.username !== username));
      await alAgregar();
      mostrarToast(`Usuario ${username} agregado.`, "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "No se pudo agregar el usuario."), "error");
    } finally {
      setCreando(null);
    }
  }

  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <IconoBuscar />
        Agregar un funcionario del Active Directory
      </div>
      <div className={styles.panelBody}>
        <form onSubmit={alBuscar} className={styles.searchRow}>
          <input
            className={styles.searchInput}
            type="text"
            placeholder="Busca por nombre, usuario o correo del dominio…"
            aria-label="Buscar en Active Directory"
            maxLength={100}
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            autoFocus
          />
          <button
            type="submit"
            className={styles.searchBtn}
            disabled={buscando}
          >
            {buscando ? <span className={styles.spinner} /> : <IconoBuscar />}
            {buscando ? "Buscando…" : "Buscar"}
          </button>
        </form>

        {errorBusq && <p className={styles.searchError}>{errorBusq}</p>}

        {resultadosAD.length > 0 && (
          <div className={styles.adResults}>
            {resultadosAD.map(u => {
              const yaExiste = registrados.has(u.username);
              return (
                <div key={u.username} className={styles.adCard}>
                  <div className={styles.adAvatar}><IconoUsuario /></div>
                  <div className={styles.adInfo}>
                    <div className={styles.adName}>
                      {u.name || u.last_name ? `${u.name} ${u.last_name}`.trim() : u.username}
                    </div>
                    <div className={styles.adMeta}>
                      <span><IconoUsuario tamano={11} />{u.username}</span>
                      {u.email && <span><IconoCorreo />{u.email}</span>}
                      {u.department && <span><IconoMaletin />{u.department}</span>}
                    </div>
                  </div>
                  <div className={styles.adAction}>
                    {yaExiste ? (
                      <span className={styles.badgeExiste}><IconoCheck /> Ya registrado</span>
                    ) : (
                      <button
                        className={styles.btnAgregar}
                        onClick={() => alCrear(u.username)}
                        disabled={creando === u.username}
                      >
                        {creando === u.username ? <span className={styles.spinner} /> : <IconoMas tamano={15} />}
                        {creando === u.username ? "Agregando…" : "Agregar"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
