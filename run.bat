@echo off
title Weather Finder
echo ============================================
echo   Weather Finder - Monitoramento Climatico
echo ============================================
echo.
echo Iniciando aplicacao...
echo.
REM python "%~dp0weather_finder.py"
"c:\Users\neialuc\Documents\GitHub\weather-finder\.venv\Scripts\python.exe" "weather_finder.py"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRO] Falha ao iniciar. Verifique se o Python esta instalado
    echo        e as dependencias foram instaladas:
    echo        pip install -r requirements.txt
    echo.
    pause
)
