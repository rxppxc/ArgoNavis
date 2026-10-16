import { useState, useEffect, useCallback } from "react";
import { apiAdmin, type UsuarioAD, type UsuarioSistema, type Rol } from "../../api/admin";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { useNotificacion } from "../../components/Notificaciones";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { MarcoPagina } from "../../components/MarcoPagina";
import {
  IconoBuscar, IconoUsuario, IconoCorreo, IconoMaletin, IconoMas,
  IconoCheck, IconoBasura, IconoPoder, IconoEscudo, IconoLlave,
} from "../../components/Iconos";
import { copiarAlPortapapeles } from "../../utils/portapapeles";
import { LARGO_MINIMO_CONTRASENA, problemaContrasena } from "../../utils/contrasena";
import { mensajeDeError } from "../../utils/errores";
import styles from "./PaginaUsuarios.module.css";

export default function PaginaUsuarios() {
  const { usuario } = useAutenticacion();
  const { mostrar: mostrarToast } = useNotificacion();
  const confirmar = useConfirmar();

  const [busqueda,     setBusqueda]     = useState("");
  const [buscando,     setBuscando]     = useState(false);
  const [resultadosAD, setResultadosAD] = useState<UsuarioAD[]>([]);
  const [errorBusq,    setErrorBusq]    = useState<string | null>(null);

  const [usuarios,     setUsuarios]     = useState<UsuarioSistema[]>([]);
  const [roles,        setRoles]        = useState<Rol[]>([]);
  const [cargando,     setCargando]     = useState(true);
  const [creando,      setCreando]      = useState<string | null>(null);
  const [ocupado,      setOcupado]      = useState<number | null>(null);
  const [claveTemporal, setClaveTemporal] = useState<{ username: string; clave: string } | null>(null);

  // Cuenta local (sin AD): usuarios externos, como los de las agencias navieras.
  const [mostrarLocal,   setMostrarLocal]   = useState(false);
  const [localUsername,  setLocalUsername]  = useState("");
  const [localPassword,  setLocalPassword]  = useState("");
  const [localNombre,    setLocalNombre]    = useState("");
  const [localApellido,  setLocalApellido]  = useState("");
  const [localEmail,     setLocalEmail]     = useState("");
  const [localRolId,     setLocalRolId]     = useState<number | "">("");
  const [creandoLocal,   setCreandoLocal]   = useState(false);
  const [errorLocal,     setErrorLocal]     = useState<string | null>(null);

  const cargarUsuarios = useCallback(() => apiAdmin.listarUsuarios().then(({ data }) => setUsuarios(data)), []);

  useEffect(() => {
    let cancelado = false;
    Promise.all([apiAdmin.listarUsuarios(), apiAdmin.listarRoles()])
      .then(([u, r]) => {
        if (cancelado) return;
        setUsuarios(u.data);
        setRoles(r.data);
      })
      .catch((e) => { if (!cancelado) mostrarToast(mensajeDeError(e, "No se pudieron cargar los usuarios."), "error"); })
      .finally(() => { if (!cancelado) setCargando(false); });
    return () => { cancelado = true; };
  }, [mostrarToast]);

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
    } catch (err) {
      setErrorBusq(mensajeDeError(err, "Error al conectar con Active Directory."));
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
    } catch (err) {
      mostrarToast(mensajeDeError(err, "Error al crear el usuario."), "error");
    } finally {
      setCreando(null);
    }
  }

  async function alCrearLocal(e: React.FormEvent) {
    e.preventDefault();
    const username = localUsername.trim();
    if (!username) {
      setErrorLocal("El usuario es obligatorio.");
      return;
    }
    const problema = problemaContrasena(localPassword, username);
    if (problema) {
      setErrorLocal(problema);
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
      mostrarToast(`Cuenta local ${username} creada. Deberá cambiar la contraseña al entrar.`, "exito");
    } catch (err) {
      setErrorLocal(mensajeDeError(err, "Error al crear la cuenta local."));
    } finally {
      setCreandoLocal(false);
    }
  }

  async function alToggleEstado(u: UsuarioSistema) {
    setOcupado(u.id);
    const nuevoEstado = u.status === "active" ? "inactive" : "active";
    try {
      const { data } = await apiAdmin.cambiarEstado(u.id, nuevoEstado);
      setUsuarios(prev => prev.map(x => x.id === u.id ? data : x));
      mostrarToast(`Usuario ${nuevoEstado === "active" ? "activado" : "desactivado"}.`, "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "Error al cambiar el estado."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function alAsignarRol(id: number, rol_id: number | null) {
    setOcupado(id);
    try {
      const { data } = await apiAdmin.asignarRolAUsuario(id, rol_id);
      setUsuarios(prev => prev.map(u => u.id === id ? data : u));
      mostrarToast("Rol asignado correctamente.", "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "Error al asignar el rol."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function alRestablecer(u: UsuarioSistema) {
    const ok = await confirmar({
      titulo: "Restablecer contraseña",
      mensaje: `Se generará una contraseña temporal para @${u.username} y se desbloqueará la cuenta. Deberá cambiarla al entrar.`,
      textoOk: "Restablecer",
    });
    if (!ok) return;
    setOcupado(u.id);
    try {
      const clave = await apiAdmin.restablecerContrasena(u.id);
      setClaveTemporal({ username: u.username, clave });
      await cargarUsuarios();
    } catch (err) {
      mostrarToast(mensajeDeError(err, "No se pudo restablecer la contraseña."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function alEliminar(u: UsuarioSistema) {
    const ok = await confirmar({
      titulo: "Eliminar usuario",
      mensaje: `Se eliminará la cuenta @${u.username}. Si tiene solicitudes registradas no se podrá: desactívala en su lugar.`,
      textoOk: "Eliminar",
      peligroso: true,
    });
    if (!ok) return;
    setOcupado(u.id);
    try {
      await apiAdmin.eliminarUsuario(u.id);
      setUsuarios(prev => prev.filter(x => x.id !== u.id));
      mostrarToast("Usuario eliminado.", "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "Error al eliminar el usuario."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function copiarClave() {
    if (!claveTemporal) return;
    const ok = await copiarAlPortapapeles(claveTemporal.clave);
    mostrarToast(ok ? "Contraseña copiada." : "No se pudo copiar: cópiala a mano.", ok ? "exito" : "aviso");
  }

  const usuariosRegistrados = new Set(usuarios.map(u => u.username));

  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.container}>

        <div className={styles.pageTitle}>
          <span className={styles.titleIcon}><IconoEscudo /></span>
          <div>
            <h1>Gestión de usuarios</h1>
            <p>Agrega usuarios del Active Directory o crea cuentas locales para usuarios externos.</p>
          </div>
        </div>

        {claveTemporal && (
          <section className={`${styles.panel} ${styles.claveTemporal}`} role="status">
            <div className={styles.panelBody}>
              <strong>Contraseña temporal de @{claveTemporal.username}:</strong>
              <code>{claveTemporal.clave}</code>
              <button type="button" className={styles.searchBtn} onClick={copiarClave}>Copiar</button>
              <button type="button" className={`${styles.actionBtn} ${styles.btnCancelar}`} onClick={() => setClaveTemporal(null)}>
                Listo
              </button>
              <p>Entrégala por un medio seguro: no se volverá a mostrar. Al entrar, el sistema le pedirá cambiarla.</p>
            </div>
          </section>
        )}

        {/* Búsqueda en Active Directory */}
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

            {errorBusq && <p className={styles.searchError}>{errorBusq}</p>}

            {resultadosAD.length > 0 && (
              <div className={styles.adResults}>
                {resultadosAD.map(u => {
                  const yaExiste = usuariosRegistrados.has(u.username);
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

        {/* Cuenta local (sin AD) */}
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <IconoLlave />
            Cuenta local (usuarios externos)
            <button
              type="button"
              className={`${styles.searchBtn} ${styles.btnPanel}`}
              onClick={() => setMostrarLocal(v => !v)}
            >
              <IconoMas tamano={14} />
              {mostrarLocal ? "Ocultar" : "Nueva"}
            </button>
          </div>
          {mostrarLocal && (
            <div className={styles.panelBody}>
              <p className={styles.ayudaLocal}>
                Para usuarios sin cuenta en el Active Directory, como los de las agencias navieras. La contraseña
                inicial debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres, con mayúscula, minúscula, número y
                carácter especial, sin el nombre de usuario; el usuario deberá
                cambiarla al entrar. Después, asígnalo a su agencia en Agencias, puestos y países.
              </p>
              <form onSubmit={alCrearLocal} className={`${styles.searchRow} ${styles.formLocal}`}>
                <input className={styles.searchInput} placeholder="Usuario *"
                  value={localUsername} onChange={e => setLocalUsername(e.target.value)} required />
                <input className={styles.searchInput} type="password" placeholder="Contraseña inicial *" autoComplete="new-password"
                  value={localPassword} onChange={e => setLocalPassword(e.target.value)} required />
                <input className={styles.searchInput} placeholder="Nombre"
                  value={localNombre} onChange={e => setLocalNombre(e.target.value)} />
                <input className={styles.searchInput} placeholder="Apellido"
                  value={localApellido} onChange={e => setLocalApellido(e.target.value)} />
                <input className={styles.searchInput} type="email" placeholder="Correo (recibe los avisos)"
                  value={localEmail} onChange={e => setLocalEmail(e.target.value)} />
                <select className={styles.rolSelect} value={localRolId}
                  onChange={e => setLocalRolId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">— Sin rol —</option>
                  {roles.map(r => <option key={r.id} value={r.id}>{r.nombre}</option>)}
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

        {/* Usuarios del sistema */}
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <IconoUsuario />
            Usuarios del sistema
            <span className={styles.count}>{usuarios.length}</span>
          </div>
          <div className={styles.panelBody}>
            {cargando ? (
              <div className={styles.loading}><span className={styles.spinner} /> Cargando usuarios…</div>
            ) : usuarios.length === 0 ? (
              <p className={styles.empty}>No hay usuarios registrados. Usa la búsqueda de arriba para agregar el primero.</p>
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
                    {usuarios.map(u => {
                      const esYo = u.id === usuario?.id;
                      const trabajando = ocupado === u.id;
                      return (
                        <tr key={u.id} className={u.status === "inactive" ? styles.rowInactive : ""}>
                          <td>
                            <div className={styles.cellUser}>
                              <div className={`${styles.cellAvatar} ${["Administrador", "SysAdmin"].includes(u.rol_personalizado?.nombre ?? "") ? styles.cellAvatarAdmin : ""}`}>
                                {(u.name?.[0] ?? u.username[0]).toUpperCase()}
                              </div>
                              <div>
                                <div className={styles.cellName}>{u.full_name}</div>
                                <div className={styles.cellUsername}>
                                  @{u.username}
                                  {u.user_type === "local" && <span className={styles.badgeTipo}>Local</span>}
                                  {u.debe_cambiar_password && <span className={styles.badgeTipo}>Cambio de clave pendiente</span>}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className={styles.cellEmail}>{u.email ?? "—"}</td>
                          <td className={styles.cellEmail}>{u.agencia?.nombre ?? "—"}</td>
                          <td>
                            <select
                              className={styles.rolSelect}
                              value={u.rol_id ?? ""}
                              onChange={e => alAsignarRol(u.id, e.target.value ? Number(e.target.value) : null)}
                              disabled={trabajando}
                            >
                              <option value="">— Sin rol —</option>
                              {roles.map(r => <option key={r.id} value={r.id}>{r.nombre}</option>)}
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
                                onClick={() => alToggleEstado(u)}
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

      </div>
    </MarcoPagina>
  );
}
