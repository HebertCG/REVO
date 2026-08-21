@echo off
title REVO - Arranque local
echo ================================================
echo   REVO - arranque local
echo ================================================
echo.
echo Este lanzador delega en start-revo.ps1, que levanta
echo la pila completa (base, cache, servicios y pasarela)
echo con la misma topologia que produccion.
echo.
echo Antes arrancaba los tres microservicios sueltos en
echo 8011/8012/8013. Eso ya no refleja como corre el
echo sistema: los servicios no publican puerto y todo
echo pasa por la pasarela en el 8080.
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-revo.ps1"

if errorlevel 1 (
    echo.
    echo El arranque fallo. Revisa los mensajes de arriba.
    pause
    exit /b 1
)
