# =============================================================================
# Connect-CORE0.ps1 (v2.2.5 - AUTO-CREDENTIALS & DYNAMIC IP)
# =============================================================================

Import-Module "$PSScriptRoot\NetworkUtilsPublic.psm1" -Force

Write-Host "=== CONEXION REMOTA A CORE0 ===" -ForegroundColor Cyan
Write-Host ""

# 1. Cargar la configuración de red
$config = Get-NetworkConfig
$CORE0_IP = Resolve-ComputerAddress "CORE0" $config
if ($CORE0_IP) {
    Write-Host "CORE0 detectado en: $CORE0_IP" -ForegroundColor Green
} else {
    $CORE0_IP = "192.168.1.16"
    Write-Host "CORE0 no encontrado en el config. Usando IP manual: $CORE0_IP" -ForegroundColor Yellow
}

# 2. CARGAR CREDENCIALES AUTOMATICAMENTE
$credPath = "$PSScriptRoot\core0-cred.xml"
if (Test-Path $credPath) {
    Write-Host "Cargando credenciales guardadas de core0-cred.xml..." -ForegroundColor Gray
    $cred = Import-CliXml -Path $credPath
} else {
    $stored = Get-StoredCredential
    if ($stored) {
        Write-Host "Cargando credenciales almacenadas de core0-cred.xml..." -ForegroundColor Gray
        $cred = $stored
    } else {
        Write-Host "No se encontraron credenciales guardadas." -ForegroundColor Yellow
        $cred = Get-Credential -Message "Introduce credenciales de CORE0 ($CORE0_IP)"
    }
}

if (-not $cred) { Write-Host "Error: No hay credenciales." -ForegroundColor Red; exit 1 }

Write-Host "Conectando a $CORE0_IP..." -ForegroundColor Cyan

try {
    $session = New-PSSession -ComputerName $CORE0_IP -Credential $cred -ErrorAction Stop
    Write-Host "Conexion exitosa!" -ForegroundColor Green

    # Ejecutar comandos de informacion
    $info = Invoke-Command -Session $session -ScriptBlock {
        [PSCustomObject]@{ Hostname = $env:COMPUTERNAME; User = $env:USERNAME; OS = (Get-CimInstance Win32_OperatingSystem).Caption }
    }
    $info | Format-Table -AutoSize | Out-Host

    Write-Host "Copiando scripts de mantenimiento..." -ForegroundColor Gray
    $scripts = @("Fix-WoL-Power.ps1", "Diagnose-WoL.ps1")
    foreach ($s in $scripts) {
        if (Test-Path "$PSScriptRoot\$s") {
            Copy-Item -ToSession $session -Path "$PSScriptRoot\$s" -Destination "C:\Users\Public\Documents\$s" -Force
        }
    }

    Write-Host "Ejecutando diagnostico en CORE0..." -ForegroundColor Gray
    Invoke-Command -Session $session -ScriptBlock { & "C:\Users\Public\Documents\Diagnose-WoL.ps1" }

    Remove-PSSession $session
    Write-Host "`n=== SESION FINALIZADA ===" -ForegroundColor Green

} catch {
    Write-Host "ERROR: No se pudo conectar a $CORE0_IP." -ForegroundColor Red
    Write-Host "Detalle: $_" -ForegroundColor Red
    Write-Host "`nSugerencia: Ejecuta 'Enable-PSRemoting -Force' en el servidor remoto." -ForegroundColor Yellow
}
Read-Host "`nEnter para cerrar"
