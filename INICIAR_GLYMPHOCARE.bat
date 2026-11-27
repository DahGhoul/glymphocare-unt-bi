@echo off
setlocal
chcp 65001 >nul
title GlymphoCare - Iniciador Local
cd /d "%~dp0"

:step_env
echo [1/6] Verificando configuracion .env y modo de base de datos...
if exist ".env" goto :detect_db_mode
if not exist ".env.example" goto :detect_db_mode
copy /y ".env.example" ".env" >nul
echo       Archivo .env creado desde .env.example - modo local Docker.

:detect_db_mode
set "USE_DOCKER_DB=1"
set "DB_MODE_LABEL=PostgreSQL local - Docker :5433"
if not exist ".env" goto :step_venv
findstr /b /c:"DATABASE_URL=" ".env" >nul 2>&1
if errorlevel 1 goto :step_venv
findstr /b /c:"DATABASE_URL=" ".env" | findstr /i "localhost 127.0.0.1" >nul 2>&1
if not errorlevel 1 goto :step_venv
set "USE_DOCKER_DB=0"
set "DB_MODE_LABEL=Base de datos remota - .env / Amazon RDS"

:step_venv
echo [2/6] Verificando entorno virtual Python .venv...
if exist ".venv\Scripts\python.exe" goto :step_db

set "PY_CMD="
python --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"
if defined PY_CMD goto :create_venv
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD goto :err_no_python

:create_venv
echo       Creando entorno virtual .venv e instalando dependencias...
%PY_CMD% -m venv .venv
if errorlevel 1 goto :err_venv_create
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :err_pip

:step_db
if "%USE_DOCKER_DB%"=="0" goto :db_cloud

:db_docker
echo [3/6] Iniciando PostgreSQL local en Docker...
docker compose up -d db
if errorlevel 1 goto :err_docker

set /a PG_TRY=0
:pg_wait
docker exec glymphocare_postgres pg_isready -U glympho -d glymphocare >nul 2>&1
if not errorlevel 1 goto :db_seed_check
set /a PG_TRY+=1
if %PG_TRY% geq 15 goto :err_pg_timeout
timeout /t 2 /nobreak >nul
goto :pg_wait

:db_seed_check
set "PYTHONPATH=%~dp0"
".venv\Scripts\python.exe" -c "import sys, psycopg; from etl.run_etl import get_dsn; dsn = get_dsn().replace('postgresql+psycopg://', 'postgresql://'); conn = psycopg.connect(dsn); c = conn.execute('SELECT COUNT(*) FROM glympho_oltp.participante').fetchone()[0]; conn.close(); sys.exit(0 if c >= 90 else 1)" >nul 2>&1
if not errorlevel 1 goto :step_frontend
echo       Primera ejecucion detectada: sembrando cohorte UNT y ejecutando ETL inicial...
".venv\Scripts\python.exe" database\seed_cohorte.py
if errorlevel 1 goto :err_seed
goto :step_frontend

:db_cloud
echo [3/6] Modo nube detectado - %DB_MODE_LABEL% - omitiendo Docker local.

:step_frontend
echo [4/6] Verificando dependencias Frontend React / Vite...
if exist "frontend\node_modules" goto :check_dry_run
call npm --version >nul 2>&1
if errorlevel 1 goto :err_no_npm
echo       Instalando paquetes npm en frontend...
pushd frontend
call npm install
if errorlevel 1 goto :err_npm_install
popd

:check_dry_run
if /i "%~1"=="--check" goto :check_ok

:step_launch
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
echo Credenciales demo - password: Glympho2026! :
echo   Admin:        admin@glymphocare.edu.pe
echo   Analista:     analista@glymphocare.edu.pe
echo   Investigador: investigador@glymphocare.edu.pe
echo   Participante: estudiante@glymphocare.edu.pe
echo.
pause
exit /b 0

:check_ok
echo CHECK_OK
exit /b 0

:err_no_python
echo [ERROR] No se encontro Python 3 en el sistema. Instalalo antes de continuar.
goto :error_exit

:err_venv_create
echo [ERROR] No se pudo crear el entorno virtual .venv.
goto :error_exit

:err_pip
echo [ERROR] Fallo la instalacion de backend\requirements.txt.
goto :error_exit

:err_docker
echo [ERROR] Asegurate de tener Docker Desktop abierto.
goto :error_exit

:err_pg_timeout
echo [ERROR] PostgreSQL en Docker no respondio a tiempo.
goto :error_exit

:err_seed
echo [ERROR] No se pudo sembrar la base de datos inicial.
goto :error_exit

:err_no_npm
echo [ERROR] No se encontro Node.js / npm en el sistema. Instalalo desde https://nodejs.org
goto :error_exit

:err_npm_install
popd
echo [ERROR] Fallo la instalacion de dependencias npm.
goto :error_exit

:error_exit
pause
exit /b 1
