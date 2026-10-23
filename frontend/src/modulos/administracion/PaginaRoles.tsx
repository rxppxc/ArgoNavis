import { useState, useEffect, useMemo } from "react";
import { apiAdmin, type Permiso, type Rol } from "../../api/admin";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { EstadoCarga } from "../../components/EstadoCarga";
import { useNotificacion } from "../../components/Notificaciones";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { mensajeDeError } from "../../utils/errores";
import {
  IconoLlave, IconoEscudo, IconoMas, IconoBasura,
  IconoCheck, IconoCandado, IconoChevronDerecha,
} from "../../components/Iconos";
import styles from "./PaginaRoles.module.css";

/** Roles fijos: se reconocen por el nombre, que no cambia, y sus permisos no se
 *  editan (el backend responde 400). */
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

const NOTA_ROL_FIJO: Record<string, string> = {
  Administrador: "Tiene acceso a todo el sistema por su rol: sus permisos no se editan.",
  SysAdmin: "Administra usuarios, roles y la bitácora, y no ve solicitudes: sus permisos no se editan.",
};

/** Roles y permisos (Administrador y SysAdmin). Los permisos los define el
 *  sistema: el código revisa esos códigos, así que aquí solo se listan y se
 *  asignan a los roles. */
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
  const [edicion, setEdicion] = useState({ nombre: "", descripcion: "" });
  const [guardandoDatos, setGuardandoDatos] = useState<number | null>(null);

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
    if (!nombre) {
      mostrarAviso("Escribe el nombre del rol.", "err");
      return;
    }
    setCreandoRol(true);
    try {
      const { data } = await apiAdmin.crearRol(nombre, nuevoRDesc.trim() || undefined);
      setRoles(prev => [...prev, data].sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setNuevoRNombre(""); setNuevoRDesc("");
      mostrarAviso("Rol creado.");
    } catch (err) {
      mostrarAviso(mensajeDeError(err, "No se pudo crear el rol."), "err");
    } finally {
      setCreandoRol(false);
    }
  }

  async function alEliminarRol(rol: Rol) {
    const ok = await confirmar({
      titulo: "Eliminar rol",
      mensaje: rol.total_usuarios > 0
        ? `El rol "${rol.nombre}" tiene ${plural(rol.total_usuarios, "usuario", "usuarios")}: quedarán sin rol y sin acceso hasta que les asignes otro.`
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
      mostrarAviso(mensajeDeError(err, "No se pudo eliminar el rol."), "err");
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
    setEdicion({ nombre: rol.nombre, descripcion: rol.descripcion ?? "" });
  }

  async function guardarDatosRol(rol: Rol) {
    const nombre = edicion.nombre.trim();
    if (!nombre) {
      mostrarAviso("El nombre del rol no puede quedar vacío.", "err");
      return;
    }
    setGuardandoDatos(rol.id);
    try {
      const { data } = await apiAdmin.actualizarRol(rol.id, {
        ...(nombre !== rol.nombre ? { nombre } : {}),
        descripcion: edicion.descripcion.trim(),
      });
      setRoles(prev => prev.map(r => r.id === rol.id ? data : r).sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setEdicion({ nombre: data.nombre, descripcion: data.descripcion ?? "" });
      mostrarAviso("Datos del rol guardados.");
    } catch (err) {
      mostrarAviso(mensajeDeError(err, "No se pudo guardar el rol."), "err");
    } finally {
      setGuardandoDatos(null);
    }
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
      mostrarAviso(mensajeDeError(err, "No se pudieron guardar los permisos."), "err");
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

          <EncabezadoPagina
            titulo="Roles y permisos"
            descripcion="Agrupa los permisos del sistema en roles; los roles se asignan en Usuarios."
          />

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
                <EstadoCarga texto="Cargando permisos…" />
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
                  placeholder="Nombre del rol (p. ej. Operador)"
                  aria-label="Nombre del rol nuevo"
                  value={nuevoRNombre}
                  onChange={e => setNuevoRNombre(e.target.value)}
                  maxLength={100}
                />
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Descripción (opcional)"
                  aria-label="Descripción del rol nuevo"
                  value={nuevoRDesc}
                  onChange={e => setNuevoRDesc(e.target.value)}
                />
                <button
                  type="submit"
                  className={styles.btnCrear}
                  disabled={creandoRol}
                >
                  {creandoRol ? <span className={styles.spinner} /> : <IconoMas />}
                  Crear
                </button>
              </form>

              {cargandoRoles ? (
                <EstadoCarga texto="Cargando roles…" />
              ) : roles.length === 0 ? (
                <p className={styles.empty}>Aún no hay roles. Crea el primero arriba.</p>
              ) : (
                <div className={styles.rolList}>
                  {roles.map(r => {
                    const abierto = rolAbierto === r.id;
                    const notaFijo = NOTA_ROL_FIJO[r.nombre];
                    const sinCambios = edicion.nombre.trim() === r.nombre
                      && edicion.descripcion.trim() === (r.descripcion ?? "");
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
                              <span className={styles.statChip}><IconoLlave /> {plural(r.permisos.length, "permiso", "permisos")}</span>
                              <span className={styles.statChip}>{plural(r.total_usuarios, "usuario", "usuarios")}</span>
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
                              <strong>Datos del rol</strong>
                            </div>
                            <div className={styles.datosRol}>
                              <input
                                className={styles.input}
                                type="text"
                                aria-label="Nombre del rol"
                                value={edicion.nombre}
                                onChange={e => setEdicion(prev => ({ ...prev, nombre: e.target.value }))}
                                maxLength={100}
                                disabled={!!notaFijo}
                                title={notaFijo ? "Este rol no se puede renombrar" : undefined}
                              />
                              <input
                                className={styles.input}
                                type="text"
                                aria-label="Descripción del rol"
                                placeholder="Descripción (opcional)"
                                value={edicion.descripcion}
                                onChange={e => setEdicion(prev => ({ ...prev, descripcion: e.target.value }))}
                                maxLength={255}
                              />
                              <button
                                type="button"
                                className={styles.btnSecundario}
                                onClick={() => guardarDatosRol(r)}
                                disabled={guardandoDatos === r.id || sinCambios}
                              >
                                {guardandoDatos === r.id ? <span className={styles.spinnerSm} /> : <IconoCheck />}
                                Guardar datos
                              </button>
                            </div>

                            {notaFijo ? (
                              <>
                                <div className={styles.rolBodyHeader}><strong>Permisos</strong></div>
                                <p className={styles.nota}>{notaFijo}</p>
                              </>
                            ) : (
                              <>
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
                                          aria-pressed={seleccionado}
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
                              </>
                            )}

                            {!notaFijo && (
                              <div className={styles.rolBodyFooter}>
                                <button
                                  type="button"
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
                            )}
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
