import { useState, useEffect } from "react";
import type * as React from "react";
import { useNavigate } from "react-router-dom";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { IconoUsuario, IconoCandado, IconoOjo, IconoOjoCerrado, IconoAlerta } from "../../components/Iconos";
import styles from "./PaginaLogin.module.css";

const FONDOS = [
  '/images/bg-migracion.jpg',
  '/images/login-bg-2.jpg',
  '/images/login-bg-3.jpg',
  '/images/login-bg-4.jpg',
  '/images/login-bg-5.jpg',
  '/images/login-bg-6.jpg',
  '/images/login-bg-7.png',
];

const CARACTERISTICAS = [
  "Autenticación con el dominio",
  "Transferencias cifradas",
  "Enlace único por transferencia",
  "Expiración automática",
];

export default function PaginaLogin() {
  const { iniciarSesion } = useAutenticacion();
  const navegar = useNavigate();
  const [nombreUsuario,     setNombreUsuario]     = useState("");
  const [contrasena,        setContrasena]        = useState("");
  const [mostrarContrasena, setMostrarContrasena] = useState(false);
  const [cargando,          setCargando]          = useState(false);
  const [error,             setError]             = useState<string | null>(null);
  const [fondoActual,       setFondoActual]       = useState(0);

  useEffect(() => {
    const t = setInterval(() => {
      setFondoActual(i => (i + 1) % FONDOS.length);
    }, 4000);
    return () => clearInterval(t);
  }, []);

  async function alEnviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      await iniciarSesion(nombreUsuario.trim(), contrasena);
      navegar("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Credenciales incorrectas. Verifica tu usuario y contraseña.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className={styles.page}>

      {/* Panel de acceso */}
      <div className={styles.panelForm}>
        <div className={styles.brand}>
          <img src="/images/logo-snm.png" alt="SNM" className={styles.brandLogo} />
          <div className={styles.brandText}>
            <div className={styles.org}>Servicio Nacional de Migración</div>
            <div className={styles.app}>FileDrop - SNM</div>
          </div>
        </div>

        <div className={styles.formWrap}>
          <h1 className={styles.titulo}>Bienvenido</h1>
          <p className={styles.subtitulo}>Ingresa con tus credenciales de dominio</p>

          {error && (
            <div className={styles.error}>
              <IconoAlerta />
              {error}
            </div>
          )}

          <form onSubmit={alEnviar} noValidate>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="nombreUsuario">Nombre de Usuario</label>
              <div className={styles.inputLine}>
                <span className={styles.inputIcon}><IconoUsuario tamano={17} /></span>
                <input
                  id="nombreUsuario"
                  className={styles.input}
                  type="text"
                  placeholder="Ej: vperez"
                  value={nombreUsuario}
                  onChange={(e) => setNombreUsuario(e.target.value)}
                  autoComplete="username"
                  required
                  autoFocus
                />
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="contrasena">Clave de Acceso</label>
              <div className={styles.inputLine}>
                <span className={styles.inputIcon}><IconoCandado /></span>
                <input
                  id="contrasena"
                  className={styles.input}
                  type={mostrarContrasena ? "text" : "password"}
                  placeholder="••••••••"
                  value={contrasena}
                  onChange={(e) => setContrasena(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setMostrarContrasena((v) => !v)}
                  aria-label="Mostrar contraseña"
                >
                  {mostrarContrasena ? <IconoOjoCerrado /> : <IconoOjo tamano={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className={styles.submitBtn}
              disabled={cargando || !nombreUsuario || !contrasena}
            >
              {cargando && <span className={styles.spinner} />}
              {cargando ? "Verificando…" : "Conectar"}
            </button>
          </form>

          <p className={styles.hint}>¿Tienes Problemas para acceder? Contacta a la Dirección de Tecnología e Innovación.</p>
        </div>

        <div className={styles.formFooter}>
          Servicio Nacional de Migración &copy; {new Date().getFullYear()} &mdash; Todos los derechos reservados
        </div>
      </div>

      {/* Panel visual */}
      <div className={styles.panelVisual}>
        <div className={styles.slideshowBg}>
          {FONDOS.map((src, i) => (
            <div
              key={src}
              className={`${styles.bgSlide} ${i === fondoActual ? styles.bgSlideActive : ""}`}
              style={{ backgroundImage: `url(${src})` }}
            />
          ))}
          <div className={styles.bgOverlay} />
        </div>

        <div className={styles.visualContent}>
          <img src="/images/logo-snm.png" alt="SNM" className={styles.visualLogo} />
          <h2 className={styles.visualTitulo}>FileDrop - SNM</h2>
          <p className={styles.visualSubtitulo}>Repositorio de Transferencia Documental</p>

          <div className={styles.feats}>
            {CARACTERISTICAS.map((c) => (
              <div key={c} className={styles.feat}>
                <span className={styles.featDot} />
                {c}
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
