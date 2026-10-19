import { useState } from "react";
import type * as React from "react";
import { useLocation, useNavigate, type Location } from "react-router-dom";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { RUTA_CAMBIAR_CONTRASENA } from "../../api/client";
import { mensajeDeError } from "../../utils/errores";
import { CabeceraInstitucional } from "../../components/CabeceraInstitucional";
import { IconoUsuario, IconoCandado, IconoAlerta } from "../../components/Iconos";
import { PieInstitucional } from "../../components/PieInstitucional";
import styles from "./PaginaLogin.module.css";

const CORREO_SOPORTE = "mesadeayuda@migracion.gob.pa";

/** Página a la que volver tras iniciar sesión: la que se pidió sin sesión
 *  (enlace de un correo, sesión vencida) o el panel. Solo rutas de esta app. */
function destinoTrasLogin(ubicacion: Location): string {
  const desde = (ubicacion.state as { desde?: unknown } | null)?.desde;
  const pedido = typeof desde === "string" ? desde : new URLSearchParams(ubicacion.search).get("siguiente");
  if (!pedido?.startsWith("/")) return "/dashboard";
  const url = new URL(pedido, window.location.origin);
  if (url.origin !== window.location.origin || url.pathname === "/login") return "/dashboard";
  return url.pathname + url.search;
}

/** Acceso a ARGO NAVIS: el logo con las coordenadas de la sede y, al lado, el formulario. */
export default function PaginaLogin() {
  const { iniciarSesion } = useAutenticacion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const [nombreUsuario,     setNombreUsuario]     = useState("");
  const [contrasena,        setContrasena]        = useState("");
  const [mostrarContrasena, setMostrarContrasena] = useState(false);
  const [cargando,          setCargando]          = useState(false);
  const [error,             setError]             = useState<string | null>(null);

  async function alEnviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      const usuario = await iniciarSesion(nombreUsuario.trim(), contrasena);
      navegar(usuario.debe_cambiar_password ? RUTA_CAMBIAR_CONTRASENA : destinoTrasLogin(ubicacion), { replace: true });
    } catch (err) {
      setError(mensajeDeError(err, "Credenciales incorrectas. Verifica tu usuario y contraseña."));
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className={styles.pagina}>
      <CabeceraInstitucional />

      <main className={styles.cuerpo}>
        <section className={styles.insignia}>
          <h1 className={styles.titulo}>
            <img src="/images/logo-argo-navis.webp" alt="ARGO NAVIS · Sistema Interno Marítimo - SNM" className={styles.logoGrande} />
          </h1>
          <div className={styles.coordenadas}>09° 01′ N · 079° 32′ O</div>
        </section>

        <section className={styles.acceso} aria-labelledby="titulo-acceso">
          <h2 id="titulo-acceso">Iniciar sesión</h2>
          <p className={styles.intro}>Ingresa con tu usuario de dominio o con la cuenta asignada a tu agencia naviera.</p>

          {error && (
            <div className={styles.error} role="alert">
              <IconoAlerta />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={alEnviar} noValidate>
            <label className={styles.etiqueta} htmlFor="nombreUsuario">Usuario</label>
            <div className={styles.campo}>
              <IconoUsuario tamano={16} />
              <input
                id="nombreUsuario"
                type="text"
                placeholder="Ej: jperez"
                value={nombreUsuario}
                onChange={(e) => setNombreUsuario(e.target.value)}
                autoComplete="username"
                spellCheck={false}
                required
                autoFocus
              />
            </div>

            <label className={styles.etiqueta} htmlFor="contrasena">Contraseña</label>
            <div className={styles.campo}>
              <IconoCandado />
              <input
                id="contrasena"
                type={mostrarContrasena ? "text" : "password"}
                placeholder="Tu contraseña"
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className={styles.ojo}
                onClick={() => setMostrarContrasena((v) => !v)}
                aria-label={mostrarContrasena ? "Ocultar contraseña" : "Mostrar contraseña"}
              >
                {mostrarContrasena ? "Ocultar" : "Mostrar"}
              </button>
            </div>

            <button type="submit" className={styles.ingresar} disabled={cargando || !nombreUsuario || !contrasena}>
              {cargando && <span className={styles.spinner} />}
              {cargando ? "Verificando…" : "Iniciar sesión"}
            </button>
          </form>

          <p className={styles.aviso}>
            <strong>Sistema de uso oficial.</strong> El acceso está restringido a personal autorizado del Servicio
            Nacional de Migración y a agencias navieras registradas. Toda actividad queda registrada en la bitácora
            del sistema.
          </p>
          <p className={styles.soporte}>
            ¿Problemas para acceder? Escribe a la Dirección de Tecnología e Innovación:{" "}
            <a href={`mailto:${CORREO_SOPORTE}?subject=${encodeURIComponent("ARGO NAVIS - Problema de acceso")}`}>
              {CORREO_SOPORTE}
            </a>
          </p>
        </section>
      </main>

      <PieInstitucional />
    </div>
  );
}
