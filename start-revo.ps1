# ============================================================
# REVO — Arranque local completo
# ============================================================
# Uso:  .\start-revo.ps1
#
# Hace todo lo necesario, en orden, y verifica cada paso:
#   1. Levanta PostgreSQL en Docker (puerto 5434)
#   2. Crea los venv de Python e instala dependencias si faltan
#   3. Genera los .env con un JWT_SECRET compartido si faltan
#   4. Arranca los 3 microservicios (8011 / 8012 / 8013)
#   5. Arranca el frontend Vite (5173)
#
# Se puede volver a ejecutar sin problema: los pasos ya
# completados se saltan.
# ============================================================

# "Continue" a proposito: con "Stop", cualquier linea que docker o npm
# escriban en stderr (incluidos avisos inofensivos) se convierte en un
# error fatal en PowerShell 5.1 y aborta el arranque. Los fallos reales
# se detectan comprobando $LASTEXITCODE y los puertos.
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot

$services = @(
    @{ Name = "auth";   Dir = "auth-service";   Port = 8011 },
    @{ Name = "survey"; Dir = "survey-service"; Port = 8012 },
    @{ Name = "ml";     Dir = "ml-service";     Port = 8013 }
)

function Write-Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)       { Write-Host "      OK  $msg" -ForegroundColor Green }
function Write-Info($msg)     { Write-Host "      ..  $msg" -ForegroundColor DarkGray }
function Write-Warn($msg)     { Write-Host "      !   $msg" -ForegroundColor Yellow }

function Test-Port($port) {
    $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  REVO — arranque local" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# ── 1. Base de datos ────────────────────────────────────────
Write-Step "1/5" "PostgreSQL (Docker, puerto 5434)"

docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Docker Desktop no responde. Abrelo y vuelve a ejecutar." -ForegroundColor Red
    exit 1
}

docker compose up -d postgres | Out-Null

# Esperar a que el healthcheck pase antes de arrancar los servicios
$ready = $false
foreach ($i in 1..30) {
    $state = (docker inspect -f '{{.State.Health.Status}}' revo_postgres 2>$null)
    if ($state -eq "healthy") { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "      PostgreSQL no llego a estado healthy." -ForegroundColor Red
    exit 1
}
Write-Ok "PostgreSQL listo"

# ── 2. Entornos Python ──────────────────────────────────────
Write-Step "2/5" "Entornos virtuales y dependencias"

foreach ($svc in $services) {
    $dir = Join-Path $root "services\$($svc.Dir)"
    $py  = Join-Path $dir "venv\Scripts\python.exe"

    if (-not (Test-Path $py)) {
        Write-Info "creando venv de $($svc.Name) (tarda un par de minutos)"
        python -m venv (Join-Path $dir "venv")
        & $py -m pip install --quiet --disable-pip-version-check -r (Join-Path $dir "requirements.txt")
        Write-Ok "$($svc.Name): venv creado"
    } else {
        Write-Ok "$($svc.Name): venv ya existe"
    }
}

# ── 3. Variables de entorno ─────────────────────────────────
Write-Step "3/5" "Archivos .env"

# Los 3 servicios DEBEN compartir el mismo JWT_SECRET: cada uno
# valida los tokens que emiten los otros. Los config.py ya no
# traen valor por defecto a proposito (un secreto en el repo
# permite falsificar tokens de admin).
$dbUrl = "postgresql://revo_user:revo_pass_2025@localhost:5434/revo_db"
$envAuth = Join-Path $root "services\auth-service\.env"

if (Test-Path $envAuth) {
    $secret = (Select-String -Path $envAuth -Pattern '^JWT_SECRET=(.+)$').Matches.Groups[1].Value
    Write-Ok "reutilizando el JWT_SECRET existente"
} else {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
    Write-Ok "JWT_SECRET nuevo generado"
}

$envFiles = @{
    "auth-service"   = "DATABASE_URL=$dbUrl`nJWT_SECRET=$secret`nJWT_ALGORITHM=HS256`nJWT_EXPIRE_HOURS=24`nSERVICE_PORT=8011`n"
    "survey-service" = "DATABASE_URL=$dbUrl`nJWT_SECRET=$secret`nJWT_ALGORITHM=HS256`nSERVICE_PORT=8012`nML_SERVICE_URL=http://localhost:8013`n"
    "ml-service"     = "DATABASE_URL=$dbUrl`nJWT_SECRET=$secret`nJWT_ALGORITHM=HS256`nSERVICE_PORT=8013`nMODEL_PATH=model/saved/decision_tree.pkl`nMODEL_VERSION=v1.0`n"
}
foreach ($dir in $envFiles.Keys) {
    $path = Join-Path $root "services\$dir\.env"
    if (-not (Test-Path $path)) {
        [System.IO.File]::WriteAllText($path, $envFiles[$dir])
        Write-Ok "$dir/.env creado"
    }
}

# ── 4. Microservicios ───────────────────────────────────────
Write-Step "4/5" "Microservicios"

foreach ($svc in $services) {
    if (Test-Port $svc.Port) {
        Write-Warn "$($svc.Name): el puerto $($svc.Port) ya esta ocupado, se omite"
        continue
    }
    $dir = Join-Path $root "services\$($svc.Dir)"
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$dir'; .\venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port $($svc.Port) --reload"
    ) -WindowStyle Minimized
    Write-Info "$($svc.Name) arrancando en $($svc.Port)"
}

# Esperar a que los 3 respondan de verdad, en vez de dormir a ciegas
foreach ($svc in $services) {
    $up = $false
    foreach ($i in 1..40) {
        try {
            $r = Invoke-WebRequest "http://127.0.0.1:$($svc.Port)/docs" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $up = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($up) { Write-Ok "$($svc.Name) responde en $($svc.Port)" }
    else     { Write-Warn "$($svc.Name) no respondio; revisa su ventana" }
}

# ── 5. Frontend ─────────────────────────────────────────────
Write-Step "5/5" "Frontend"

$frontDir = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontDir "node_modules"))) {
    Write-Info "instalando dependencias de npm"
    Push-Location $frontDir; npm install; Pop-Location
}

# El proxy de vite.config.js apunta a 8011/8012/8013, asi que el
# frontend debe correr en 5173. Si esta ocupado, Vite salta a 5174
# y el aviso de abajo evita que busques la pestana equivocada.
if ((Test-Port 5173) -and (Test-Port 5174)) {
    Write-Warn "ya hay un frontend corriendo, se omite"
} else {
    if (Test-Port 5173) { Write-Warn "el puerto 5173 esta ocupado: Vite usara 5174" }
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$frontDir'; npm run dev"
    ) -WindowStyle Minimized
}

# Vite elige 5174 si 5173 esta ocupado, y tarda unos segundos en
# enlazarse. Hay que sondear en vez de mirar una sola vez, o se
# anuncia el puerto equivocado.
# Se identifica por el proxy /api/auth de vite.config.js: si hay otro
# proyecto Vite en 5173, tambien responde 200 en la raiz y con el mismo
# <title>, asi que mirar la portada no sirve para distinguirlos.
$frontUrl = $null
foreach ($i in 1..20) {
    foreach ($p in 5173, 5174, 5175) {
        try {
            $r = Invoke-WebRequest "http://localhost:$p/api/auth/docs" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $frontUrl = "http://localhost:$p"; break }
        } catch { }
    }
    if ($frontUrl) { break }
    Start-Sleep -Seconds 2
}
if (-not $frontUrl) {
    Write-Warn "no se pudo determinar el puerto del frontend; revisa su ventana"
    $frontUrl = "http://localhost:5173"
}

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "  REVO listo" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Frontend : $frontUrl" -ForegroundColor Yellow
Write-Host "  Auth     : http://localhost:8011/docs"
Write-Host "  Survey   : http://localhost:8012/docs"
Write-Host "  ML       : http://localhost:8013/docs"
Write-Host ""
Write-Host "  Usuarios sembrados:" -ForegroundColor DarkGray
Write-Host "    admin@revo.edu / Admin@REVO2025" -ForegroundColor DarkGray
Write-Host "    demo@revo.edu  / Demo@1234" -ForegroundColor DarkGray
Write-Host "================================================" -ForegroundColor Cyan

Start-Process $frontUrl
