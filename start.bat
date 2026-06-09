@echo off
echo ====================================
echo   FOOCATION - Arrancando servidor
echo ====================================
cd /d "%~dp0"

REM Matar cualquier proceso en puerto 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>nul

py -m uvicorn api:app --port 8000 --host 0.0.0.0
pause
