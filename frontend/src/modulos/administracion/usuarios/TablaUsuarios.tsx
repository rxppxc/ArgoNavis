import { useState } from "react";
import type { Rol, UsuarioSistema } from "../../../api/admin";
import { EstadoCarga } from "../../../components/EstadoCarga";
import { IconoBasura, IconoLlave, IconoPoder, IconoUsuario } from "../../../components/Iconos";
import styles from "../PaginaUsuarios.module.css";

interface Props {
  usuarios: UsuarioSistema[];
  roles: Rol[];
  cargando: boolean;
  /** La propia cuenta: no se desactiva, no se borra ni se cambia el rol. */
  idPropio: number | undefined;
  /** La fila con una acción en curso. */
  ocupado: number | null;
  alCambiarEstado: (u: UsuarioSistema) => void;
  alAsignarRol: (id: number, rolId: number | null) => void;
  alRestablecer: (u: UsuarioSistema) => void;
  alEliminar: (u: UsuarioSistema) => void;
}

/** «Usuarios del sistema», con su filtro (de PaginaUsuarios, 2026-11-14). */
export function TablaUsuarios({
  usuarios, roles, cargando, idPropio, ocupado, alCambiarEstado, alAsignarRol, alRestablecer, alEliminar,
}: Props) {
  // Filtro de la tabla (en el navegador): antes, para encontrar a alguien había que recorrerla entera.
  const [filtro, setFiltro] = useState("");
  const textoFiltro = filtro.trim().toLowerCase();
  const visibles = textoFiltro
    ? usuarios.filter(u => [u.full_name, u.username, u.email, u.agencia?.nombre, u.rol_personalizado?.nombre]
      .some(dato => dato?.toLowerCase().includes(textoFiltro)))
    : usuarios;

  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <IconoUsuario />
        Usuarios del sistema
        <span className={styles.count}>{textoFiltro ? `${visibles.length} de ${usuarios.length}` : usuarios.length}</span>
      </div>
      <div className={styles.panelBody}>
        {usuarios.length > 0 && (
          <input
            className={`${styles.searchInput} ${styles.filtroTabla}`}
            type="search"
            placeholder="Filtrar por nombre, usuario, correo, agencia o rol…"
            aria-label="Filtrar los usuarios del sistema"
            maxLength={100}
            value={filtro}
            onChange={e => setFiltro(e.target.value)}
          />
        )}
        {cargando ? (
          <EstadoCarga texto="Cargando usuarios…" />
        ) : usuarios.length === 0 ? (
          <p className={styles.empty}>No hay usuarios registrados. Usa la búsqueda de arriba para agregar el primero.</p>
        ) : visibles.length === 0 ? (
          <p className={styles.empty}>Ningún usuario coincide con «{filtro.trim()}».</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Correo</th>
                  <th>Agencia</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {visibles.map(u => {
                  const esYo = u.id === idPropio;
                  const trabajando = ocupado === u.id;
                  return (
                    // data-etiqueta: el título de cada dato cuando la tabla pasa a fichas en el celular.
                    <tr key={u.id} className={u.status === "inactive" ? styles.rowInactive : ""}>
                      <td className={styles.celdaAncha}>
                        <div className={styles.cellUser}>
                          <div className={`${styles.cellAvatar} ${["Administrador", "SysAdmin"].includes(u.rol_personalizado?.nombre ?? "") ? styles.cellAvatarAdmin : ""}`}>
                            {(u.name?.[0] ?? u.username[0]).toUpperCase()}
                          </div>
                          <div>
                            <div className={styles.cellName}>{u.full_name}</div>
                            <div className={styles.cellUsername}>
                              @{u.username}
                              {/* La propia cuenta: por eso Desactivar, Eliminar y el rol quedan inactivos. */}
                              {esYo && <span className={styles.badgeTipo}>Tú</span>}
                              {u.user_type === "local" && <span className={styles.badgeTipo}>Local</span>}
                              {u.debe_cambiar_password && <span className={styles.badgeTipo}>Cambio de clave pendiente</span>}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className={styles.cellEmail} data-etiqueta="Correo">{u.email ?? "—"}</td>
                      <td className={styles.cellEmail} data-etiqueta="Agencia">{u.agencia?.nombre ?? "—"}</td>
                      <td data-etiqueta="Rol">
                        <select
                          className={styles.rolSelect}
                          value={u.rol_id ?? ""}
                          onChange={e => alAsignarRol(u.id, e.target.value ? Number(e.target.value) : null)}
                          disabled={trabajando || esYo}
                          title={esYo ? "Tu propio rol lo cambia otra persona" : undefined}
                          aria-label={`Rol de ${u.full_name}`}
                        >
                          <option value="">— Sin rol —</option>
                          {roles.map(r => <option key={r.id} value={r.id}>{r.nombre}</option>)}
                        </select>
                      </td>
                      <td data-etiqueta="Estado">
                        <span className={`${styles.badge} ${u.status === "active" ? styles.badgeActive : styles.badgeInactive}`}>
                          {u.status === "active" ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className={styles.celdaAncha}>
                        <div className={styles.actions}>
                          <button
                            className={`${styles.actionBtn} ${u.status === "active" ? styles.btnDesactivar : styles.btnActivar}`}
                            onClick={() => alCambiarEstado(u)}
                            disabled={trabajando || esYo}
                            title={u.status === "active" ? "Desactivar" : "Activar"}
                          >
                            {trabajando ? <span className={styles.spinnerSm} /> : <IconoPoder />}
                            {u.status === "active" ? "Desactivar" : "Activar"}
                          </button>
                          {u.user_type === "local" && (
                            <button
                              className={`${styles.actionBtn} ${styles.btnRestablecer}`}
                              onClick={() => alRestablecer(u)}
                              disabled={trabajando}
                              title="Generar una contraseña temporal"
                            >
                              <IconoLlave tamano={14} /> Restablecer
                            </button>
                          )}
                          <button
                            className={`${styles.actionBtn} ${styles.btnEliminar}`}
                            onClick={() => alEliminar(u)}
                            disabled={trabajando || esYo}
                            title="Eliminar usuario"
                          >
                            <IconoBasura tamano={14} /> Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
