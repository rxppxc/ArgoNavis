import { useState } from "react";
import type * as React from "react";
import { useLocation, useNavigate, type Location } from "react-router-dom";
import { useAutenticacion } from "../../hooks/useAutenticacion";
import { useTituloDocumento } from "../../hooks/useTituloDocumento";
import { RUTA_CAMBIAR_CONTRASENA } from "../../api/client";
import { mensajeDeError } from "../../utils/errores";
import { CabeceraInstitucional } from "../../components/CabeceraInstitucional";
import { FondoPagina } from "../../components/FondoPagina";
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
  useTituloDocumento("Iniciar sesión");

  async function alEnviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!nombreUsuario.trim() || !contrasena) {
      setError("Escribe tu usuario y tu contraseña.");
      return;
    }
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
      <a href="#contenido" className="saltar-contenido">Saltar al contenido</a>
      <CabeceraInstitucional />

      <div className={styles.medio}>
      <FondoPagina coordenadas={false} animado />
      <main id="contenido" tabIndex={-1} className={styles.cuerpo}>
        {/* Un pasaporte abierto sobre la carta (identidad «pase oficial», 2026-11-11):
            la tapa con el emblema de ARGO NAVIS y, en la hoja, el acceso. */}
        <div className={styles.libreta}>
        <section className={styles.tapa}>
          <p className={styles.pais}>República de Panamá</p>
          <h1 className={styles.titulo}>
            <img src="/images/logo-argo-navis.webp" alt="ARGO NAVIS · Sistema Interno Marítimo - SNM" className={styles.logoGrande} />
          </h1>
          <p className={styles.coordenadas}>09° 01′ N · 079° 32′ O</p>
          <span className={styles.chip} aria-hidden="true" />
          <p className={styles.mrz} aria-hidden="true">P&lt;PANARGO&lt;NAVIS&lt;&lt;SERVICIO&lt;NACIONAL&lt;DE&lt;MIGRACION&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;</p>
        </section>

        <section className={styles.acceso} aria-labelledby="titulo-acceso">
          <p className={styles.antetitulo}>Acceso al sistema</p>
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
                placeholder="Ej. jperez"
                value={nombreUsuario}
                onChange={(e) => setNombreUsuario(e.target.value)}
                autoComplete="username"
                spellCheck={false}
                maxLength={100}
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
                maxLength={256}
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

            <button type="submit" className={styles.ingresar} disabled={cargando}>
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
        </div>
      </main>
      </div>

      <PieInstitucional />
    </div>
  );
}
