param([string]$ComputerName = "192.168.1.14")

Write-Host "Iniciando intercomunicador con $ComputerName..." -ForegroundColor Cyan

$credFile = Join-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) "core0-cred.xml"

try {
    $cred = $null
    if (Test-Path $credFile) {
        try { $cred = Import-CliXml $credFile } catch {}
    }
    if (-not $cred) {
        $cred = Get-Credential -UserName "Administrador" -Message "Credenciales para intercom en $ComputerName"
    }
    
    $taskName = "RemoteIntercom"
    
    Invoke-Command -ComputerName $ComputerName -Credential $cred -ScriptBlock {
        param($taskName)
        
        $scriptCode = @'
$host.UI.RawUI.WindowTitle = "INTERCOM - Remoto"
$host.UI.RawUI.BackgroundColor = "DarkBlue"
$host.UI.RawUI.ForegroundColor = "White"
Clear-Host
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "       INTERCOMUNICADOR ACTIVADO" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Escribe mensajes para el administrador." -ForegroundColor White
Write-Host "Escribe SALIR para cerrar." -ForegroundColor Gray
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
while ($true) {
    $msg = Read-Host "TU > "
    if ($msg -eq "SALIR") { break }
    $time = Get-Date -Format "HH:mm:ss"
    Write-Host "[$time] TU: $msg" -ForegroundColor Green
}
Write-Host "`nIntercomunicador cerrado." -ForegroundColor Red
Start-Sleep -Seconds 2
'@
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($scriptCode))
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoExit -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"
        
        Register-ScheduledTask -TaskName $taskName -Action $action -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName
        
        Start-Sleep -Seconds 5
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    } -ArgumentList $taskName
    
    Write-Host "Intercomunicador abierto en $ComputerName." -ForegroundColor Green
    Start-Sleep -Seconds 3
} catch {
    [Windows.Forms.MessageBox]::Show("Error: " + $_.Exception.Message)
}