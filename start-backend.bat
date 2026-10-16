@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM ARGO NAVIS (SNM) — Arranque DESARROLLO (con --reload y 1 worker)
REM Para producción usar: start-backend-prod.bat
REM ════════════════════════════════════════════════════════════════════════════
cd /d %~dp0backend
REM python -m (no uvicorn.exe ni activate): sigue andando aunque se mueva o renombre la carpeta.
venv\Scripts\python -m uvicorn app.main:aplicacion --host 127.0.0.1 --port 8000 --reload
pause
