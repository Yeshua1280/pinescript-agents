# clean_build.ps1 - Compila y renombra con underscore para romper TODA cache posible.

$dist  = 'C:\Users\ivan\Desktop\TradingView\dist'
$build = 'C:\Users\ivan\Desktop\TradingView\build'
$spec  = 'C:\Users\ivan\Desktop\TradingView\TradingView CDP.spec'
$dst   = 'C:\Users\ivan\Desktop\TradingView_CDP.exe'

# 1. Eliminar cache de pyinstaller
if (Test-Path $dist)  { Remove-Item -Recurse -Force $dist; }
if (Test-Path $build) { Remove-Item -Recurse -Force $build; }

# Eliminar el acceso viejo para que el usuario no se confunda
$old_dst = 'C:\Users\ivan\Desktop\TradingView CDP.exe'
if (Test-Path $old_dst) { Remove-Item -Force $old_dst; }

# 2. Rebuild limpio
Write-Host '[BUILD] Compilando...'
Set-Location 'C:\Users\ivan\Desktop\TradingView'
python -m PyInstaller --noconfirm $spec

# 3. Eliminar IconCache ANTES de copiar (y apagar explorer)
Write-Host '[CACHE] Limpiando cache profundo de iconos...'
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 4. Copiar al escritorio (sobreescribiendo mientras explorer esta apagado)
$newExe = 'C:\Users\ivan\Desktop\TradingView\dist\TradingView CDP.exe'
if (Test-Path $newExe) {
    Copy-Item -Path $newExe -Destination $dst -Force
    # Cambiar la fecha de modificacion para invalidar cache adicional
    (Get-Item $dst).LastWriteTime = Get-Date
    Write-Host '[OK] EXE Copiado y timestamp actualizado'
} else {
    Write-Host '[ERROR] Fallo el build'
}

# 5. Reiniciar explorer
Start-Process explorer
Write-Host '[OK] Explorer reiniciado - Cache bypasseada por renombre.'
