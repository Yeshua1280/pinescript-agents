@echo off
echo ========================================================
echo   TRADINGVIEW CDP - MODO ANTIGRAVITY
echo ========================================================
echo.

:: Matar instancias previas para asegurar puerto limpio
echo [1/3] Cerrando instancias previas de TradingView...
taskkill /F /IM TradingView.exe /T 2>NUL
timeout /t 3 /nobreak > NUL

:: Ruta real - App instalada via Microsoft Store (WindowsApps)
set "TV_PATH=C:\Program Files\WindowsApps\TradingView.Desktop_3.0.0.7652_x64__n534cwy3pjxzj\TradingView.exe"

echo [2/3] Lanzando TradingView con Debug Port 9222...

if exist "%TV_PATH%" (
    start "" "%TV_PATH%" --remote-debugging-port=9222
    echo.
    echo ========================================================
    echo   TradingView INICIADO en modo CDP (puerto 9222)
    echo   Antigravity ahora puede controlar tus graficos.
    echo ========================================================
) else (
    echo [AVISO] Ruta exacta no encontrada. Intentando via shell...
    start "" "tradingview://"
    echo Lanzado via protocolo. El puerto CDP puede no estar activo.
)

echo.
echo [3/3] Esperando 5 segundos para que TradingView arranque...
timeout /t 5 /nobreak > NUL

:: Verificar que el puerto CDP esta abierto
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:9222/json/version' -TimeoutSec 3 -UseBasicParsing; Write-Host '[OK] Puerto CDP 9222 ACTIVO - Antigravity listo para conectar.' -ForegroundColor Green } catch { Write-Host '[AVISO] Puerto CDP no responde aun. Espera unos segundos o relanza.' -ForegroundColor Yellow }"

echo.
pause
