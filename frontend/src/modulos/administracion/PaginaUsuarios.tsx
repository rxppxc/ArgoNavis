import { useState, useEffect, useCallback } from "react";
import { apiAdmin, type UsuarioSistema, type Rol } from "../../api/admin";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { useNotificacion } from "../../components/Notificaciones";
import { useConfirmar } from "../../components/ModalConfirmacion";
import { MarcoPagina } from "../../components/MarcoPagina";
import { EncabezadoPagina } from "../../components/EncabezadoPagina";
import { RelojHorario } from "../../components/RelojHorario";
import { usePermisos } from "../../hooks/usePermisos";
import { copiarAlPortapapeles } from "../../utils/portapapeles";
import { mensajeDeError } from "../../utils/errores";
import { BusquedaAD } from "./usuarios/BusquedaAD";
import { FormularioCuentaLocal } from "./usuarios/FormularioCuentaLocal";
import { TablaUsuarios } from "./usuarios/TablaUsuarios";
import styles from "./PaginaUsuarios.module.css";

/** Usuarios: alta desde el AD o local, rol, estado, contraseña temporal y baja.
 *  Cada bloque es su componente (usuarios/, 2026-11-14); aquí viven la lista, los
 *  roles y las acciones de la tabla. */
export default function PaginaUsuarios() {
  const { usuario } = useAutenticacion();
  const { esSysAdmin } = usePermisos();
  const { mostrar: mostrarToast } = useNotificacion();
  const confirmar = useConfirmar();

  const [usuarios,      setUsuarios]      = useState<UsuarioSistema[]>([]);
  const [roles,         setRoles]         = useState<Rol[]>([]);
  const [cargando,      setCargando]      = useState(true);
  const [ocupado,       setOcupado]       = useState<number | null>(null);
  const [claveTemporal, setClaveTemporal] = useState<{ username: string; clave: string } | null>(null);

  /** Relee la lista tras una acción que ya se hizo: si falla, no la da por
   *  fallida (antes decía «No se pudo agregar» de una cuenta que sí se creó). */
  const cargarUsuarios = useCallback(async () => {
    try {
      setUsuarios((await apiAdmin.listarUsuarios()).data);
    } catch {
      mostrarToast("Listo, pero la lista no se pudo actualizar: recarga la página para verla al día.", "aviso");
    }
  }, [mostrarToast]);

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

  async function alCambiarEstado(u: UsuarioSistema) {
    setOcupado(u.id);
    const nuevoEstado = u.status === "active" ? "inactive" : "active";
    try {
      const { data } = await apiAdmin.cambiarEstado(u.id, nuevoEstado);
      setUsuarios(prev => prev.map(x => x.id === u.id ? data : x));
      mostrarToast(`Usuario ${nuevoEstado === "active" ? "activado" : "desactivado"}.`, "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "No se pudo cambiar el estado."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function alAsignarRol(id: number, rol_id: number | null) {
    setOcupado(id);
    try {
      const { data } = await apiAdmin.asignarRolAUsuario(id, rol_id);
      setUsuarios(prev => prev.map(u => u.id === id ? data : u));
      mostrarToast("Rol asignado.", "exito");
    } catch (err) {
      mostrarToast(mensajeDeError(err, "No se pudo asignar el rol."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function alRestablecer(u: UsuarioSistema) {
    const ok = await confirmar({
      titulo: "Restablecer contraseña",
      mensaje: `Se generará una contraseña temporal para @${u.username} y se desbloqueará la cuenta. Deberá cambiarla al entrar.`,
      textoOk: "Restablecer",
      tono: "clave",
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
      mostrarToast(mensajeDeError(err, "No se pudo eliminar el usuario."), "error");
    } finally {
      setOcupado(null);
    }
  }

  async function copiarClave() {
    if (!claveTemporal) return;
    const ok = await copiarAlPortapapeles(claveTemporal.clave);
    mostrarToast(ok ? "Contraseña copiada." : "No se pudo copiar: cópiala a mano.", ok ? "exito" : "aviso");
  }

  return (
    <MarcoPagina volverA="/dashboard" ancho="amplio">
      <div className={styles.container}>

        <EncabezadoPagina
          titulo="Usuarios"
          descripcion="Agrega usuarios del Active Directory o crea cuentas locales para usuarios externos."
        />

        {/* Es el inicio del SysAdmin: lleva el reloj, como las bandejas (2026-11-24), en franja bajo
            el encabezado (2026-11-27). Sin el recargo, que es de las solicitudes y él no las ve. */}
        {esSysAdmin && <RelojHorario conRecargo={false} />}

        {claveTemporal && (
          <section className={`${styles.panel} ${styles.claveTemporal}`} role="status">
            <div className={styles.panelBody}>
              <strong>Contraseña temporal de @{claveTemporal.username}:</strong>
              <code>{claveTemporal.clave}</code>
              <button type="button" className={styles.searchBtn} onClick={copiarClave}>Copiar</button>
              <button type="button" className={styles.actionBtn} onClick={() => setClaveTemporal(null)}>
                Listo
              </button>
              <p>Entrégala por un medio seguro: no se volverá a mostrar. Al entrar, el sistema le pedirá cambiarla.</p>
            </div>
          </section>
        )}

        <BusquedaAD registrados={new Set(usuarios.map(u => u.username))} alAgregar={cargarUsuarios} />
        <FormularioCuentaLocal roles={roles} alCrear={cargarUsuarios} />
        <TablaUsuarios
          usuarios={usuarios} roles={roles} cargando={cargando} idPropio={usuario?.id} ocupado={ocupado}
          alCambiarEstado={alCambiarEstado} alAsignarRol={alAsignarRol} alRestablecer={alRestablecer}
          alEliminar={alEliminar}
        />

      </div>
    </MarcoPagina>
  );
}
