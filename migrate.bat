@echo off
echo === ARGO NAVIS - Migraciones de base de datos ===
REM ════════════════════════════════════════════════════════════════════════════
REM Alembic es la única fuente de verdad del esquema (versions/). No hay
REM migraciones runtime aparte — todo el esquema (usuarios, roles, solicitudes,
REM catálogos, bitácora) vive en backend/alembic/versions/. Este script solo
REM corre `alembic upgrade head`.
REM
REM Para un cambio estructural nuevo: crear la revisión a mano (o con
REM `alembic revision --autogenerate` si el modelo ya cambió) y revisarla
REM antes de aplicarla.
REM ════════════════════════════════════════════════════════════════════════════
cd /d %~dp0backend
REM -I: que la carpeta alembic\ (las migraciones) no tape al paquete alembic; y sin
REM alembic.exe, que guarda la ruta del venv y se rompe si se mueve la carpeta.
venv\Scripts\python -I -m alembic upgrade head
if errorlevel 1 goto fin
REM Con MIGRACIONES_DATABASE_URL en el .env: crea o pone al día la cuenta de la
REM aplicación (DATABASE_URL), con lo justo. Sin ella, no hace nada.
venv\Scripts\python -m app.infrastructure.permisos_bd
:fin
echo === Listo ===
pause
