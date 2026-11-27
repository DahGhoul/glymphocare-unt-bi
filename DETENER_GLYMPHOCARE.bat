@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Deteniendo procesos de GlymphoCare...
taskkill /FI "WINDOWTITLE eq GlymphoCare Backend (:8000)*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GlymphoCare Frontend (:5173)*" /T /F >nul 2>&1
docker compose stop db
echo GlymphoCare detenido.
pause
