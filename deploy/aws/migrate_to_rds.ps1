param(
    [Parameter(Mandatory=$true)][string]$RdsHost,
    [string]$RdsUser = "postgres",
    [Parameter(Mandatory=$true)][string]$RdsPassword,
    [string]$RdsDb = "glymphocare",
    [int]$RdsPort = 5432
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path "$PSScriptRoot\..\.."
$py = "$root\.venv\Scripts\python.exe"
$dsn = "postgresql://${RdsUser}:${RdsPassword}@${RdsHost}:${RdsPort}/${RdsDb}?sslmode=require"

Write-Host "[1/4] Verificando conexion a Amazon RDS ($RdsHost)..."
$env:DATABASE_URL = $dsn
& $py -c "import psycopg; conn = psycopg.connect('$dsn'); print('Conexion RDS exitosa:', conn.info.server_version); conn.close()"

Write-Host "[2/4] Aplicando esquemas OLTP, Data Mart y Reglas base..."
& $py -c "
import psycopg
from pathlib import Path
root = Path(r'$root')
with psycopg.connect('$dsn', autocommit=True) as conn:
    for f in ['database/01_oltp_schema.sql', 'database/02_datamart_star_schema.sql', 'database/03_seed_reglas_base.sql']:
        conn.execute((root / f).read_text(encoding='utf-8'))
        print('Aplicado:', f)
"

Write-Host "[3/4] Poblando cohorte UNT (90 estudiantes) y ejecutando ETL..."
& $py "$root\database\seed_cohorte.py"

Write-Host "[4/4] Actualizando .env local para apuntar a Amazon RDS..."
$envFile = "$root\.env"
$content = Get-Content $envFile | Where-Object { $_ -notmatch '^DATABASE_URL=' }
@("DATABASE_URL=$dsn") + $content | Set-Content $envFile -Encoding UTF8

Write-Host "Migracion a Amazon RDS completada! Ahora puedes iniciar GlymphoCare conectado 100% a AWS RDS."
