import axios from "axios";

// Por defecto, la API en el mismo origen: en dev la sirve el proxy de Vite
// (/api → backend) y en producción nginx. VITE_API_URL solo hace falta si el
// backend vive en otro origen.
export const URL_BASE_API: string = import.meta.env.VITE_API_URL ?? "/api/v1";

// 30s para peticiones normales (GET/POST/PATCH/DELETE). Las subidas y
// descargas grandes definen su propio timeout via la opción `timeout` de cada
// llamada, así que esto solo afecta a los JSON.
const TIMEOUT_MS = 30_000;

/** Cabecera con la que el backend pide cambiar la contraseña antes de seguir. */
const CABECERA_CAMBIO_CONTRASENA = "x-cambio-contrasena";
export const RUTA_CAMBIAR_CONTRASENA = "/cambiar-contrasena";

export const clienteApi = axios.create({
  baseURL: URL_BASE_API,
  timeout: TIMEOUT_MS,
  headers: { "Content-Type": "application/json" },
});

clienteApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Vencimiento (ms desde epoch) del token guardado; null si no hay o no se puede leer. */
export function vencimientoDelToken(): number | null {
  const carga = localStorage.getItem("access_token")?.split(".")[1];
  if (!carga) return null;
  try {
    const { exp } = JSON.parse(atob(carga.replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: unknown };
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

clienteApi.interceptors.response.use(
  (respuesta) => respuesta,
  (error) => {
    const estado = error?.response?.status;
    // Cualquier 401 implica token inválido/revocado → forzar re-login y, al
    // entrar de nuevo, volver a la página donde estaba.
    if (estado === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      if (window.location.pathname !== "/login") {
        const siguiente = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?siguiente=${siguiente}`;
      }
    }
    // Cuenta local con cambio de contraseña pendiente: solo puede cambiarla.
    if (estado === 403 && error?.response?.headers?.[CABECERA_CAMBIO_CONTRASENA] === "requerido"
        && window.location.pathname !== RUTA_CAMBIAR_CONTRASENA) {
      window.location.href = RUTA_CAMBIAR_CONTRASENA;
    }
    return Promise.reject(error);
  }
);

/** Guarda un blob como archivo en el equipo del usuario. */
export function guardarComoArchivo(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
