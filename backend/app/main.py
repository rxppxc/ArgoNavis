import asyncio
import logging
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, and_
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.core.config import obtener_configuracion
from app.core.rate_limit import limiter
from app.infrastructure.database import SesionLocal
from app.api.v1 import auth, transfers, admin
from app.domain.models import puerto as _puerto_model    # noqa: registrar en ORM registry
from app.domain.models import rol as _rol_model          # noqa: registrar en ORM registry
from app.domain.models.transfer import Transferencia

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


async def _purgar_expiradas() -> int:
    """Elimina del disco y la BD las transferencias cuya expiración venció hace
    más de LIMPIEZA_RETENER_DIAS días. Devuelve el número de transferencias
    purgadas.

    Se purga por `expires_at` sin filtrar por estado: así también se limpian los
    borradores, devueltos, en revisión y procesados que quedaron abandonados —
    de lo contrario sus archivos se acumulaban en disco para siempre. Las filas
    con `expires_at` NULL quedan fuera (la comparación con NULL no coincide)."""
    ahora    = datetime.now(timezone.utc)
    limite   = ahora - timedelta(days=configuracion.LIMPIEZA_RETENER_DIAS)
    purgadas = 0
    try:
        async with SesionLocal() as sesion:
            resultado = await sesion.execute(
                select(Transferencia).where(
                    and_(
                        Transferencia.expires_at.isnot(None),
                        Transferencia.expires_at < limite,
                    )
                )
            )
            expiradas = list(resultado.scalars().all())
            for t in expiradas:
                carpeta_archivos = Path(configuracion.STORAGE_PATH) / t.token
                if carpeta_archivos.exists():
                    shutil.rmtree(carpeta_archivos, ignore_errors=True)
                ruta_zip = Path(configuracion.STORAGE_PATH) / f"{t.token}.zip"
                if ruta_zip.exists():
                    ruta_zip.unlink(missing_ok=True)
                await sesion.delete(t)
                purgadas += 1
            if purgadas:
                await sesion.commit()
    except Exception as exc:
        logger.error(f"[limpieza] Error durante la purga: {exc}")
    return purgadas


async def _tarea_limpieza():
    """Purga transferencias expiradas al arrancar y luego cada LIMPIEZA_INTERVALO_HORAS horas."""
    intervalo = configuracion.LIMPIEZA_INTERVALO_HORAS * 3600
    while True:
        n = await _purgar_expiradas()
        if n:
            logger.info(f"[limpieza] {n} transferencia(s) expirada(s) purgada(s) del disco y BD.")
        else:
            logger.debug("[limpieza] Sin transferencias expiradas que purgar.")
        await asyncio.sleep(intervalo)


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    """Ciclo de vida de la aplicación: deja corriendo en segundo plano la tarea
    de purga de transferencias expiradas. El esquema de BD lo maneja Alembic
    (`alembic upgrade head`, corrido por el entrypoint del contenedor antes de
    levantar uvicorn) — ya no hay migraciones ad-hoc en el arranque de la app.
    Al apagar (Ctrl+C / SIGTERM) cancela la tarea limpiamente."""
    tarea = asyncio.create_task(_tarea_limpieza())
    yield
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass


aplicacion = FastAPI(
    title="FileDrop - SNM API",
    version="2.0.0",
    description="Sistema de transferencia de archivos — Servicio Nacional de Migración",
    docs_url="/api/docs" if configuracion.APP_ENV == "development" else None,
    redoc_url="/api/redoc" if configuracion.APP_ENV == "development" else None,
    lifespan=ciclo_vida,
)

# Rate limiting (protección contra DDoS en endpoints públicos)
aplicacion.state.limiter = limiter
aplicacion.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
)

aplicacion.include_router(auth.enrutador,      prefix="/api/v1")
aplicacion.include_router(transfers.enrutador, prefix="/api/v1")
aplicacion.include_router(admin.enrutador,     prefix="/api/v1")


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

    @aplicacion.get("/{ruta_completa:path}", include_in_schema=False)
    async def servir_spa(ruta_completa: str):
        # Defensa contra path traversal: resolver la ruta y verificar que el
        # resultado siga estando dentro de _FRONTEND_DIST. Si está fuera o si
        # no existe el archivo, se devuelve el index.html del SPA.
        if ruta_completa:
            try:
                archivo = (_FRONTEND_DIST / ruta_completa).resolve()
                archivo.relative_to(_RAIZ_DIST)
                if archivo.is_file():
                    return FileResponse(str(archivo))
            except (ValueError, OSError):
                pass
        indice = _FRONTEND_DIST / "index.html"
        if indice.exists():
            return FileResponse(str(indice))
        raise HTTPException(status_code=404, detail="Frontend no compilado.")
