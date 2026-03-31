@echo off
title REVO - Sistema ML Recomendacion
echo ================================================
echo   REVO - Iniciando todos los servicios...
echo ================================================
echo.

:: Auth Service (8011)
echo [1/4] Iniciando Auth Service en puerto 8011...
start "REVO-Auth" cmd /k "cd /d %~dp0services\auth-service && venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8011 --reload"
timeout /t 3 /nobreak >nul

:: Survey Service (8012)
echo [2/4] Iniciando Survey Service en puerto 8012...
start "REVO-Survey" cmd /k "cd /d %~dp0services\survey-service && venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8012 --reload"
timeout /t 3 /nobreak >nul

:: ML Service (8013)
echo [3/4] Iniciando ML Service (Arbol de Decision) en puerto 8013...
start "REVO-ML" cmd /k "cd /d %~dp0services\ml-service && venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8013 --reload"
timeout /t 5 /nobreak >nul

:: Frontend React (5173)
echo [4/4] Iniciando Frontend React en puerto 5173...
start "REVO-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host"
timeout /t 5 /nobreak >nul

echo.
echo ================================================
echo   Todos los servicios iniciados:
echo   Auth:    http://localhost:8011/docs
echo   Survey:  http://localhost:8012/docs
echo   ML:      http://localhost:8013/docs
echo   Frontend:http://localhost:5173
echo ================================================
echo.
echo Abriendo el sistema en el navegador...
timeout /t 3 /nobreak >nul
start http://localhost:5173
