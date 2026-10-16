/**
 * Cambio de contraseña de una cuenta local (las del AD se cambian en Windows).
 *
 * Es paso obligatorio cuando el admin crea la cuenta o restablece su
 * contraseña: hasta cambiarla, el backend no deja usar nada más.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MarcoPagina } from "../../components/MarcoPagina";
import { useNotificacion } from "../../components/Notificaciones";
import { IconoAlerta, IconoCandado } from "../../components/Iconos";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { problemaContrasena, requisitosContrasena } from "../../utils/contrasena";
import { mensajeDeError } from "../../utils/errores";
import styles from "./PaginaCambiarContrasena.module.css";

export default function PaginaCambiarContrasena() {
  const { usuario, cambiarContrasena, cerrarSesion } = useAutenticacion();
  const { mostrar } = useNotificacion();
  const navegar = useNavigate();
  const obligatorio = !!usuario?.debe_cambiar_password;

  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const problema = nueva ? problemaContrasena(nueva, usuario?.username) : null;
  const requisitos = requisitosContrasena(nueva);
  const faltanRequisitos = requisitos.some((r) => !r.cumple);
  const noCoinciden = !!confirmacion && confirmacion !== nueva;

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (problemaContrasena(nueva, usuario?.username) || nueva !== confirmacion) return;
    setGuardando(true);
    try {
      await cambiarContrasena(actual, nueva);
      mostrar("Contraseña actualizada.", "exito");
      navegar("/dashboard", { replace: true });
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo cambiar la contraseña."));
    } finally {
      setGuardando(false);
    }
  }

  async function salir() {
    await cerrarSesion(true, false);
    navegar("/login", { replace: true });
  }

  if (usuario?.user_type === "ad") {
    return (
      <MarcoPagina volverA="/dashboard">
        <div className={styles.tarjeta}>
          <h1>Cambiar contraseña</h1>
          <p className={styles.ayuda}>
            Tu cuenta es del Active Directory: la contraseña se cambia en Windows o con la Dirección de
            Tecnología e Innovación.
          </p>
        </div>
      </MarcoPagina>
    );
  }

  return (
    <MarcoPagina volverA={obligatorio ? undefined : "/dashboard"}>
      <form className={styles.tarjeta} onSubmit={guardar} noValidate>
        <div className={styles.icono}><IconoCandado /></div>
        <h1>Cambiar contraseña</h1>
        {obligatorio ? (
          <div className={styles.aviso}>
            <IconoAlerta tamano={15} />
            Antes de continuar debes elegir una contraseña nueva: la que tienes te la dio el administrador o
            ya no cumple los requisitos de seguridad.
          </div>
        ) : (
          <p className={styles.ayuda}>Elige una contraseña que no uses en otros sistemas.</p>
        )}

        {error && <div className={styles.error}><IconoAlerta tamano={15} /> {error}</div>}

        <label className={styles.campo}>
          <span>Contraseña actual</span>
          <input type="password" autoComplete="current-password" value={actual}
            onChange={(e) => setActual(e.target.value)} autoFocus />
        </label>
        <label className={styles.campo}>
          <span>Contraseña nueva</span>
          <input type="password" autoComplete="new-password" value={nueva}
            onChange={(e) => setNueva(e.target.value)} aria-invalid={!!problema} />
          <ul className={styles.requisitos} aria-label="Requisitos de la contraseña">
            {requisitos.map((r) => (
              <li key={r.texto} className={r.cumple ? styles.cumple : undefined}>{r.texto}</li>
            ))}
          </ul>
          {/* Lo que la lista no muestra: el nombre de usuario, palabras obvias o el largo máximo. */}
          {problema && !faltanRequisitos && <em className={styles.invalido}>{problema}</em>}
        </label>
        <label className={styles.campo}>
          <span>Repite la contraseña nueva</span>
          <input type="password" autoComplete="new-password" value={confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)} aria-invalid={noCoinciden} />
          {noCoinciden && <em className={styles.invalido}>No coincide con la contraseña nueva.</em>}
        </label>

        <div className={styles.acciones}>
          {obligatorio && (
            <button type="button" className={styles.btnTexto} onClick={salir}>Cerrar sesión</button>
          )}
          <button type="submit" className={styles.btnPrimario}
            disabled={guardando || !actual || !nueva || !!problema || nueva !== confirmacion}>
            {guardando ? "Guardando…" : "Guardar contraseña"}
          </button>
        </div>
      </form>
    </MarcoPagina>
  );
}
