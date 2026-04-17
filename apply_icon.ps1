# apply_icon.ps1 - Aplica tv_perfect.ico al shortcut de TradingView y refresca el escritorio

$icoPath = 'C:\Users\ivan\Desktop\TradingView\tv_perfect.ico'

# Buscar shortcut de TradingView en el escritorio
$lnkPath = Get-ChildItem -Path 'C:\Users\ivan\Desktop' -Filter '*TradingView*' | Select-Object -First 1 -ExpandProperty FullName

if ($lnkPath) {
    Write-Host "Shortcut encontrado: $lnkPath"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnkPath)
    $shortcut.IconLocation = "$icoPath,0"
    $shortcut.Save()
    Write-Host "[OK] Icono aplicado: $icoPath"
} else {
    Write-Host "[WARN] No se encontro shortcut de TradingView CDP en el escritorio"
}

# Limpiar cache de iconos y reiniciar explorer
ie4uinit.exe -show
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process explorer
Write-Host "[OK] Explorer reiniciado - cache de iconos limpiado"
