# Script para configurar WoL en CORE0 remotamente
# Usa WMI para configurar el adaptador de red

$CORE0_IP = "192.168.1.13"
$CORE0_MAC = "5C-85-7E-41-80-2B"

Write-Host "=== CONFIGURANDO WAKE-ON-LAN EN CORE0 ($CORE0_IP) ===" -ForegroundColor Cyan
Write-Host ""

# Intentar conexión con credenciales guardadas
$credPath = "$PSScriptRoot\core0-cred.xml"
if (Test-Path $credPath) {
    $cred = Import-CliXml -Path $credPath
    Write-Host "Usando credenciales guardadas..." -ForegroundColor Gray
} else {
    $cred = Get-Credential -Message "Credenciales de CORE0"
}

if (-not $cred) {
    Write-Host "Error: No se proporcionaron credenciales." -ForegroundColor Red
    exit 1
}

# Script remoto para configurar WoL
$remoteScript = {
    Write-Host "=== Configurando WoL en CORE0 ===" -ForegroundColor Cyan
    
    # 1. Habilitar Wake-on-LAN en registro
    Write-Host "[1] Configurando registro..." -ForegroundColor Yellow
    $registryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\*"
    $adapterKeys = Get-ChildItem $registryPath -ErrorAction SilentlyContinue
    
    foreach ($key in $adapterKeys) {
        $props = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
        if ($props.DriverDesc) {
            Write-Host "  Adaptador: $($props.DriverDesc)" -ForegroundColor Gray
            
            # Habilitar Wake-on-LAN
            Set-ItemProperty -Path $key.PSPath -Name "*WakeOnMagicPacket" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $key.PSPath -Name "*WakeOnPattern" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $key.PSPath -Name "*EnablePowerManagement" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $key.PSPath -Name "PnPCapabilities" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
            
            Write-Host "    WoL habilitado" -ForegroundColor Green
        }
    }
    
    # 2. Deshabilitar hibernación y inicio rápido
    Write-Host "[2] Configurando energía..." -ForegroundColor Yellow
    powercfg /h /off
    Write-Host "    Hibernación deshabilitada" -ForegroundColor Green
    
    # 3. Configurar plan de energía
    Write-Host "[3] Configurando plan de energía..." -ForegroundColor Yellow
    powercfg /setactive SCHEME_MIN
    Write-Host "    Plan de alto rendimiento activado" -ForegroundColor Green
    
    # 4. Verificar configuración
    Write-Host "[4] Verificando configuración..." -ForegroundColor Yellow
    $wolStatus = Get-ItemProperty -Path $registryPath -ErrorAction SilentlyContinue | Where-Object { $_.'*WakeOnMagicPacket' -eq 1 }
    if ($wolStatus) {
        Write-Host "    WoL configurado correctamente en $($wolStatus.Count) adaptador(es)" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "=== Configuración completada ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "PARA APAGAR CORE0 CORRECTAMENTE (WoL compatible):" -ForegroundColor Cyan
    Write-Host "  shutdown /s /t 0 /full" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "NOTA: El LED del adaptador Ethernet debe permanecer encendido tras apagar" -ForegroundColor Yellow
}

try {
    # Intentar usar Invoke-Command
    $session = New-PSSession -ComputerName $CORE0_IP -Credential $cred -ErrorAction Stop
    Write-Host "Conectado a CORE0" -ForegroundColor Green
    Write-Host ""
    
    Invoke-Command -Session $session -ScriptBlock $remoteScript
    
    Remove-PSSession $session
    Write-Host ""
    Write-Host "=== SESION FINALIZADA ===" -ForegroundColor Green
} catch {
    Write-Host "ERROR: No se pudo conectar a CORE0." -ForegroundColor Red
    Write-Host "Detalle: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Sugerencia: Ejecuta 'Enable-PSRemoting -Force' en CORE0" -ForegroundColor Yellow
    Write-Host "O usa el script Enable-WoL.ps1 directamente en CORE0" -ForegroundColor Yellow
}

Read-Host "Enter para continuar"