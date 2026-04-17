# ============================================================
# TradingView Desktop — CDP Launch Script
# ============================================================
# Lanza TradingView Portable con Chrome DevTools Protocol
# habilitado en el puerto 9222 para el bridge MCP.
#
# Uso: .\launch-tradingview-cdp.ps1 [-Port 9222] [-Kill]
# ============================================================

param(
    [int]$Port = 9222,
    [switch]$Kill
)

$tvPath = "C:\Users\ivan\Desktop\TradingView\TradingView-Portable\TradingView.exe"

if (-not (Test-Path $tvPath)) {
    Write-Host "[ERROR] TradingView portable no encontrado en: $tvPath" -ForegroundColor Red
    exit 1
}

# Matar instancias existentes si se solicita
if ($Kill) {
    Write-Host "[INFO] Cerrando instancias existentes de TradingView..." -ForegroundColor Yellow
    taskkill /F /IM TradingView.exe 2>$null
    Start-Sleep -Seconds 2
}

# Verificar si ya hay algo en el puerto CDP
try {
    $existing = Invoke-RestMethod -Uri "http://localhost:$Port/json/version" -TimeoutSec 2
    Write-Host "[OK] CDP ya activo en puerto $Port — Browser: $($existing.Browser)" -ForegroundColor Green
    Write-Host "[OK] WebSocket: $($existing.webSocketDebuggerUrl)" -ForegroundColor Green
    exit 0
} catch {
    Write-Host "[INFO] Puerto $Port libre. Lanzando TradingView..." -ForegroundColor Cyan
}

# Lanzar TradingView con flag CDP
$proc = Start-Process -FilePath $tvPath -ArgumentList "--remote-debugging-port=$Port" -PassThru
Write-Host "[INFO] PID: $($proc.Id) — Esperando inicializacion..." -ForegroundColor Cyan

# Esperar a que CDP responda (max 20 segundos)
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $ver = Invoke-RestMethod -Uri "http://localhost:$Port/json/version" -TimeoutSec 2
        $ready = $true
        break
    } catch {}
}

if ($ready) {
    Write-Host "" 
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " TradingView CDP ACTIVO" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " Puerto:    $Port"
    Write-Host " Browser:   $($ver.Browser)"
    Write-Host " WebSocket: $($ver.webSocketDebuggerUrl)"
    Write-Host " PID:       $($proc.Id)"
    Write-Host "============================================" -ForegroundColor Green
    
    # Listar targets de chart
    $targets = Invoke-RestMethod -Uri "http://localhost:$Port/json/list" -TimeoutSec 3
    $charts = $targets | Where-Object { $_.type -eq "page" -and $_.url -match "tradingview.com/chart" }
    if ($charts) {
        Write-Host ""
        Write-Host " Charts encontrados:" -ForegroundColor Yellow
        foreach ($c in $charts) {
            Write-Host "   -> $($c.url)" -ForegroundColor White
        }
    }
} else {
    Write-Host "[WARN] TradingView lanzado (PID $($proc.Id)) pero CDP no responde aun. Intenta en unos segundos." -ForegroundColor Yellow
}
