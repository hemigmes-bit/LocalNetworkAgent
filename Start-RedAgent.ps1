$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$logFile = "$projectPath\redagent-startup.log"
$OpenCodePassword = "RedAgent2026!"

function Write-StartLog {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Add-Content $logFile $line -ErrorAction SilentlyContinue
}

Write-StartLog "=== Inicio RedAgent ==="

& shutdown.exe /a 2>&1 | Out-Null
Write-StartLog "Apagados pendientes cancelados (shutdown /a)"

$ocRunning = Get-NetTCPConnection -LocalPort 4096 -State Listen -ErrorAction SilentlyContinue
if (-not $ocRunning) {
    Write-StartLog "opencode serve no activo. Iniciando..."
    $startArgs = "-ExecutionPolicy Bypass -NoProfile -Command `"`$env:OPENCODE_SERVER_PASSWORD='$OpenCodePassword'; Set-Location '$projectPath'; opencode serve --hostname 127.0.0.1 --port 4096`""
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $startArgs
    $ready = $false
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        if (Get-NetTCPConnection -LocalPort 4096 -State Listen -ErrorAction SilentlyContinue) {
            $ready = $true
            break
        }
    }
    if ($ready) {
        Write-StartLog "opencode serve LISTO (tras $($i+1)s)"
    } else {
        Write-StartLog "ERROR: opencode serve no arranco en 45s"
    }
} else {
    Write-StartLog "opencode serve ya estaba activo"
}

$botRunning = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "TelegramBot-OpenCode" }
if (-not $botRunning) {
    Write-StartLog "Bot Telegram no activo. Iniciando..."
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$projectPath\TelegramBot-OpenCode.ps1`""
    Start-Sleep -Seconds 3
    $botCheck = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "TelegramBot-OpenCode" }
    if ($botCheck) {
        Write-StartLog "Bot Telegram LISTO"
    } else {
        Write-StartLog "ERROR: Bot Telegram no arranco"
    }
} else {
    Write-StartLog "Bot Telegram ya estaba activo"
}

Write-StartLog "=== Fin RedAgent ==="