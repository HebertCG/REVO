# ============================================================
# REVO — Arranque local completo
# ============================================================
# Uso:  .\start-revo.ps1
#
# Hace todo lo necesario, en orden, y verifica cada paso:
#   1. Comprueba Docker
#   2. Genera el .env con secretos propios si falta
#   3. Levanta la pila completa en Docker (base, cache, servicios, pasarela)
#   4. Espera a que todo este sano
#   5. Arranca el frontend Vite (5173)
#
# Se puede volver a ejecutar sin problema.
#
# ── Por que cambio respecto a la version anterior ──────────
# Antes este script arrancaba los tres microservicios sueltos en los puertos
# 8011/8012/8013 y el frontend hablaba directamente con cada uno. Eso ya no
# refleja como corre el sistema: en produccion los servicios no publican
# ningun puerto y todo pasa por la pasarela. Desarrollar contra una topologia
# distinta hace que los fallos de enrutado, de CORS y de cabeceras solo
# aparezcan al desplegar.
#
# Ahora se levanta la MISMA pila, con recarga en caliente encima
# (docker-compose.desarrollo.yml): se edita un .py y el servicio se reinicia
# solo, sin renunciar a probar contra la pasarela real.
# ============================================================

# "Continue" a proposito: con "Stop", cualquier linea que docker o npm
# escriban en stderr (incluidos avisos inofensivos) se convierte en un
# error fatal en PowerShell 5.1 y aborta el arranque. Los fallos reales
# se detectan comprobando $LASTEXITCODE y el estado de los contenedores.
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot

$composeArgs = @(
    "-f", (Join-Path $root "docker-compose.yml"),
    "-f", (Join-Path $root "docker-compose.desarrollo.yml")
)

function Write-Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)       { Write-Host "      OK  $msg" -ForegroundColor Green }
function Write-Info($msg)     { Write-Host "      ..  $msg" -ForegroundColor DarkGray }
function Write-Warn($msg)     { Write-Host "      !   $msg" -ForegroundColor Yellow }
function Write-Bad($msg)      { Write-Host "      X   $msg" -ForegroundColor Red }

function New-Secreto {
    # 48 bytes en base64 url-safe. Se genera aqui y no se copia de ningun
    # ejemplo: un secreto que aparece en un fichero de plantilla es publico.
    $bytes = New-Object byte[] 36
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  REVO - arranque local" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# ── 1. Docker ───────────────────────────────────────────────
Write-Step "1/5" "Comprobando Docker"

docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Bad "Docker Desktop no responde. Abrelo y vuelve a ejecutar."
    exit 1
}
Write-Ok "Docker disponible"

# ── 2. Secretos ─────────────────────────────────────────────
Write-Step "2/5" "Archivo .env"

$envPath = Join-Path $root ".env"

if (Test-Path $envPath) {
    Write-Ok ".env ya existe (no se toca)"

    # Aviso si falta alguna variable nueva: la causa mas comun de que la pila
    # no arranque tras actualizar es un .env de una version anterior.
    $contenido = Get-Content $envPath -Raw
    $requeridas = @(
        "POSTGRES_PASSWORD", "APP_DB_PASSWORD", "SERVICE_DB_PASSWORD",
        "REDIS_PASSWORD", "JWT_SECRET", "GATEWAY_SECRET"
    )
    $faltan = $requeridas | Where-Object { $contenido -notmatch "(?m)^$_=.+" }

    if ($faltan.Count -gt 0) {
        Write-Warn "Faltan variables en tu .env: $($faltan -join ', ')"
        Write-Info "Anadelas con un valor propio o borra el .env para regenerarlo."
    }
} else {
    Write-Info "No existe: generando uno con secretos nuevos"

    $lineas = @(
        "ENVIRONMENT=development",
        "PUERTO_PUBLICO=8080",
        "",
        "POSTGRES_DB=revo_db",
        "POSTGRES_USER=revo_user",
        "POSTGRES_PASSWORD=$(New-Secreto)",
        "APP_DB_PASSWORD=$(New-Secreto)",
        "SERVICE_DB_PASSWORD=$(New-Secreto)",
        "DB_REQUIRE_SSL=false",
        "",
        "REDIS_PASSWORD=$(New-Secreto)",
        "",
        "JWT_SECRET=$(New-Secreto)",
        "JWT_EXPIRE_HOURS=24",
        "",
        "GATEWAY_SECRET=$(New-Secreto)",
        "REQUIRE_GATEWAY=true",
        "TRUSTED_PROXY_COUNT=1",
        "",
        "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
        "",
        "VITE_API_URL=http://localhost:8080/api"
    )
    Set-Content -Path $envPath -Value ($lineas -join "`n") -Encoding utf8
    Write-Ok ".env generado con seis secretos distintos"
}

# ── 3. Levantar la pila ─────────────────────────────────────
Write-Step "3/5" "Levantando la pila en Docker"
Write-Info "Base de datos, Redis, tres servicios y pasarela"
Write-Info "La primera vez tarda: hay que construir las imagenes"

& docker compose @composeArgs up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Bad "docker compose fallo. Revisa la salida de arriba."
    exit 1
}
Write-Ok "Contenedores lanzados"

# ── 4. Esperar a que este sano ──────────────────────────────
Write-Step "4/5" "Esperando a que los servicios esten sanos"

$sano = $false
foreach ($i in 1..60) {
    $estados = (& docker compose @composeArgs ps --format "{{.Name}} {{.Health}}") 2>$null

    if ($estados -and ($estados -notmatch "starting") -and ($estados -notmatch "unhealthy")) {
        $sano = $true
        break
    }
    Start-Sleep -Seconds 3
}

if (-not $sano) {
    Write-Warn "Algun servicio no llego a estado sano en 3 minutos."
    & docker compose @composeArgs ps
    Write-Info "Registros: docker compose $($composeArgs -join ' ') logs -f"
} else {
    Write-Ok "Todos los servicios responden"
}

# La sonda de la pasarela es la que confirma que la cadena entera funciona.
try {
    $salud = Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing -TimeoutSec 5
    if ($salud.StatusCode -eq 200) { Write-Ok "Pasarela respondiendo en 8080" }
} catch {
    Write-Warn "La pasarela todavia no responde en 8080"
}

# ── 5. Frontend ─────────────────────────────────────────────
Write-Step "5/5" "Frontend (Vite, puerto 5173)"

$frontDir = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontDir "node_modules"))) {
    Write-Info "Instalando dependencias de npm (solo la primera vez)"
    Push-Location $frontDir
    npm install
    Pop-Location
}

Write-Info "Abriendo el servidor de desarrollo en una ventana nueva"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontDir'; npm run dev"

# ── Resumen ─────────────────────────────────────────────────
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "  REVO en marcha" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Aplicacion : http://localhost:5173"
Write-Host "  API        : http://localhost:8080/api"
Write-Host ""
Write-Host "  Los microservicios NO tienen puerto propio: se llega a ellos"
Write-Host "  solo por la pasarela, igual que en produccion." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Registros  : docker compose $($composeArgs -join ' ') logs -f"
Write-Host "  Base       : psql -h localhost -p 5434 -U revo_user -d revo_db"
Write-Host "  Parar todo : docker compose $($composeArgs -join ' ') down"
Write-Host ""
Write-Host "  Comprobar el despliegue:" -ForegroundColor DarkGray
Write-Host "    bash infraestructura/verificar_despliegue.sh" -ForegroundColor DarkGray
Write-Host ""
