@echo off
echo ====================================
echo   CANASTA MVP - Instalando librerias
echo ====================================
py -m pip install requests beautifulsoup4 --quiet

echo.
echo ====================================
echo   Descargando precios...
echo ====================================
py scrapers/mercadona.py
py scrapers/carrefour.py
py scrapers/dia.py

echo.
echo ====================================
echo   Calculando mejor canasta...
echo ====================================
py canasta.py

pause
