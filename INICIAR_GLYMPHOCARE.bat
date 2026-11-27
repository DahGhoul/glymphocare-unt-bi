@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title GlymphoCare - Iniciador Local
cd /d "%~dp0"

echo [1/6] Verificando configuracion (.env) y modo de base de datos...
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo       Archivo .env creado desde .env.example ^(modo local Docker^).
    )
)

set "USE_DOCKER_DB=1"
set "DB_MODE_LABEL=PostgreSQL local (Docker :5433)"
if exist ".env" (
    findstr /b /c:"DATABASE_URL=" ".env" >nul 2>&1
    if not errorlevel 1 (
        findstr /b /c:"DATABASE_URL=" ".env" | findstr /i "localhost 127.0.0.1" >nul 2>&1
        if errorlevel 1 (
            set "USE_DOCKER_DB=0"
            set "DB_MODE_LABEL=Base de datos remota (.env / Amazon RDS)"
        )
    )
)

echo [2/6] Verificando entorno virtual Python (.venv)...
if not exist ".venv\Scripts\python.exe" (
    set "PY_CMD="
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py -3"
    )
    if "!PY_CMD!"=="" (
        echo [ERROR] No se encontro Python 3 en el sistema. Instalalo antes de continuar.
        pause
        exit /b 1
    )
    echo       Creando entorno virtual .venv e instalando dependencias...
    !PY_CMD! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual .venv.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de backend\requirements.txt.
        pause
        exit /b 1
    )
)

if "%USE_DOCKER_DB%"=="0" (
    echo [3/6] Modo nube detectado ^(%DB_MODE_LABEL%^) - omitiendo Docker local.
) else (
    echo [3/6] Iniciando PostgreSQL local en Docker...
    docker compose up -d db
    if errorlevel 1 (
        echo [ERROR] Asegurate de tener Docker Desktop abierto.
        pause
        exit /b 1
    )
    set "PG_READY=0"
    for /L %%i in (1,1,15) do (
        if "!PG_READY!"=="0" (
            docker exec glymphocare_postgres pg_isready -U glympho -d glymphocare >nul 2>&1
            if not errorlevel 1 (
                set "PG_READY=1"
            ) else (
                timeout /t 2 /nobreak >nul
            )
        )
    )
    if "!PG_READY!"=="0" (
        echo [ERROR] PostgreSQL en Docker no respondio a tiempo.
        pause
        exit /b 1
    )
    set "PYTHONPATH=%~dp0"
    ".venv\Scripts\python.exe" -c "import sys, psycopg; from etl.run_etl import get_dsn; dsn = get_dsn().replace('postgresql+psycopg://', 'postgresql://'); conn = psycopg.connect(dsn); c = conn.execute('SELECT COUNT(*) FROM glympho_oltp.participante').fetchone()[0]; conn.close(); sys.exit(0 if c >= 90 else 1)" >nul 2>&1
    if errorlevel 1 (
        echo       Primera ejecucion detectada: sembrando cohorte UNT y ejecutando ETL inicial...
        ".venv\Scripts\python.exe" database\seed_cohorte.py
        if errorlevel 1 (
            echo [ERROR] No se pudo sembrar la base de datos inicial.
            pause
            exit /b 1
        )
    )
)

echo [4/6] Verificando dependencias Frontend (React / Vite)...
if not exist "frontend\node_modules" (
    call npm --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se encontro Node.js / npm en el sistema.
        pause
        exit /b 1
    )
    echo       Instalando paquetes npm en frontend...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] Fallo la instalacion de dependencias npm.
        pause
        exit /b 1
    )
    popd
)

echo [5/6] Iniciando Backend FastAPI en http://127.0.0.1:8000 ...
start "GlymphoCare Backend (:8000)" cmd /k "set PYTHONPATH=%~dp0&& cd /d ""%~dp0backend"" && ""%~dp0.venv\Scripts\python.exe"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [5/6] Iniciando Frontend React en http://localhost:5173 ...
start "GlymphoCare Frontend (:5173)" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo [6/6] Esperando 4 segundos y abriendo navegador...
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo GlymphoCare iniciado correctamente!
echo Base de datos activa: %DB_MODE_LABEL%
echo Credenciales demo ^(password: Glympho2026!^):
echo   Admin:        admin@glymphocare.edu.pe
echo   Analista:     analista@glymphocare.edu.pe
echo   Investigador: investigador@glymphocare.edu.pe
echo   Participante: estudiante@glymphocare.edu.pe
echo.
pause
