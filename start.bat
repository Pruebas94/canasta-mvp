@echo off
echo ====================================
echo   CANASTA MVP - Arrancando servidor
echo ====================================
cd /d "%~dp0"
py -m uvicorn api:app --port 8000 --host 0.0.0.0
pause
