# start-revo.ps1 — Levanta todos los servicios REVO en ventanas separadas
$root = $PSScriptRoot

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  REVO - Iniciando todos los servicios..." -ForegroundColor Cyan
Write-Host "================================================"

# Auth Service
Write-Host "[1/4] Auth Service -> http://localhost:8011" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\services\auth-service'; .\venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8011 --reload"
Start-Sleep 3

# Survey Service
Write-Host "[2/4] Survey Service -> http://localhost:8012" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\services\survey-service'; .\venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8012 --reload"
Start-Sleep 3

# ML Service
Write-Host "[3/4] ML Service -> http://localhost:8013" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\services\ml-service'; .\venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8013 --reload"
Start-Sleep 5

# Frontend React
Write-Host "[4/4] Frontend React -> http://localhost:5173" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev -- --host"
Start-Sleep 5

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Servicios REVO activos:" -ForegroundColor Cyan
Write-Host "  Auth:     http://localhost:8011/docs" -ForegroundColor White
Write-Host "  Survey:   http://localhost:8012/docs" -ForegroundColor White
Write-Host "  ML:       http://localhost:8013/docs" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan

Start-Process "http://localhost:5173"
