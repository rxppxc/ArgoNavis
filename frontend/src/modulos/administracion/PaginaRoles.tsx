import { useState, useEffect, useCallback, useMemo } from "react";
import { apiAdmin, type Permiso, type Rol } from "../../api/admin";
import { MenuCabecera } from "../../components/MenuCabecera";
import { BotonVolver } from "../../components/BotonVolver";
import {
  IconoLlave, IconoEscudo, IconoMas, IconoBasura,
  IconoCheck, IconoX, IconoCandado, IconoChevronDerecha,
} from "../../components/Iconos";
import styles from "./PaginaRoles.module.css";

export default function PaginaRoles() {
  /* ── Permisos ── */
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [cargandoPermisos, setCargandoPermisos] = useState(true);
  const [creandoPermiso, setCreandoPermiso] = useState(false);
  const [nuevoPCodigo, setNuevoPCodigo] = useState("");
  const [nuevoPNombre, setNuevoPNombre] = useState("");
  const [nuevoPDesc, setNuevoPDesc] = useState("");
  const [eliminandoP, setEliminandoP] = useState<number | null>(null);
  const [confirmarP, setConfirmarP] = useState<number | null>(null);

  /* ── Roles ── */
  const [roles, setRoles] = useState<Rol[]>([]);
  const [cargandoRoles, setCargandoRoles] = useState(true);
  const [creandoRol, setCreandoRol] = useState(false);
  const [nuevoRNombre, setNuevoRNombre] = useState("");
  const [nuevoRDesc, setNuevoRDesc] = useState("");
  const [eliminandoR, setEliminandoR] = useState<number | null>(null);
  const [confirmarR, setConfirmarR] = useState<number | null>(null);

  /* ── Rol expandido (vista de permisos asignados) ── */
  const [rolAbierto, setRolAbierto] = useState<number | null>(null);
  const [guardandoPermisosRol, setGuardandoPermisosRol] = useState<number | null>(null);
  const [seleccionPermisos, setSeleccionPermisos] = useState<Set<number>>(new Set());

  /* ── Mensaje global ── */
  const [aviso, setAviso] = useState<{ texto: string; tipo: "ok" | "err" } | null>(null);

  function mostrarAviso(texto: string, tipo: "ok" | "err" = "ok") {
    setAviso({ texto, tipo });
    setTimeout(() => setAviso(null), 3000);
  }

  const cargarPermisos = useCallback(async () => {
    try {
      const { data } = await apiAdmin.listarPermisos();
      setPermisos(data);
    } catch {
      // silencio
    } finally {
      setCargandoPermisos(false);
    }
  }, []);

  const cargarRoles = useCallback(async () => {
    try {
      const { data } = await apiAdmin.listarRoles();
      setRoles(data);
    } catch {
      // silencio
    } finally {
      setCargandoRoles(false);
    }
  }, []);

  useEffect(() => { cargarPermisos(); cargarRoles(); }, [cargarPermisos, cargarRoles]);

  /* ── Permisos ── */
  async function alCrearPermiso(e: React.FormEvent) {
    e.preventDefault();
    const codigo = nuevoPCodigo.trim().toUpperCase();
    const nombre = nuevoPNombre.trim();
    if (!codigo || !nombre) return;
    setCreandoPermiso(true);
    try {
      const { data } = await apiAdmin.crearPermiso(codigo, nombre, nuevoPDesc.trim() || undefined);
      setPermisos(prev => [...prev, data].sort((a, b) => a.codigo.localeCompare(b.codigo)));
      setNuevoPCodigo(""); setNuevoPNombre(""); setNuevoPDesc("");
      mostrarAviso("Permiso creado correctamente.");
    } catch (err: any) {
      mostrarAviso(err?.response?.data?.detail ?? "Error al crear el permiso.", "err");
    } finally {
      setCreandoPermiso(false);
    }
  }

  async function alEliminarPermiso(id: number) {
    setEliminandoP(id);
    try {
      await apiAdmin.eliminarPermiso(id);
      setPermisos(prev => prev.filter(p => p.id !== id));
      // refrescar roles que pudieran tenerlo
      cargarRoles();
      mostrarAviso("Permiso eliminado.");
    } catch (err: any) {
      mostrarAviso(err?.response?.data?.detail ?? "Error al eliminar el permiso.", "err");
    } finally {
      setEliminandoP(null);
      setConfirmarP(null);
    }
  }

  /* ── Roles ── */
  async function alCrearRol(e: React.FormEvent) {
    e.preventDefault();
    const nombre = nuevoRNombre.trim();
    if (!nombre) return;
    setCreandoRol(true);
    try {
      const { data } = await apiAdmin.crearRol(nombre, nuevoRDesc.trim() || undefined);
      setRoles(prev => [...prev, data].sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setNuevoRNombre(""); setNuevoRDesc("");
      mostrarAviso("Rol creado correctamente.");
    } catch (err: any) {
      mostrarAviso(err?.response?.data?.detail ?? "Error al crear el rol.", "err");
    } finally {
      setCreandoRol(false);
    }
  }

  async function alEliminarRol(id: number) {
    setEliminandoR(id);
    try {
      await apiAdmin.eliminarRol(id);
      setRoles(prev => prev.filter(r => r.id !== id));
      if (rolAbierto === id) setRolAbierto(null);
      mostrarAviso("Rol eliminado.");
    } catch (err: any) {
      mostrarAviso(err?.response?.data?.detail ?? "Error al eliminar el rol.", "err");
    } finally {
      setEliminandoR(null);
      setConfirmarR(null);
    }
  }

  function abrirRol(rol: Rol) {
    if (rolAbierto === rol.id) {
      setRolAbierto(null);
      return;
    }
    setRolAbierto(rol.id);
    setSeleccionPermisos(new Set(rol.permisos.map(p => p.id)));
  }

  function togglePermiso(pid: number) {
    setSeleccionPermisos(prev => {
      const nuevo = new Set(prev);
      if (nuevo.has(pid)) nuevo.delete(pid);
      else nuevo.add(pid);
      return nuevo;
    });
  }

  async function guardarPermisosRol(rolId: number) {
    setGuardandoPermisosRol(rolId);
    try {
      const { data } = await apiAdmin.asignarPermisosARol(rolId, Array.from(seleccionPermisos));
      setRoles(prev => prev.map(r => r.id === rolId ? data : r));
      mostrarAviso("Permisos del rol actualizados.");
    } catch (err: any) {
      mostrarAviso(err?.response?.data?.detail ?? "Error al guardar los permisos.", "err");
    } finally {
      setGuardandoPermisosRol(null);
    }
  }

  const permisosOrdenados = useMemo(
    () => [...permisos].sort((a, b) => a.codigo.localeCompare(b.codigo)),
    [permisos]
  );

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

      {/* Aviso flotante */}
      {aviso && (
        <div className={`${styles.toast} ${aviso.tipo === "err" ? styles.toastErr : styles.toastOk}`}>
          {aviso.texto}
        </div>
      )}

      {/* Body */}
      <main className={styles.body}>
        <div className={styles.container}>

          {/* Page title */}
          <div className={styles.pageTitle}>
            <span className={styles.titleIcon}><IconoEscudo /></span>
            <div>
              <h1>Roles y permisos</h1>
              <p>Crea permisos, agrúpalos en roles y asigna roles a los usuarios.</p>
            </div>
          </div>

          {/* ── Panel: Permisos ── */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <IconoLlave />
              Permisos
              <span className={styles.count}>{permisos.length}</span>
            </div>
            <div className={styles.panelBody}>
              <form onSubmit={alCrearPermiso} className={styles.formRow}>
                <input
                  className={`${styles.input} ${styles.inputCodigo}`}
                  type="text"
                  placeholder="Código (ej: A-01)"
                  value={nuevoPCodigo}
                  onChange={e => setNuevoPCodigo(e.target.value.toUpperCase())}
                  maxLength={50}
                />
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Nombre del permiso"
                  value={nuevoPNombre}
                  onChange={e => setNuevoPNombre(e.target.value)}
                  maxLength={150}
                />
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Descripción (opcional)"
                  value={nuevoPDesc}
                  onChange={e => setNuevoPDesc(e.target.value)}
                />
                <button
                  type="submit"
                  className={styles.btnCrear}
                  disabled={creandoPermiso || !nuevoPCodigo.trim() || !nuevoPNombre.trim()}
                >
                  {creandoPermiso ? <span className={styles.spinner} /> : <IconoMas />}
                  Crear
                </button>
              </form>

              {cargandoPermisos ? (
                <div className={styles.loading}><span className={styles.spinner} /> Cargando permisos…</div>
              ) : permisos.length === 0 ? (
                <p className={styles.empty}>Aún no hay permisos. Crea el primero arriba (por ejemplo A-01).</p>
              ) : (
                <div className={styles.permisoList}>
                  {permisosOrdenados.map(p => (
                    <div key={p.id} className={styles.permisoRow}>
                      <span className={styles.permisoCodigo}>{p.codigo}</span>
                      <div className={styles.permisoInfo}>
                        <div className={styles.permisoNombre}>{p.nombre}</div>
                        {p.descripcion && <div className={styles.permisoDesc}>{p.descripcion}</div>}
                      </div>
                      {confirmarP === p.id ? (
                        <div className={styles.confirmRow}>
                          <span className={styles.confirmText}>¿Eliminar?</span>
                          <button
                            className={`${styles.actionBtn} ${styles.btnEliminarConfirm}`}
                            onClick={() => alEliminarPermiso(p.id)}
                            disabled={eliminandoP === p.id}
                          >
                            {eliminandoP === p.id ? <span className={styles.spinnerSm} /> : <IconoCheck />}
                            Sí
                          </button>
                          <button
                            className={`${styles.actionBtn} ${styles.btnCancelar}`}
                            onClick={() => setConfirmarP(null)}
                          >
                            <IconoX tamano={13} /> No
                          </button>
                        </div>
                      ) : (
                        <button
                          className={`${styles.actionBtn} ${styles.btnEliminar}`}
                          onClick={() => setConfirmarP(p.id)}
                          title="Eliminar permiso"
                        >
                          <IconoBasura /> Eliminar
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* ── Panel: Roles ── */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <IconoEscudo />
              Roles
              <span className={styles.count}>{roles.length}</span>
            </div>
            <div className={styles.panelBody}>
              <form onSubmit={alCrearRol} className={styles.formRow}>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Nombre del rol (ej: Operador)"
                  value={nuevoRNombre}
                  onChange={e => setNuevoRNombre(e.target.value)}
                  maxLength={100}
                />
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Descripción (opcional)"
                  value={nuevoRDesc}
                  onChange={e => setNuevoRDesc(e.target.value)}
                />
                <button
                  type="submit"
                  className={styles.btnCrear}
                  disabled={creandoRol || !nuevoRNombre.trim()}
                >
                  {creandoRol ? <span className={styles.spinner} /> : <IconoMas />}
                  Crear
                </button>
              </form>

              {cargandoRoles ? (
                <div className={styles.loading}><span className={styles.spinner} /> Cargando roles…</div>
              ) : roles.length === 0 ? (
                <p className={styles.empty}>Aún no hay roles. Crea el primero arriba.</p>
              ) : (
                <div className={styles.rolList}>
                  {roles.map(r => {
                    const abierto = rolAbierto === r.id;
                    return (
                      <div key={r.id} className={`${styles.rolCard} ${abierto ? styles.rolCardOpen : ""}`}>
                        <button
                          className={styles.rolHeader}
                          onClick={() => abrirRol(r)}
                        >
                          <span className={`${styles.rolChevron} ${abierto ? styles.rolChevronOpen : ""}`}>
                            <IconoChevronDerecha />
                          </span>
                          <div className={styles.rolInfo}>
                            <div className={styles.rolNombre}>
                              {r.nombre}
                              {r.es_sistema && (
                                <span className={styles.badgeSistema}>
                                  <IconoCandado tamano={11} /> Sistema
                                </span>
                              )}
                            </div>
                            {r.descripcion && <div className={styles.rolDesc}>{r.descripcion}</div>}
                          </div>
                          <div className={styles.rolStats}>
                            <span className={styles.statChip}><IconoLlave /> {r.permisos.length} permisos</span>
                            <span className={styles.statChip}>{r.total_usuarios} usuarios</span>
                          </div>
                          {!r.es_sistema && (
                            <>
                              {confirmarR === r.id ? (
                                <div
                                  className={styles.confirmRow}
                                  onClick={e => e.stopPropagation()}
                                >
                                  <span className={styles.confirmText}>¿Eliminar?</span>
                                  <button
                                    className={`${styles.actionBtn} ${styles.btnEliminarConfirm}`}
                                    onClick={() => alEliminarRol(r.id)}
                                    disabled={eliminandoR === r.id}
                                  >
                                    {eliminandoR === r.id ? <span className={styles.spinnerSm} /> : <IconoCheck />}
                                    Sí
                                  </button>
                                  <button
                                    className={`${styles.actionBtn} ${styles.btnCancelar}`}
                                    onClick={() => setConfirmarR(null)}
                                  >
                                    <IconoX tamano={13} /> No
                                  </button>
                                </div>
                              ) : (
                                <button
                                  className={`${styles.actionBtn} ${styles.btnEliminar}`}
                                  onClick={e => { e.stopPropagation(); setConfirmarR(r.id); }}
                                  title="Eliminar rol"
                                >
                                  <IconoBasura /> Eliminar
                                </button>
                              )}
                            </>
                          )}
                        </button>

                        {abierto && (
                          <div className={styles.rolBody}>
                            <div className={styles.rolBodyHeader}>
                              <strong>Permisos asignados</strong>
                              <span className={styles.muted}>
                                {seleccionPermisos.size} de {permisos.length} seleccionados
                              </span>
                            </div>

                            {permisos.length === 0 ? (
                              <p className={styles.empty}>Crea permisos arriba para poder asignarlos a este rol.</p>
                            ) : (
                              <div className={styles.permisoGrid}>
                                {permisosOrdenados.map(p => {
                                  const seleccionado = seleccionPermisos.has(p.id);
                                  return (
                                    <button
                                      key={p.id}
                                      type="button"
                                      className={`${styles.permisoChip} ${seleccionado ? styles.permisoChipOn : ""}`}
                                      onClick={() => togglePermiso(p.id)}
                                    >
                                      <span className={styles.chipCheck}>
                                        {seleccionado ? <IconoCheck /> : null}
                                      </span>
                                      <span className={styles.chipCodigo}>{p.codigo}</span>
                                      <span className={styles.chipNombre}>{p.nombre}</span>
                                    </button>
                                  );
                                })}
                              </div>
                            )}

                            <div className={styles.rolBodyFooter}>
                              <button
                                className={styles.btnGuardar}
                                onClick={() => guardarPermisosRol(r.id)}
                                disabled={guardandoPermisosRol === r.id}
                              >
                                {guardandoPermisosRol === r.id
                                  ? <span className={styles.spinner} />
                                  : <IconoCheck />}
                                Guardar permisos
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
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
