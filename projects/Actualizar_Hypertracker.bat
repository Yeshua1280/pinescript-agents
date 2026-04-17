@echo off
color 0B
echo.
echo ==============================================================
echo     ✨ ACTUALIZADOR AUTOMATICO DE HYPERTRACKER DASHBOARD ✨
echo ==============================================================
echo.
echo ⚠️  MUY IMPORTANTE ANTES DE SEGUIR:
echo       1. Has probado el codigo viejo ejecutandolo con:
echo          pythonw hypertracker_dashboard.pyw ?
echo       2. Te aseguras de que no hay errores ni se rompe la UI?
echo.
echo    Si no lo has probado, CANCELA AHORA MISMO (Ctrl + C).
echo.
pause

echo.
echo [1/3] Iniciando el empaquetado seguro...
echo Usando el Python del sistema (WindowsApps) que incluye "customtkinter"
echo.
@REM NO USAMOS EL PYINSTALLER DEL ENTORNO VIRTUAL.
"C:\Users\ivan\AppData\Local\Microsoft\WindowsApps\python.exe" -m PyInstaller --noconfirm --onefile --windowed --icon=hypertracker.ico --name="Hypertracker Dashboard" --collect-all customtkinter hypertracker_dashboard.pyw

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo ❌ ERROR en la compilacion. Revisa el codigo.
    pause
    exit /b
)

echo.
echo [2/3] Compilacion Exitosa. Copiando el ejecutable al Escritorio...
copy /Y "dist\Hypertracker Dashboard.exe" "C:\Users\ivan\Desktop\Hypertracker Dashboard.exe"

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo ❌ ERROR al copiar al Escritorio. Quiza el programa esta abierto. Cierra Hypertracker e intentalo de nuevo.
    pause
    exit /b
)

echo.
color 0A
echo [3/3] ✅ COMPLETO!
echo.
echo La nueva version ya esta en tu Escritorio lista para ser usada.
echo Puedes cerrar esta ventana.
pause
