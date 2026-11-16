import { useState } from "react";
import { apiAdmin, type Rol } from "../../../api/admin";
import { useNotificacion } from "../../../components/Notificaciones";
import { IconoCheck, IconoLlave, IconoMas } from "../../../components/Iconos";
import { LARGO_MINIMO_CONTRASENA, problemaContrasena } from "../../../utils/contrasena";
import { mensajeDeError } from "../../../utils/errores";
import styles from "../PaginaUsuarios.module.css";

interface Props {
  roles: Rol[];
  /** Tras crear la cuenta, relee la lista de la página. */
  alCrear: () => Promise<void>;
}

/** «Crear una cuenta local»: usuarios externos, como los de las agencias navieras
 *  (de PaginaUsuarios, 2026-11-14). */
export function FormularioCuentaLocal({ roles, alCrear }: Props) {
  const { mostrar: mostrarToast } = useNotificacion();
  const [mostrarLocal,   setMostrarLocal]   = useState(false);
  const [localUsername,  setLocalUsername]  = useState("");
  const [localPassword,  setLocalPassword]  = useState("");
  const [localNombre,    setLocalNombre]    = useState("");
  const [localApellido,  setLocalApellido]  = useState("");
  const [localEmail,     setLocalEmail]     = useState("");
  const [localRolId,     setLocalRolId]     = useState<number | "">("");
  const [creandoLocal,   setCreandoLocal]   = useState(false);
  const [errorLocal,     setErrorLocal]     = useState<string | null>(null);

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
      await alCrear();
      mostrarToast(`Cuenta local ${username} creada. Deberá cambiar la contraseña al entrar.`, "exito");
    } catch (err) {
      setErrorLocal(mensajeDeError(err, "No se pudo crear la cuenta local."));
    } finally {
      setCreandoLocal(false);
    }
  }

  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <IconoLlave />
        Crear una cuenta local (agencias navieras y usuarios sin dominio)
        <button
          type="button"
          className={styles.btnPanel}
          onClick={() => setMostrarLocal(v => !v)}
          aria-expanded={mostrarLocal}
        >
          {!mostrarLocal && <IconoMas tamano={14} />}
          {mostrarLocal ? "Ocultar" : "Crear cuenta"}
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
          {/* Con etiquetas visibles, como el resto de los formularios (antes solo
              el texto de ejemplo, que desaparece al escribir). */}
          <form onSubmit={alCrearLocal} className={styles.formLocal}>
            <label className={styles.campoLocal}>
              <span>Usuario *</span>
              <input className={styles.searchInput} autoComplete="off" spellCheck={false}
                value={localUsername} onChange={e => setLocalUsername(e.target.value)} maxLength={100} required />
            </label>
            <label className={styles.campoLocal}>
              <span>Contraseña inicial *</span>
              <input className={styles.searchInput} type="password" autoComplete="new-password"
                value={localPassword} onChange={e => setLocalPassword(e.target.value)} maxLength={64} required />
            </label>
            <label className={styles.campoLocal}>
              <span>Rol</span>
              <select className={styles.rolSelect} value={localRolId}
                onChange={e => setLocalRolId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">— Sin rol —</option>
                {roles.map(r => <option key={r.id} value={r.id}>{r.nombre}</option>)}
              </select>
            </label>
            <label className={styles.campoLocal}>
              <span>Nombre</span>
              <input className={styles.searchInput} value={localNombre} onChange={e => setLocalNombre(e.target.value)} maxLength={150} />
            </label>
            <label className={styles.campoLocal}>
              <span>Apellido</span>
              <input className={styles.searchInput} value={localApellido} onChange={e => setLocalApellido(e.target.value)} maxLength={150} />
            </label>
            <label className={styles.campoLocal}>
              <span>Correo <em>(recibe los avisos)</em></span>
              <input className={styles.searchInput} type="email" value={localEmail} onChange={e => setLocalEmail(e.target.value)} maxLength={255} />
            </label>
            <div className={styles.formLocalAcciones}>
              <button type="submit" className={styles.btnCrear} disabled={creandoLocal}>
                {creandoLocal ? <span className={styles.spinner} /> : <IconoCheck tamano={14} />}
                {creandoLocal ? "Creando…" : "Crear cuenta"}
              </button>
            </div>
          </form>
          {errorLocal && <p className={styles.searchError}>{errorLocal}</p>}
        </div>
      )}
    </section>
  );
}
