/**
 * Catálogos del flujo de Autorizaciones Marítimas (solo admin):
 *  - Agencias navieras: alta, edición, activación y sus usuarios (comparten
 *    las solicitudes de la agencia).
 *  - Puestos de control: alta, edición, activación y funcionarios asignados
 *    (los que ven y finalizan las autorizaciones de ese puesto).
 *  - Nacionalidades restringidas: en Desembarque exigen el Formulario No. 6 de
 *    custodia; en los trámites que lo indican, la aprobación avisa la custodia.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiAdmin, type Rol, type UsuarioSistema } from "../../api/admin";
import {
  apiCatalogos, type CatalogoConUsuarios, type DatosCatalogo, type Pais,
} from "../../api/catalogos";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoBasura, IconoBuscar, IconoEditar, IconoMas, IconoUsuarios } from "../../components/Iconos";
import { mensajeDeError } from "../../utils/errores";
import styles from "./PaginaCatalogos.module.css";

type Pestana = "agencias" | "puestos" | "paises";
type Tipo = "agencia" | "puesto";

const PERMISO_POR_TIPO: Record<Tipo, string> = {
  agencia: "T-CREAR-BASICA",
  puesto:  "T-FINALIZAR-PUERTO",
};

/** Textos y llamadas a la API de cada catálogo (misma forma, distinto recurso). */
const CONFIG: Record<Tipo, {
  singular: string; usuarios: string; placeholder: string; ayudaCandidatos: string;
  actualizar: (id: number, datos: DatosCatalogo) => Promise<CatalogoConUsuarios>;
  eliminar:   (id: number) => Promise<unknown>;
  asignar:    (id: number, ids: number[]) => Promise<CatalogoConUsuarios>;
}> = {
  agencia: {
    singular: "agencia", usuarios: "usuarios", placeholder: "Correo de la agencia (opcional)",
    ayudaCandidatos: "Se listan los usuarios cuyo rol tiene el permiso T-CREAR-BASICA. Un usuario es de una sola agencia: asignarlo aquí lo saca de la que tenga.",
    actualizar: apiCatalogos.actualizarAgencia, eliminar: apiCatalogos.eliminarAgencia, asignar: apiCatalogos.asignarUsuariosAgencia,
  },
  puesto: {
    singular: "puesto", usuarios: "funcionarios", placeholder: "Correo del puesto (opcional)",
    ayudaCandidatos: "Se listan los usuarios cuyo rol tiene el permiso T-FINALIZAR-PUERTO.",
    actualizar: apiCatalogos.actualizarPuesto, eliminar: apiCatalogos.eliminarPuesto, asignar: apiCatalogos.asignarUsuariosPuesto,
  },
};

function TarjetaCatalogo({
  tipo, entidad, usuarios, rolesCandidatos, onCambio,
}: {
  tipo: Tipo;
  entidad: CatalogoConUsuarios;
  usuarios: UsuarioSistema[];
  rolesCandidatos: Set<number>;
  onCambio: (e: CatalogoConUsuarios | null, id: number) => void;
}) {
  const config = CONFIG[tipo];
  const { mostrar } = useNotificacion();
  const confirmar = useConfirmar();
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(entidad.nombre);
  const [correo, setCorreo] = useState(entidad.correo ?? "");
  const [asignando, setAsignando] = useState(false);
  const [seleccion, setSeleccion] = useState<Set<number>>(new Set(entidad.usuarios.map((u) => u.id)));
  const [todos, setTodos] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const candidatos = usuarios.filter(
    (u) => todos || (u.rol_id !== null && rolesCandidatos.has(u.rol_id)) || seleccion.has(u.id),
  );

  async function guardarDatos() {
    setGuardando(true);
    try {
      onCambio(await config.actualizar(entidad.id, { nombre: nombre.trim(), correo: correo.trim() || null }), entidad.id);
      setEditando(false);
      mostrar("Cambios guardados.", "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo guardar."), "error");
    } finally {
      setGuardando(false);
    }
  }

  async function alternarActivo() {
    try {
      onCambio(await config.actualizar(entidad.id, { activo: !entidad.activo }), entidad.id);
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo cambiar el estado."), "error");
    }
  }

  async function eliminar() {
    const ok = await confirmar({
      titulo: `Eliminar ${config.singular}`,
      mensaje: `Se eliminará "${entidad.nombre}". Sus ${config.usuarios} quedan sin asignar.`,
      textoOk: "Eliminar",
      peligroso: true,
    });
    if (!ok) return;
    try {
      await config.eliminar(entidad.id);
      onCambio(null, entidad.id);
      mostrar("Eliminado.", "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo eliminar."), "error");
    }
  }

  async function guardarAsignacion() {
    setGuardando(true);
    try {
      onCambio(await config.asignar(entidad.id, [...seleccion]), entidad.id);
      setAsignando(false);
      mostrar("Asignación guardada.", "exito");
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo guardar la asignación."), "error");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={`${styles.tarjeta} ${entidad.activo ? "" : styles.inactivo}`}>
      <div className={styles.tarjetaCabecera}>
        {editando ? (
          <div className={styles.formEnLinea}>
            <input className={styles.input} value={nombre} maxLength={200} onChange={(e) => setNombre(e.target.value)} />
            <input className={styles.input} value={correo} maxLength={255} type="email"
              placeholder={config.placeholder} onChange={(e) => setCorreo(e.target.value)} />
            <button type="button" className={styles.btnPrimario} onClick={guardarDatos} disabled={guardando || nombre.trim().length < 3}>
              Guardar
            </button>
            <button type="button" className={styles.btnTexto} onClick={() => { setEditando(false); setNombre(entidad.nombre); setCorreo(entidad.correo ?? ""); }}>
              Cancelar
            </button>
          </div>
        ) : (
          <>
            <div className={styles.tarjetaInfo}>
              <div className={styles.tarjetaNombre}>{entidad.nombre}</div>
              <div className={styles.tarjetaMeta}>
                {entidad.correo ?? "Sin correo"} · {entidad.total_solicitudes} solicitud{entidad.total_solicitudes === 1 ? "" : "es"}
              </div>
            </div>
            <label className={styles.interruptor} title={entidad.activo ? "Desactivar" : "Activar"}>
              <input type="checkbox" checked={entidad.activo} onChange={alternarActivo} />
              <span>{entidad.activo ? "Activo" : "Inactivo"}</span>
            </label>
            <button type="button" className={styles.btnIcono} onClick={() => setEditando(true)} title="Editar" aria-label={`Editar ${entidad.nombre}`}>
              <IconoEditar tamano={14} />
            </button>
            <button type="button" className={`${styles.btnIcono} ${styles.peligro}`} onClick={eliminar}
              disabled={entidad.total_solicitudes > 0}
              title={entidad.total_solicitudes > 0 ? "Tiene solicitudes: desactívalo en lugar de eliminarlo" : "Eliminar"}
              aria-label={`Eliminar ${entidad.nombre}`}>
              <IconoBasura tamano={14} />
            </button>
          </>
        )}
      </div>

      <div className={styles.asignados}>
        <IconoUsuarios tamano={14} />
        {entidad.usuarios.length === 0
          ? <span className={styles.vacio}>Sin {config.usuarios} asignados</span>
          : entidad.usuarios.map((u) => <span key={u.id} className={styles.chip}>{u.full_name}</span>)}
        <button type="button" className={styles.btnSecundario} onClick={() => {
          // Al abrir, parte de la asignación vigente (otra tarjeta pudo cambiarla).
          if (!asignando) setSeleccion(new Set(entidad.usuarios.map((u) => u.id)));
          setAsignando((v) => !v);
        }}>
          {asignando ? "Cerrar" : `Asignar ${config.usuarios}`}
        </button>
      </div>

      {asignando && (
        <div className={styles.selector}>
          <p className={styles.ayuda}>
            {config.ayudaCandidatos}
            <label className={styles.checkTodos}>
              <input type="checkbox" checked={todos} onChange={(e) => setTodos(e.target.checked)} /> Mostrar todos los usuarios
            </label>
          </p>
          <div className={styles.listaUsuarios}>
            {candidatos.length === 0 && <span className={styles.vacio}>No hay usuarios con ese permiso.</span>}
            {candidatos.map((u) => {
              const otraAgencia = tipo === "agencia" && u.agencia && u.agencia.id !== entidad.id ? u.agencia.nombre : null;
              return (
                <label key={u.id} className={styles.opcionUsuario}>
                  <input type="checkbox" checked={seleccion.has(u.id)}
                    onChange={(e) => setSeleccion((prev) => {
                      const s = new Set(prev);
                      if (e.target.checked) s.add(u.id); else s.delete(u.id);
                      return s;
                    })} />
                  <span>{u.full_name}</span>
                  <em>
                    @{u.username}{u.rol_personalizado ? ` · ${u.rol_personalizado.nombre}` : ""}
                    {otraAgencia && ` · hoy en ${otraAgencia}`}
                  </em>
                </label>
              );
            })}
          </div>
          <div className={styles.filaBotones}>
            <button type="button" className={styles.btnPrimario} onClick={guardarAsignacion} disabled={guardando}>
              Guardar asignación
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SeccionCatalogo({
  tipo, lista, usuarios, rolesCandidatos, onCambio, onCreado, descripcion, vacio,
}: {
  tipo: Tipo;
  lista: CatalogoConUsuarios[];
  usuarios: UsuarioSistema[];
  rolesCandidatos: Set<number>;
  onCambio: (e: CatalogoConUsuarios | null, id: number) => void;
  onCreado: (e: CatalogoConUsuarios) => void;
  descripcion: string;
  vacio: string;
}) {
  const { mostrar } = useNotificacion();
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [creando, setCreando] = useState(false);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    if (nombre.trim().length < 3) return;
    setCreando(true);
    try {
      const crearEn = tipo === "agencia" ? apiCatalogos.crearAgencia : apiCatalogos.crearPuesto;
      onCreado(await crearEn(nombre.trim(), correo.trim() || null));
      setNombre("");
      setCorreo("");
      mostrar(tipo === "agencia" ? "Agencia naviera creada." : "Puesto de control creado.", "exito");
    } catch (err) {
      mostrar(mensajeDeError(err, "No se pudo crear."), "error");
    } finally {
      setCreando(false);
    }
  }

  return (
    <>
      <p className={styles.descripcion}>{descripcion}</p>
      <form className={styles.formNuevo} onSubmit={crear}>
        <input className={styles.input} maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)}
          placeholder={tipo === "agencia" ? "Nombre de la agencia naviera" : "Nombre del puesto (ej. Puerto de Balboa)"} />
        <input className={styles.input} type="email" maxLength={255} value={correo} onChange={(e) => setCorreo(e.target.value)}
          placeholder={CONFIG[tipo].placeholder} />
        <button type="submit" className={styles.btnPrimario} disabled={creando || nombre.trim().length < 3}>
          <IconoMas tamano={14} /> {tipo === "agencia" ? "Agregar agencia" : "Agregar puesto"}
        </button>
      </form>
      {lista.length === 0 ? (
        <div className={styles.vacioGrande}>{vacio}</div>
      ) : (
        <div className={styles.lista}>
          {lista.map((e) => (
            <TarjetaCatalogo key={e.id} tipo={tipo} entidad={e} usuarios={usuarios}
              rolesCandidatos={rolesCandidatos} onCambio={onCambio} />
          ))}
        </div>
      )}
    </>
  );
}

function ordenar(lista: CatalogoConUsuarios[]): CatalogoConUsuarios[] {
  return [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
}

export default function PaginaCatalogos() {
  const { mostrar } = useNotificacion();
  const [pestana, setPestana] = useState<Pestana>("agencias");
  const [agencias, setAgencias] = useState<CatalogoConUsuarios[]>([]);
  const [puestos, setPuestos] = useState<CatalogoConUsuarios[]>([]);
  const [paises, setPaises] = useState<Pais[]>([]);
  const [usuarios, setUsuarios] = useState<UsuarioSistema[]>([]);
  const [roles, setRoles] = useState<Rol[]>([]);
  const [cargando, setCargando] = useState(true);

  const [buscarPais, setBuscarPais] = useState("");
  const [soloRestringidas, setSoloRestringidas] = useState(false);

  const recargarUsuarios = useCallback(() => {
    apiAdmin.listarUsuarios().then((r) => setUsuarios(r.data)).catch(() => { /* la lista anterior sigue sirviendo */ });
  }, []);

  useEffect(() => {
    let cancelado = false;
    Promise.all([
      apiCatalogos.listarAgenciasAdmin(), apiCatalogos.listarPuestosAdmin(), apiCatalogos.listarPaises(),
      apiAdmin.listarUsuarios(), apiAdmin.listarRoles(),
    ])
      .then(([a, p, pa, u, r]) => {
        if (cancelado) return;
        setAgencias(a);
        setPuestos(p);
        setPaises(pa);
        setUsuarios(u.data);
        setRoles(r.data);
      })
      .catch((e) => { if (!cancelado) mostrar(mensajeDeError(e, "No se pudieron cargar los catálogos."), "error"); })
      .finally(() => { if (!cancelado) setCargando(false); });
    return () => { cancelado = true; };
  }, [mostrar]);

  const rolesCon = useCallback(
    (permiso: string) => new Set(
      roles.filter((r) => r.nombre === "Administrador" || r.permisos.some((p) => p.codigo === permiso)).map((r) => r.id),
    ),
    [roles],
  );
  const rolesAgencia = useMemo(() => rolesCon(PERMISO_POR_TIPO.agencia), [rolesCon]);
  const rolesPuerto = useMemo(() => rolesCon(PERMISO_POR_TIPO.puesto), [rolesCon]);

  const cambiarAgencia = useCallback((a: CatalogoConUsuarios | null, id: number) => {
    // Asignar usuarios a una agencia puede sacarlos de otra: se releen todas.
    setAgencias((prev) => (a ? prev.map((x) => (x.id === id ? a : x)) : prev.filter((x) => x.id !== id)));
    apiCatalogos.listarAgenciasAdmin().then(setAgencias).catch(() => { /* queda la versión local */ });
    recargarUsuarios();
  }, [recargarUsuarios]);

  const cambiarPuesto = useCallback((p: CatalogoConUsuarios | null, id: number) => {
    setPuestos((prev) => (p ? prev.map((x) => (x.id === id ? p : x)) : prev.filter((x) => x.id !== id)));
  }, []);

  async function alternarRestringida(pais: Pais) {
    try {
      const actualizado = await apiCatalogos.actualizarPais(pais.codigo, !pais.nacionalidad_restringida);
      setPaises((prev) => prev.map((p) => (p.codigo === actualizado.codigo ? actualizado : p)));
      mostrar(
        `${actualizado.nombre}: ${actualizado.nacionalidad_restringida ? "marcada como restringida" : "ya no es restringida"}.`,
        "exito",
      );
    } catch (e) {
      mostrar(mensajeDeError(e, "No se pudo actualizar el país."), "error");
    }
  }

  const termino = buscarPais.trim().toLowerCase();
  const paisesVisibles = paises.filter((p) =>
    (!soloRestringidas || p.nacionalidad_restringida) &&
    (!termino || p.nombre.toLowerCase().includes(termino) || p.codigo.toLowerCase().includes(termino)),
  );
  const totalRestringidas = paises.filter((p) => p.nacionalidad_restringida).length;

  const pestanas: { id: Pestana; etiqueta: string; conteo: number }[] = [
    { id: "agencias", etiqueta: "Agencias navieras", conteo: agencias.length },
    { id: "puestos", etiqueta: "Puestos de control", conteo: puestos.length },
    { id: "paises", etiqueta: "Nacionalidades restringidas", conteo: totalRestringidas },
  ];

  return (
    <MarcoPagina volverA="/dashboard">
      <div className={styles.titulo}>
        <h1>Agencias, puestos y países</h1>
        <p>Catálogos del flujo de autorizaciones marítimas.</p>
      </div>

      <div className={styles.pestanas} role="tablist">
        {pestanas.map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={pestana === p.id}
            className={`${styles.pestana} ${pestana === p.id ? styles.pestanaActiva : ""}`}
            onClick={() => setPestana(p.id)}>
            {p.etiqueta} <span className={styles.conteo}>{p.conteo}</span>
          </button>
        ))}
      </div>

      {cargando ? (
        <div className={styles.vacioGrande}>Cargando…</div>
      ) : pestana === "agencias" ? (
        <SeccionCatalogo
          tipo="agencia" lista={agencias} usuarios={usuarios} rolesCandidatos={rolesAgencia}
          onCambio={cambiarAgencia}
          onCreado={(a) => setAgencias((prev) => ordenar([...prev, a]))}
          descripcion={
            "Cada solicitud pertenece a una agencia naviera: todos sus usuarios la ven, la corrigen y descargan la "
            + "autorización. Los avisos van al correo de la agencia y a sus usuarios. Un usuario sin agencia no puede "
            + "enviar solicitudes. Si desactivas una agencia, sus usuarios no pueden entrar (se les cierra la sesión)."
          }
          vacio="Aún no hay agencias navieras. Agrega la primera y asígnale sus usuarios."
        />
      ) : pestana === "puestos" ? (
        <SeccionCatalogo
          tipo="puesto" lista={puestos} usuarios={usuarios} rolesCandidatos={rolesPuerto}
          onCambio={cambiarPuesto}
          onCreado={(p) => setPuestos((prev) => ordenar([...prev, p]))}
          descripcion={
            "Cada solicitud indica el puesto donde se hará el trámite. Al aprobarse, se avisa al correo del puesto y a "
            + "sus funcionarios asignados, que son los únicos que pueden comentarla y finalizarla."
          }
          vacio="Aún no hay puestos de control. Agrega el primero para que las agencias puedan elegirlo."
        />
      ) : (
        <>
          <p className={styles.descripcion}>
            A los tripulantes de una nacionalidad restringida se les exige el Formulario No. 6 de custodia en
            Desembarque. En Desembarque, Urgencias, Renovación de pasaporte y Shore Pass, al aprobar se avisa a la
            agencia que debe realizar el trámite de solicitud de custodia. El cambio aplica a las solicitudes que se
            envíen desde ahora.
          </p>
          <div className={styles.barraPaises}>
            <div className={styles.buscador}>
              <IconoBuscar tamano={14} />
              <input placeholder="Buscar país o código…" value={buscarPais} onChange={(e) => setBuscarPais(e.target.value)} />
            </div>
            <label className={styles.checkTodos}>
              <input type="checkbox" checked={soloRestringidas} onChange={(e) => setSoloRestringidas(e.target.checked)} />
              Solo restringidas
            </label>
          </div>
          <div className={styles.paises}>
            {paisesVisibles.map((p) => (
              <label key={p.codigo} className={`${styles.pais} ${p.nacionalidad_restringida ? styles.paisRestringido : ""}`}>
                <input type="checkbox" checked={p.nacionalidad_restringida} onChange={() => alternarRestringida(p)} />
                <span className={styles.paisNombre}>{p.nombre}</span>
                <span className={styles.paisCodigo}>{p.codigo}</span>
              </label>
            ))}
            {paisesVisibles.length === 0 && <span className={styles.vacio}>Ningún país coincide.</span>}
          </div>
        </>
      )}
    </MarcoPagina>
  );
}
