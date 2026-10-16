/**
 * Captura errores no manejados del árbol de React y muestra una pantalla
 * de respaldo en vez de dejar la app en blanco. Equivalente al patrón
 * "Error Boundary" de React (clase obligatoria, no hay versión con hooks).
 */
import { Component, type ReactNode } from "react";

interface Props  { children: ReactNode; }
interface Estado { hayError: boolean; mensaje: string; }

export class CapturadorErrores extends Component<Props, Estado> {
  state: Estado = { hayError: false, mensaje: "" };

  static getDerivedStateFromError(error: Error): Estado {
    return { hayError: true, mensaje: error.message };
  }

  componentDidCatch(error: Error) {
    console.error("[ARGO NAVIS] Error no capturado:", error);
  }

  render() {
    if (this.state.hayError) {
      // Usa los tokens del tema: data-theme ya está puesto por public/tema-inicial.js
      // aunque el error haya ocurrido antes de montar ProveedorTema.
      return (
        <div style={{
          minHeight: "100vh", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          background: "var(--bg)", color: "var(--text)", fontFamily: "Segoe UI, sans-serif",
          padding: "40px 20px", textAlign: "center",
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h2 style={{ fontSize: "1.4rem", marginBottom: 8 }}>Algo salió mal</h2>
          <p style={{ color: "var(--text-2)", marginBottom: 24, maxWidth: 400 }}>
            Ocurrió un error inesperado en la aplicación. Por favor recarga la página.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: "var(--y)", color: "var(--on-accent)", border: "none",
              borderRadius: 8, padding: "12px 28px", fontWeight: 700,
              fontSize: "0.95rem", cursor: "pointer",
            }}
          >
            Recargar página
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
