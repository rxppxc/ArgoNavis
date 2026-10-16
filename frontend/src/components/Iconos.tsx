/**
 * Catálogo único de iconos SVG.
 *
 * Antes vivían inline (104 definiciones duplicadas en 12 archivos). Ahora cada
 * icono se define una sola vez y acepta un prop opcional `tamano` para casos
 * donde el contexto requiere un tamaño distinto al por defecto.
 *
 * Convención: nombres `Icono<NombreEnEspañol>`. El SVG usa stroke="currentColor"
 * para que el color se controle desde CSS via `color:`.
 */
import type { ReactNode, CSSProperties } from "react";

interface PropsIcono {
  tamano?: number;
  className?: string;
  style?: CSSProperties;
}

interface FabricaProps {
  ancho: number;
  alto: number;
  strokeWidth?: number;
  fill?: string;
  children: ReactNode;
}

function crearIcono({ ancho, alto, strokeWidth = 2, fill = "none", children }: FabricaProps) {
  return function Icono({ tamano, className, style }: PropsIcono = {}) {
    return (
      <svg
        width={tamano ?? ancho}
        height={tamano ?? alto}
        viewBox="0 0 24 24"
        fill={fill}
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={style}
      >
        {children}
      </svg>
    );
  };
}

// ── Usuarios y permisos ──────────────────────────────────────────────────────
export const IconoUsuario = crearIcono({
  ancho: 18, alto: 18,
  children: (
    <>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </>
  ),
});

export const IconoUsuarios = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
});

export const IconoCandado = crearIcono({
  ancho: 17, alto: 17,
  children: (
    <>
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </>
  ),
});

export const IconoEscudo = crearIcono({
  ancho: 16, alto: 16,
  children: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
});

export const IconoLlave = crearIcono({
  ancho: 16, alto: 16,
  children: <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4" />,
});

// ── Acciones básicas ─────────────────────────────────────────────────────────
export const IconoMas = crearIcono({
  ancho: 14, alto: 14, strokeWidth: 2.5,
  children: (
    <>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </>
  ),
});

export const IconoBasura = crearIcono({
  ancho: 13, alto: 13,
  children: (
    <>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
    </>
  ),
});

export const IconoEditar = crearIcono({
  ancho: 14, alto: 14,
  children: (
    <>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </>
  ),
});

export const IconoCheck = crearIcono({
  ancho: 14, alto: 14, strokeWidth: 2.5,
  children: <polyline points="20 6 9 17 4 12" />,
});

export const IconoX = crearIcono({
  ancho: 14, alto: 14, strokeWidth: 2.5,
  children: (
    <>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </>
  ),
});

export const IconoBuscar = crearIcono({
  ancho: 16, alto: 16,
  children: (
    <>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </>
  ),
});

// ── Archivos y carpetas ──────────────────────────────────────────────────────
export const IconoArchivo = crearIcono({
  ancho: 14, alto: 14,
  children: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </>
  ),
});

// ── Descarga ─────────────────────────────────────────────────────────────────
export const IconoDescargar = crearIcono({
  ancho: 18, alto: 18,
  children: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </>
  ),
});

// ── Métricas y estado ────────────────────────────────────────────────────────
export const IconoGrafico = crearIcono({
  ancho: 18, alto: 18,
  children: (
    <>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </>
  ),
});

export const IconoEstadisticas = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </>
  ),
});

export const IconoActividad = crearIcono({
  ancho: 18, alto: 18,
  children: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />,
});

export const IconoReloj = crearIcono({
  ancho: 13, alto: 13,
  children: (
    <>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </>
  ),
});

export const IconoAlerta = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </>
  ),
});

export const IconoXCirculo = crearIcono({
  ancho: 32, alto: 32, strokeWidth: 1.5,
  children: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </>
  ),
});

export const IconoExito = crearIcono({
  ancho: 16, alto: 16, strokeWidth: 2.5,
  children: <polyline points="20 6 9 17 4 12" />,
});

// Icono de check dentro de círculo relleno — para estado "procesada" (final)
export const IconoProcesada = crearIcono({
  ancho: 16, alto: 16, fill: "currentColor", strokeWidth: 0,
  children: (
    <>
      <circle cx="12" cy="12" r="10" />
      <polyline
        points="8.5 12.5 11 15 16 9.5"
        fill="none"
        stroke="#ffffff"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  ),
});

export const IconoTrofeo = crearIcono({
  ancho: 18, alto: 18,
  children: (
    <>
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2z" />
    </>
  ),
});

// ── Visibilidad ──────────────────────────────────────────────────────────────
export const IconoOjo = crearIcono({
  ancho: 13, alto: 13,
  children: (
    <>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
});

// ── Dominio (puertos, naves) ─────────────────────────────────────────────────
export const IconoAncla = crearIcono({
  ancho: 16, alto: 16,
  children: (
    <>
      <circle cx="12" cy="5" r="3" />
      <line x1="12" y1="22" x2="12" y2="8" />
      <path d="M5 12H2a10 10 0 0 0 20 0h-3" />
    </>
  ),
});

export const IconoBarco = crearIcono({
  ancho: 14, alto: 14,
  children: (
    <>
      <path d="M2 20a2.4 2.4 0 0 0 2 1 2.4 2.4 0 0 0 2-1 2.4 2.4 0 0 1 2-1 2.4 2.4 0 0 1 2 1 2.4 2.4 0 0 0 2 1 2.4 2.4 0 0 0 2-1 2.4 2.4 0 0 1 2-1 2.4 2.4 0 0 1 2 1" />
      <path d="M4 18l-1-5h18l-2 5" />
      <path d="M12 3v8" />
      <path d="M8 11V7l4-4 4 4v4" />
    </>
  ),
});

// Icono de grúa portuaria — representa el muelle donde el operador procesa
export const IconoBandeja = crearIcono({
  ancho: 18, alto: 18,
  children: (
    <>
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </>
  ),
});

export const IconoDisco = crearIcono({
  ancho: 22, alto: 22, strokeWidth: 1.8,
  children: (
    <>
      <line x1="22" y1="12" x2="2" y2="12" />
      <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
      <line x1="6" y1="16" x2="6.01" y2="16" />
      <line x1="10" y1="16" x2="10.01" y2="16" />
    </>
  ),
});

// ── Navegación ───────────────────────────────────────────────────────────────
export const IconoAtras = crearIcono({
  ancho: 14, alto: 14, strokeWidth: 2.5,
  children: <polyline points="15 18 9 12 15 6" />,
});

export const IconoChevronAbajo = crearIcono({
  ancho: 13, alto: 13, strokeWidth: 2.5,
  children: <polyline points="6 9 12 15 18 9" />,
});

export const IconoChevronDerecha = crearIcono({
  ancho: 14, alto: 14, strokeWidth: 2.5,
  children: <polyline points="9 18 15 12 9 6" />,
});

// ── Identidad / comunicación ─────────────────────────────────────────────────
export const IconoCorreo = crearIcono({
  ancho: 13, alto: 13,
  children: (
    <>
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </>
  ),
});

export const IconoMaletin = crearIcono({
  ancho: 13, alto: 13,
  children: (
    <>
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    </>
  ),
});

export const IconoSalir = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </>
  ),
});

export const IconoPoder = crearIcono({
  ancho: 14, alto: 14,
  children: (
    <>
      <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />
      <line x1="12" y1="2" x2="12" y2="12" />
    </>
  ),
});

// ── Tema (claro/oscuro) ──────────────────────────────────────────────────────
export const IconoSol = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </>
  ),
});

export const IconoLuna = crearIcono({
  ancho: 14, alto: 14,
  children: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />,
});

/** "Sistema": el tema sigue al del sistema operativo. */
export const IconoMonitor = crearIcono({
  ancho: 15, alto: 15,
  children: (
    <>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </>
  ),
});
