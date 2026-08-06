import { useState, useEffect, useCallback } from "react";
import { apiAdmin, type UsuarioAD, type UsuarioSistema, type Rol } from "../../api/admin";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { useNotificacion } from "../../components/Notificaciones";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import {
  IconoBuscar, IconoUsuario, IconoCorreo, IconoMaletin, IconoMas,
  IconoCheck, IconoBasura, IconoPoder, IconoEscudo, IconoLlave,
} from "../../components/Iconos";
import styles from "./PaginaUsuarios.module.css";

export default function PaginaUsuarios() {
  const { usuario } = useAutenticacion();
  const { mostrar: mostrarToast } = useNotificacion();

  const [busqueda,     setBusqueda]     = useState("");
  const [buscando,     setBuscando]     = useState(false);
  const [resultadosAD, setResultadosAD] = useState<UsuarioAD[]>([]);
  const [errorBusq,    setErrorBusq]    = useState<string | null>(null);

  const [usuarios,     setUsuarios]     = useState<UsuarioSistema[]>([]);
  const [roles,        setRoles]        = useState<Rol[]>([]);
  const [cargando,     setCargando]     = useState(true);
  const [creando,      setCreando]      = useState<string | null>(null);
  const [eliminando,   setEliminando]   = useState<number | null>(null);
  const [toggling,     setToggling]     = useState<number | null>(null);
  const [asignandoRol, setAsignandoRol] = useState<number | null>(null);
  const [confirmar,    setConfirmar]    = useState<number | null>(null);

  // Usuario local de prueba (sin AD) — temporal, solo mientras no esté en producción.
  const [mostrarLocal,   setMostrarLocal]   = useState(false);
  const [localUsername,  setLocalUsername]  = useState("");
  const [localPassword,  setLocalPassword]  = useState("");
  const [localNombre,    setLocalNombre]    = useState("");
  const [localApellido,  setLocalApellido]  = useState("");
  const [localEmail,     setLocalEmail]     = useState("");
  const [localRolId,     setLocalRolId]     = useState<number | "">("");
  const [creandoLocal,   setCreandoLocal]   = useState(false);
  const [errorLocal,     setErrorLocal]     = useState<string | null>(null);

  const cargarUsuarios = useCallback(async () => {
    try {
      const { data } = await apiAdmin.listarUsuarios();
      setUsuarios(data);
    } catch {
      // silencio
    } finally {
      setCargando(false);
    }
  }, []);

  const cargarRoles = useCallback(async () => {
    try {
      const { data } = await apiAdmin.listarRoles();
      setRoles(data);
    } catch {
      // silencio
    }
  }, []);

  useEffect(() => {
    cargarUsuarios();
    cargarRoles();
  }, [cargarUsuarios, cargarRoles]);

  async function alBuscar(e: React.FormEvent) {
    e.preventDefault();
    const q = busqueda.trim();
    if (q.length < 2) return;
    setBuscando(true);
    setErrorBusq(null);
    setResultadosAD([]);
    try {
      const { data } = await apiAdmin.buscarEnAD(q);
      setResultadosAD(data);
      if (data.length === 0) setErrorBusq("No se encontraron usuarios con ese criterio.");
    } catch (err: any) {
      setErrorBusq(err?.response?.data?.detail ?? "Error al conectar con Active Directory.");
    } finally {
      setBuscando(false);
    }
  }

  async function alCrear(username: string) {
    setCreando(username);
    try {
      await apiAdmin.crearUsuario(username);
      setResultadosAD(prev => prev.filter(u => u.username !== username));
      await cargarUsuarios();
      mostrarToast(`Usuario ${username} agregado.`, "exito");
    } catch (err: any) {
      mostrarToast(err?.response?.data?.detail ?? "Error al crear el usuario.", "error");
    } finally {
      setCreando(null);
    }
  }

  async function alCrearLocal(e: React.FormEvent) {
    e.preventDefault();
    const username = localUsername.trim();
    if (!username || localPassword.length < 4) {
      setErrorLocal("Usuario y contraseña (mínimo 4 caracteres) son obligatorios.");
      return;
    }
    setCreandoLocal(true);
    setErrorLocal(null);
    try {
      await apiAdmin.crearUsuarioLocal({
        username,
        password: localPassword,
        name: localNombre.trim() || undefined,
        last_name: localApellido.trim() || undefined,
        email: localEmail.trim() || undefined,
        rol_id: localRolId !== "" ? localRolId : undefined,
      });
      setLocalUsername(""); setLocalPassword(""); setLocalNombre("");
      setLocalApellido(""); setLocalEmail(""); setLocalRolId("");
      await cargarUsuarios();
      mostrarToast(`Usuario local ${username} creado.`, "exito");
    } catch (err: any) {
      setErrorLocal(err?.response?.data?.detail ?? "Error al crear el usuario local.");
    } finally {
      setCreandoLocal(false);
    }
  }

  async function alToggleEstado(id: number, estadoActual: string) {
    setToggling(id);
    const nuevoEstado = estadoActual === "active" ? "inactive" : "active";
    try {
      const { data } = await apiAdmin.cambiarEstado(id, nuevoEstado);
      setUsuarios(prev => prev.map(u => u.id === id ? data : u));
      mostrarToast(`Usuario ${nuevoEstado === "active" ? "activado" : "desactivado"}.`, "exito");
    } catch (err: any) {
      mostrarToast(err?.response?.data?.detail ?? "Error al cambiar el estado.", "error");
    } finally {
      setToggling(null);
    }
  }

  async function alAsignarRol(id: number, rol_id: number | null) {
    setAsignandoRol(id);
    try {
      const { data } = await apiAdmin.asignarRolAUsuario(id, rol_id);
      setUsuarios(prev => prev.map(u => u.id === id ? data : u));
      mostrarToast("Rol asignado correctamente.", "exito");
    } catch (err: any) {
      mostrarToast(err?.response?.data?.detail ?? "Error al asignar el rol.", "error");
    } finally {
      setAsignandoRol(null);
    }
  }

  async function alEliminar(id: number) {
    setEliminando(id);
    try {
      await apiAdmin.eliminarUsuario(id);
      setUsuarios(prev => prev.filter(u => u.id !== id));
      mostrarToast("Usuario eliminado.", "exito");
    } catch (err: any) {
      mostrarToast(err?.response?.data?.detail ?? "Error al eliminar el usuario.", "error");
    } finally {
      setEliminando(null);
      setConfirmar(null);
    }
  }

  const usuariosRegistrados = new Set(usuarios.map(u => u.username));

  return (
    <div className={styles.page}>


      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <BotonVolver to="/dashboard" />
          <div className={styles.headerCenter}>
            <img src="/images/logo-snm.png" alt="SNM" className={styles.logo} />
            <div className={styles.headerText}>
              <div className={styles.org}>Servicio Nacional de Migración</div>
              <div className={styles.app}>FileDrop - SNM</div>
            </div>
          </div>
          <div className={styles.headerRight}>
            <MenuCabecera />
          </div>
        </div>
      </header>

      {/* Body */}
      <main className={styles.body}>
        <div className={styles.container}>

          {/* Page title */}
          <div className={styles.pageTitle}>
            <span className={styles.titleIcon}><IconoEscudo /></span>
            <div>
              <h1>Gestión de usuarios</h1>
              <p>Busca usuarios en Active Directory y agrégalos al sistema.</p>
            </div>
          </div>

          {/* AD Search panel */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <IconoBuscar />
              Buscar en Active Directory
            </div>
            <div className={styles.panelBody}>
              <form onSubmit={alBuscar} className={styles.searchRow}>
                <input
                  className={styles.searchInput}
                  type="text"
                  placeholder="Nombre, usuario o correo..."
                  value={busqueda}
                  onChange={e => setBusqueda(e.target.value)}
                  autoFocus
                />
                <button
                  type="submit"
                  className={styles.searchBtn}
                  disabled={buscando || busqueda.trim().length < 2}
                >
                  {buscando ? <span className={styles.spinner} /> : <IconoBuscar />}
                  {buscando ? "Buscando…" : "Buscar"}
                </button>
              </form>

              {errorBusq && (
                <p className={styles.searchError}>{errorBusq}</p>
              )}

              {resultadosAD.length > 0 && (
                <div className={styles.adResults}>
                  {resultadosAD.map(u => {
                    const yaExiste = usuariosRegistrados.has(u.username);
                    return (
                      <div key={u.username} className={styles.adCard}>
                        <div className={styles.adAvatar}>
                          <IconoUsuario />
                        </div>
                        <div className={styles.adInfo}>
                          <div className={styles.adName}>
                            {u.name || u.last_name
                              ? `${u.name} ${u.last_name}`.trim()
                              : u.username}
                          </div>
                          <div className={styles.adMeta}>
                            <span><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>{u.username}</span>
                            {u.email && <span><IconoCorreo />{u.email}</span>}
                            {u.department && <span><IconoMaletin />{u.department}</span>}
                          </div>
                        </div>
                        <div className={styles.adAction}>
                          {yaExiste ? (
                            <span className={styles.badgeExiste}>
                              <IconoCheck /> Ya registrado
                            </span>
                          ) : (
                            <button
                              className={styles.btnAgregar}
                              onClick={() => alCrear(u.username)}
                              disabled={creando === u.username}
                            >
                              {creando === u.username
                                ? <span className={styles.spinner} />
                                : <IconoMas tamano={15} />}
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

          {/* Usuario local de prueba (temporal, sin AD) */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <IconoLlave />
              Usuario de prueba (local, temporal)
              <button
                type="button"
                className={styles.searchBtn}
                style={{ marginLeft: "auto", padding: "6px 14px" }}
                onClick={() => setMostrarLocal(v => !v)}
              >
                <IconoMas tamano={14} />
                {mostrarLocal ? "Ocultar" : "Nuevo"}
              </button>
            </div>
            {mostrarLocal && (
              <div className={styles.panelBody}>
                <p className={styles.searchError} style={{ marginTop: 0, marginBottom: 14 }}>
                  Crea una cuenta con contraseña propia, sin pasar por Active Directory — solo para
                  probar roles y permisos mientras el sistema está en fase de pruebas. Esta opción
                  se elimina antes de pasar a producción.
                </p>
                <form onSubmit={alCrearLocal} className={styles.searchRow} style={{ flexWrap: "wrap" }}>
                  <input
                    className={styles.searchInput}
                    style={{ minWidth: 140 }}
                    placeholder="Usuario *"
                    value={localUsername}
                    onChange={e => setLocalUsername(e.target.value)}
                    required
                  />
                  <input
                    className={styles.searchInput}
                    style={{ minWidth: 140 }}
                    type="password"
                    placeholder="Contraseña *"
                    value={localPassword}
                    onChange={e => setLocalPassword(e.target.value)}
                    required
                  />
                  <input
                    className={styles.searchInput}
                    style={{ minWidth: 140 }}
                    placeholder="Nombre"
                    value={localNombre}
                    onChange={e => setLocalNombre(e.target.value)}
                  />
                  <input
                    className={styles.searchInput}
                    style={{ minWidth: 140 }}
                    placeholder="Apellido"
                    value={localApellido}
                    onChange={e => setLocalApellido(e.target.value)}
                  />
                  <input
                    className={styles.searchInput}
                    style={{ minWidth: 160 }}
                    type="email"
                    placeholder="Correo (opcional)"
                    value={localEmail}
                    onChange={e => setLocalEmail(e.target.value)}
                  />
                  <select
                    className={styles.rolSelect}
                    value={localRolId}
                    onChange={e => setLocalRolId(e.target.value ? Number(e.target.value) : "")}
                  >
                    <option value="">— Sin rol —</option>
                    {roles.map(r => (
                      <option key={r.id} value={r.id}>{r.nombre}</option>
                    ))}
                  </select>
                  <button type="submit" className={styles.searchBtn} disabled={creandoLocal}>
                    {creandoLocal ? <span className={styles.spinner} /> : <IconoCheck tamano={14} />}
                    {creandoLocal ? "Creando…" : "Crear"}
                  </button>
                </form>
                {errorLocal && <p className={styles.searchError}>{errorLocal}</p>}
              </div>
            )}
          </section>

          {/* Users table */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <IconoUsuario />
              Usuarios del sistema
              <span className={styles.count}>{usuarios.length}</span>
            </div>
            <div className={styles.panelBody}>
              {cargando ? (
                <div className={styles.loading}>
                  <span className={styles.spinner} /> Cargando usuarios…
                </div>
              ) : usuarios.length === 0 ? (
                <p className={styles.empty}>No hay usuarios registrados. Usa la búsqueda de arriba para agregar el primero.</p>
              ) : (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Usuario</th>
                        <th>Correo</th>
                        <th>Rol</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usuarios.map(u => (
                        <tr key={u.id} className={u.status === "inactive" ? styles.rowInactive : ""}>
                          <td>
                            <div className={styles.cellUser}>
                              <div className={`${styles.cellAvatar} ${u.rol_personalizado?.nombre === "Administrador" ? styles.cellAvatarAdmin : ""}`}>
                                {(u.name?.[0] ?? u.username[0]).toUpperCase()}
                              </div>
                              <div>
                                <div className={styles.cellName}>{u.full_name}</div>
                                <div className={styles.cellUsername}>@{u.username}</div>
                              </div>
                            </div>
                          </td>
                          <td className={styles.cellEmail}>{u.email ?? "—"}</td>
                          <td>
                            <select
                              className={styles.rolSelect}
                              value={u.rol_id ?? ""}
                              onChange={e => alAsignarRol(u.id, e.target.value ? Number(e.target.value) : null)}
                              disabled={asignandoRol === u.id}
                            >
                              <option value="">— Sin rol —</option>
                              {roles.map(r => (
                                <option key={r.id} value={r.id}>{r.nombre}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <span className={`${styles.badge} ${u.status === "active" ? styles.badgeActive : styles.badgeInactive}`}>
                              {u.status === "active" ? "Activo" : "Inactivo"}
                            </span>
                          </td>
                          <td>
                            <div className={styles.actions}>
                              <button
                                className={`${styles.actionBtn} ${u.status === "active" ? styles.btnDesactivar : styles.btnActivar}`}
                                onClick={() => alToggleEstado(u.id, u.status)}
                                disabled={toggling === u.id || u.id === usuario?.id}
                                title={u.status === "active" ? "Desactivar" : "Activar"}
                              >
                                {toggling === u.id
                                  ? <span className={styles.spinnerSm} />
                                  : <IconoPoder />}
                                {u.status === "active" ? "Desactivar" : "Activar"}
                              </button>

                              {confirmar === u.id ? (
                                <div className={styles.confirmRow}>
                                  <span className={styles.confirmText}>¿Confirmar?</span>
                                  <button
                                    className={`${styles.actionBtn} ${styles.btnEliminarConfirm}`}
                                    onClick={() => alEliminar(u.id)}
                                    disabled={eliminando === u.id}
                                  >
                                    {eliminando === u.id ? <span className={styles.spinnerSm} /> : <IconoCheck />}
                                    Sí
                                  </button>
                                  <button
                                    className={`${styles.actionBtn} ${styles.btnCancelar}`}
                                    onClick={() => setConfirmar(null)}
                                  >
                                    No
                                  </button>
                                </div>
                              ) : (
                                <button
                                  className={`${styles.actionBtn} ${styles.btnEliminar}`}
                                  onClick={() => setConfirmar(u.id)}
                                  disabled={u.id === usuario?.id}
                                  title="Eliminar usuario"
                                >
                                  <IconoBasura tamano={14} /> Eliminar
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

        </div>
      </main>

      {/* Footer */}
      <footer className={styles.footer}>
        Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
      </footer>
    </div>
  );
}
