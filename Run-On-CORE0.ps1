# Script para ejecutar comandos en CORE0 remotamente
param(
    [string]$Command = "diagnose"
)

$CORE0_IP = "192.168.1.14"

Write-Host "=== CONEXION A CORE0 ($CORE0_IP) ===" -ForegroundColor Cyan

$cred = Get-Credential -Message "Usuario de CORE0"

if (-not $cred) { exit 1 }

try {
    $session = New-PSSession -ComputerName $CORE0_IP -Credential $cred -ErrorAction Stop
    Write-Host "Conectado a CORE0" -ForegroundColor Green
    Write-Host ""

    if ($Command -eq "diagnose") {
        Write-Host "=== DIAGNOSTICO WoL ===" -ForegroundColor Cyan
        Invoke-Command -Session $session -ScriptBlock {
            Write-Host "Adaptadores de red:" -ForegroundColor Yellow
            Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, MacAddress, InterfaceDescription | Format-Table

            Write-Host "Configuracion WoL en registro:" -ForegroundColor Yellow
            $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\*"
            Get-ChildItem $regPath | ForEach-Object {
                $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                if ($p.DriverDesc) {
                    Write-Host "  $($p.DriverDesc):"
                    Write-Host "    *WakeOnMagicPacket = $($p.'*WakeOnMagicPacket')"
                    Write-Host "    *EnablePowerManagement = $($p.'*EnablePowerManagement')"
                }
            }

            Write-Host ""
            Write-Host "Estado de energia:" -ForegroundColor Yellow
            powercfg /a
        }
    }
    elseif ($Command -eq "fix") {
        Write-Host "=== CONFIGURANDO WoL ===" -ForegroundColor Cyan
        Invoke-Command -Session $session -ScriptBlock {
            Write-Host "Deshabilitando hibernacion..." -ForegroundColor Yellow
            powercfg /h /off

            Write-Host "Configurando registro..." -ForegroundColor Yellow
            $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\*"
            Get-ChildItem $regPath | ForEach-Object {
                $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                if ($p.DriverDesc) {
                    Set-ItemProperty -Path $_.PSPath -Name "*WakeOnMagicPacket" -Value 1 -Type DWord -Force
                    Set-ItemProperty -Path $_.PSPath -Name "*EnablePowerManagement" -Value 1 -Type DWord -Force
                    Set-ItemProperty -Path $_.PSPath -Name "PnPCapabilities" -Value 0 -Type DWord -Force
                }
            }
            Write-Host "Configuracion completada" -ForegroundColor Green
        }
    }
    elseif ($Command -eq "shutdown") {
        Write-Host "Apagando CORE0..." -ForegroundColor Yellow
        Invoke-Command -Session $session -ScriptBlock {
            shutdown /s /t 0 /full
        }
        Write-Host "Comando de apagado enviado" -ForegroundColor Green
    }

    Remove-PSSession $session
    Write-Host ""
    Write-Host "=== COMPLETADO ===" -ForegroundColor Green

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}
