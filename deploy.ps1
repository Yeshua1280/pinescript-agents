$src = 'C:\Users\ivan\Desktop\TradingView\dist\TradingView CDP.exe'
$dst = 'C:\Users\ivan\Desktop\TradingView CDP.exe'

if (Test-Path $src) {
    Copy-Item -Path $src -Destination $dst -Force
    Write-Host '[OK] EXE copiado al escritorio'
} else {
    Write-Host '[ERROR] No se encontro el exe compilado en dist\'
    Get-ChildItem 'C:\Users\ivan\Desktop\TradingView\dist'
}

# Limpiar cache de iconos de Windows
ie4uinit.exe -show
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process explorer
Write-Host '[OK] Explorer reiniciado'
