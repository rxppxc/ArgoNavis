import { useState, useEffect, useMemo } from "react";
import { apiAdmin, type Permiso, type Rol } from "../../api/admin";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useNotificacion } from "../../components/Notificaciones";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { mensajeDeError } from "../../utils/errores";
import {
  IconoLlave, IconoEscudo, IconoMas, IconoBasura,
  IconoCheck, IconoCandado, IconoChevronDerecha,
} from "../../components/Iconos";
import styles from "./PaginaRoles.module.css";

/** Roles y permisos (SysAdmin). Los permisos los define el sistema: el código
 *  revisa esos códigos, así que aquí solo se listan y se asignan a los roles. */
export default function PaginaRoles() {
  /* ── Permisos (solo lectura) ── */
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [cargandoPermisos, setCargandoPermisos] = useState(true);

  /* ── Roles ── */
  const [roles, setRoles] = useState<Rol[]>([]);
  const [cargandoRoles, setCargandoRoles] = useState(true);
  const [creandoRol, setCreandoRol] = useState(false);
  const [nuevoRNombre, setNuevoRNombre] = useState("");
  const [nuevoRDesc, setNuevoRDesc] = useState("");
  const [eliminandoR, setEliminandoR] = useState<number | null>(null);

  /* ── Rol expandido (vista de permisos asignados) ── */
  const [rolAbierto, setRolAbierto] = useState<number | null>(null);
  const [guardandoPermisosRol, setGuardandoPermisosRol] = useState<number | null>(null);
  const [seleccionPermisos, setSeleccionPermisos] = useState<Set<number>>(new Set());

  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();

  function mostrarAviso(texto: string, tipo: "ok" | "err" = "ok") {
    mostrar(texto, tipo === "ok" ? "exito" : "error");
  }

  useEffect(() => {
    let cancelado = false;
    apiAdmin.listarPermisos()
      .then(({ data }) => { if (!cancelado) setPermisos(data); })
      .catch((e) => { if (!cancelado) mostrar(mensajeDeError(e, "No se pudieron cargar los permisos."), "error"); })
      .finally(() => { if (!cancelado) setCargandoPermisos(false); });
    apiAdmin.listarRoles()
      .then(({ data }) => { if (!cancelado) setRoles(data); })
      .catch((e) => { if (!cancelado) mostrar(mensajeDeError(e, "No se pudieron cargar los roles."), "error"); })
      .finally(() => { if (!cancelado) setCargandoRoles(false); });
    return () => { cancelado = true; };
  }, [mostrar]);

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
    } catch (err) {
      mostrarAviso(mensajeDeError(err, "Error al crear el rol."), "err");
    } finally {
      setCreandoRol(false);
    }
  }

  async function alEliminarRol(rol: Rol) {
    const ok = await confirmar({
      titulo: "Eliminar rol",
      mensaje: rol.total_usuarios > 0
        ? `El rol "${rol.nombre}" tiene ${rol.total_usuarios} usuario(s): quedarán sin rol y sin acceso hasta que les asignes otro.`
        : `Se eliminará el rol "${rol.nombre}".`,
      textoOk: "Eliminar",
      peligroso: true,
    });
    if (!ok) return;
    setEliminandoR(rol.id);
    try {
      await apiAdmin.eliminarRol(rol.id);
      setRoles(prev => prev.filter(r => r.id !== rol.id));
      if (rolAbierto === rol.id) setRolAbierto(null);
      mostrarAviso("Rol eliminado.");
    } catch (err) {
      mostrarAviso(mensajeDeError(err, "Error al eliminar el rol."), "err");
    } finally {
      setEliminandoR(null);
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
    } catch (err) {
      mostrarAviso(mensajeDeError(err, "Error al guardar los permisos."), "err");
    } finally {
      setGuardandoPermisosRol(null);
    }
  }

  const permisosOrdenados = useMemo(
    () => [...permisos].sort((a, b) => a.codigo.localeCompare(b.codigo)),
    [permisos]
  );

  return (
    <MarcoPagina volverA="/dashboard">
        <div className={styles.container}>

          {/* Page title */}
          <div className={styles.pageTitle}>
            <span className={styles.titleIcon}><IconoEscudo /></span>
            <div>
              <h1>Roles y permisos</h1>
              <p>Agrupa los permisos del sistema en roles; los roles se asignan en Usuarios.</p>
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
              <p className={styles.nota}>
                Los define el sistema: cada uno habilita una parte del flujo. Para dar acceso, asígnalos a un rol.
              </p>
              {cargandoPermisos ? (
                <div className={styles.loading}><span className={styles.spinner} /> Cargando permisos…</div>
              ) : (
                <div className={styles.permisoList}>
                  {permisosOrdenados.map(p => (
                    <div key={p.id} className={styles.permisoRow}>
                      <span className={styles.permisoCodigo}>{p.codigo}</span>
                      <div className={styles.permisoInfo}>
                        <div className={styles.permisoNombre}>{p.nombre}</div>
                        {p.descripcion && <div className={styles.permisoDesc}>{p.descripcion}</div>}
                      </div>
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
                        <div className={styles.rolHeader}>
                          <button
                            type="button"
                            className={styles.rolToggle}
                            onClick={() => abrirRol(r)}
                            aria-expanded={abierto}
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
                          </button>
                          {!r.es_sistema && (
                            <button
                              type="button"
                              className={`${styles.actionBtn} ${styles.btnEliminar}`}
                              onClick={() => alEliminarRol(r)}
                              disabled={eliminandoR === r.id}
                              title="Eliminar rol"
                            >
                              {eliminandoR === r.id ? <span className={styles.spinnerSm} /> : <IconoBasura />} Eliminar
                            </button>
                          )}
                        </div>

                        {abierto && (
                          <div className={styles.rolBody}>
                            <div className={styles.rolBodyHeader}>
                              <strong>Permisos asignados</strong>
                              <span className={styles.muted}>
                                {seleccionPermisos.size} de {permisos.length} seleccionados
                              </span>
                            </div>

                            {permisos.length === 0 ? (
                              <p className={styles.empty}>No hay permisos para asignar.</p>
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
    </MarcoPagina>
  );
}
