# Script de diagnóstico para conexión remota
param([string]$ComputerName = "192.168.1.15")

Write-Host "=== DIAGNÓSTICO DE CONEXIÓN REMOTA ===" -ForegroundColor Cyan
Write-Host "Equipo remoto: $ComputerName" -ForegroundColor Yellow
Write-Host ""

# 1. Test de ping
Write-Host "[1/5] Probando conectividad (ping)..." -ForegroundColor Cyan
try {
    $ping = Test-Connection -ComputerName $ComputerName -Count 2 -Quiet
    if ($ping) {
        Write-Host "  OK - El equipo responde al ping" -ForegroundColor Green
    } else {
        Write-Host "  ERROR - El equipo no responde al ping" -ForegroundColor Red
        Write-Host "  Solución: Verifica que el equipo esté encendido y en la misma red"
        return
    }
} catch {
    Write-Host "  ERROR - $($_.Exception.Message)" -ForegroundColor Red
}

# 2. Test de puerto WinRM (5985)
Write-Host "[2/5] Probando puerto WinRM (5985)..." -ForegroundColor Cyan
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.ConnectAsync($ComputerName, 5985).Wait(3000) | Out-Null
    if ($tcp.Connected) {
        Write-Host "  OK - Puerto 5985 accesible" -ForegroundColor Green
    } else {
        Write-Host "  ERROR - Puerto 5985 no responde" -ForegroundColor Red
        Write-Host "  Solución: Verifica el firewall en el equipo remoto"
    }
    $tcp.Close()
} catch {
    Write-Host "  ERROR - $($_.Exception.Message)" -ForegroundColor Red
}

# 3. Test WSMan
Write-Host "[3/5] Probando WinRM (Test-WSMan)..." -ForegroundColor Cyan
try {
    $wsman = Test-WSMan -ComputerName $ComputerName -ErrorAction Stop
    Write-Host "  OK - WinRM responde correctamente" -ForegroundColor Green
} catch {
    Write-Host "  ERROR - WinRM no responde" -ForegroundColor Red
    Write-Host "  Posibles causas:"
    Write-Host "    - WinRM no está ejecutándose en el equipo remoto"
    Write-Host "    - El servicio está detenido"
    Write-Host "    - Firewall bloquea el puerto 5985"
}

# 4. Verificar TrustedHosts
Write-Host "[4/5] Verificando TrustedHosts..." -ForegroundColor Cyan
try {
    $trustedHosts = Get-Item WSMan:\localhost\Client\TrustedHosts -ErrorAction Stop
    Write-Host "  TrustedHosts: $($trustedHosts.Value)" -ForegroundColor Yellow
    if ($trustedHosts.Value -like "*$ComputerName*" -or $trustedHosts.Value -eq "*") {
        Write-Host "  OK - El equipo está en la lista de confianza" -ForegroundColor Green
    } else {
        Write-Host "  ADVERTENCIA - El equipo NO está en TrustedHosts" -ForegroundColor Yellow
        Write-Host "  Ejecuta como Administrador:"
        Write-Host "    Set-Item WSMan:\localhost\Client\TrustedHosts -Value '$ComputerName' -Force -Concatenate"
    }
} catch {
    Write-Host "  ERROR - No se pudo leer TrustedHosts" -ForegroundColor Red
}

# 5. Prueba de sesión PowerShell
Write-Host "[5/5] Probando sesión PowerShell..." -ForegroundColor Cyan
try {
    $session = New-PSSession -ComputerName $ComputerName -ErrorAction Stop
    Write-Host "  OK - Sesión creada correctamente" -ForegroundColor Green
    Remove-PSSession $session
} catch {
    Write-Host "  ERROR - No se pudo crear la sesión" -ForegroundColor Red
    Write-Host "  Detalle: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== DIAGNÓSTICO COMPLETADO ===" -ForegroundColor Cyan
