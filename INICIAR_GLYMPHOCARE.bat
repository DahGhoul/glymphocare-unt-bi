@echo off
chcp 65001 >nul
title GlymphoCare - Iniciador Local
cd /d "%~dp0"

echo [1/4] Verificando base de datos PostgreSQL en Docker...
docker compose up -d db
if errorlevel 1 (
    echo [ERROR] Asegurate de tener Docker Desktop abierto.
    pause
    exit /b 1
)

echo [2/4] Iniciando Backend FastAPI en http://127.0.0.1:8000 ...
start "GlymphoCare Backend (:8000)" cmd /k "set PYTHONPATH=%~dp0&& cd /d ""%~dp0backend"" && ""%~dp0.venv\Scripts\python.exe"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [3/4] Iniciando Frontend React en http://localhost:5173 ...
start "GlymphoCare Frontend (:5173)" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo [4/4] Esperando 4 segundos y abriendo navegador...
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo GlymphoCare iniciado correctamente!
echo Credenciales demo (password: Glympho2026!):
echo   Admin:        admin@glymphocare.edu.pe
echo   Analista:     analista@glymphocare.edu.pe
echo   Investigador: investigador@glymphocare.edu.pe
echo   Participante: estudiante@glymphocare.edu.pe
echo.
pause
