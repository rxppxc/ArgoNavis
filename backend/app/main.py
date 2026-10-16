import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError
from app.core.config import obtener_configuracion
from app.core.rate_limit import limiter
from app.core.registro import configurar_registro
from app.core.security import CABECERA_CAMBIO_CONTRASENA
from app.api.v1 import auth, admin, tramites, solicitudes, verificacion, catalogos, bitacora
# Registrar todos los modelos en el registry del ORM (relaciones por nombre).
from app.domain.models import rol, tramite, catalogo, solicitud  # noqa: F401
from app.infrastructure.tareas import tarea_vencimientos

configurar_registro()
logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    """Ciclo de vida de la aplicación: deja corriendo en segundo plano la tarea
    que expira las solicitudes con plazos vencidos (ver infrastructure/tareas.py).
    El esquema de BD lo maneja Alembic (`alembic upgrade head`, corrido por el
    entrypoint del contenedor antes de levantar uvicorn).
    Al apagar (Ctrl+C / SIGTERM) cancela la tarea limpiamente."""
    tarea = asyncio.create_task(tarea_vencimientos())
    yield
    tarea.cancel()
    with suppress(asyncio.CancelledError):
        await tarea


aplicacion = FastAPI(
    title="ARGO NAVIS - SNM API",
    version="3.0.0",
    description="Autorizaciones Marítimas (UCVMM) — Servicio Nacional de Migración",
    docs_url="/api/docs" if configuracion.APP_ENV == "development" else None,
    redoc_url="/api/redoc" if configuracion.APP_ENV == "development" else None,
    lifespan=ciclo_vida,
)

# Rate limiting (protección contra abuso de los endpoints públicos)
aplicacion.state.limiter = limiter


@aplicacion.exception_handler(RateLimitExceeded)
async def demasiadas_solicitudes(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 con `detail`, como el resto de los errores (el frontend lo muestra tal cual)."""
    logger.warning("[rate limit] %s %s superó %s", request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados intentos en poco tiempo. Espera unos minutos e intenta de nuevo."},
    )


@aplicacion.exception_handler(IntegrityError)
async def conflicto_de_integridad(request: Request, exc: IntegrityError) -> JSONResponse:
    """Una regla de la BD (llave foránea, valor único) rechazó el cambio: 409
    en vez de 500. Los servicios deberían validarlo antes; si llega aquí, el
    log dice qué restricción fue, para agregar esa validación."""
    restriccion = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
    logger.warning("[bd] La restricción %s rechazó %s %s", restriccion or "?", request.method, request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "No se pudo completar: hay registros relacionados que lo impiden."},
    )

# CORS: en desarrollo permite el frontend de Vite (no usamos "*" para poder enviar credenciales).
# En producción el frontend viene del mismo servidor → solo el FRONTEND_URL configurado.
_cors_origins = list({
    origen for origen in (configuracion.FRONTEND_URL, configuracion.APP_URL) if origen
})
aplicacion.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition", CABECERA_CAMBIO_CONTRASENA],
)

aplicacion.include_router(auth.enrutador,         prefix="/api/v1")
aplicacion.include_router(admin.enrutador,        prefix="/api/v1")
aplicacion.include_router(tramites.enrutador,     prefix="/api/v1")
aplicacion.include_router(solicitudes.enrutador,  prefix="/api/v1")
aplicacion.include_router(verificacion.enrutador, prefix="/api/v1")
aplicacion.include_router(catalogos.enrutador,    prefix="/api/v1")
aplicacion.include_router(bitacora.enrutador,     prefix="/api/v1")


@aplicacion.get("/api/health")
async def verificar_salud():
    return {"estado": "ok", "aplicacion": configuracion.APP_NAME}


# ── Servir el frontend compilado (npm run build) ──────────────────────────────
# Solo activo cuando existe la carpeta dist/. En dev se usa Vite directamente.
if _FRONTEND_DIST.exists():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        aplicacion.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    _RAIZ_DIST = _FRONTEND_DIST.resolve()
    # Las mismas cabeceras que pone nginx en Docker (ver frontend/nginx.conf),
    # para cuando el backend sirve el frontend directamente (start-backend-prod.bat).
    _CABECERAS_SPA = {
        # Solo corre código propio de ARGO NAVIS: sin scripts en línea, sin eval y sin
        # recursos de otros sitios (barrera ante un XSS: el token vive en localStorage).
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
            "frame-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        ),
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    @aplicacion.get("/{ruta_completa:path}", include_in_schema=False)
    async def servir_spa(ruta_completa: str):
        # Una ruta de la API que no existe es un 404, no la página del SPA.
        if ruta_completa == "api" or ruta_completa.startswith("api/"):
            raise HTTPException(status_code=404, detail="Recurso no encontrado.")
        # Defensa contra path traversal: resolver la ruta y verificar que el
        # resultado siga estando dentro de _FRONTEND_DIST. Si está fuera o si
        # no existe el archivo, se devuelve el index.html del SPA.
        if ruta_completa:
            try:
                archivo = (_FRONTEND_DIST / ruta_completa).resolve()
                archivo.relative_to(_RAIZ_DIST)
                if archivo.is_file():
                    return FileResponse(str(archivo), headers=_CABECERAS_SPA)
            except (ValueError, OSError):
                pass
        indice = _FRONTEND_DIST / "index.html"
        if indice.exists():
            # Sin hash en el nombre: que el navegador revalide para no quedarse
            # con un index.html que apunta al bundle de una versión anterior.
            return FileResponse(str(indice), headers={**_CABECERAS_SPA, "Cache-Control": "no-cache"})
        raise HTTPException(status_code=404, detail="Frontend no compilado.")
