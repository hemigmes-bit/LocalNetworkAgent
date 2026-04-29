param([string]$ComputerName = "192.168.1.10")

Add-Type -AssemblyName Microsoft.VisualBasic
$text = [Microsoft.VisualBasic.Interaction]::InputBox("Escribe lo que quieres que diga CORE0:", "Megafonia Remota", "Hola CORE0")

if (-not $text) { exit }

Write-Host "Enviando voz a $ComputerName..." -ForegroundColor Cyan

try {
    # Intentar cargar credenciales guardadas si existen
    $credPath = "$PSScriptRoot\core0-cred.xml"
    $params = @{ ComputerName = $ComputerName; ScriptBlock = { param($msg); $s = New-Object -ComObject SAPI.SpVoice; $s.Speak($msg) }; ArgumentList = $text }
    
    if (Test-Path $credPath) { 
        $params.Credential = Import-CliXml -Path $credPath 
    }

    Invoke-Command @params
    Write-Host "Mensaje reproducido con exito en CORE0." -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    # Si falla, pedir credenciales de nuevo
    $cred = Get-Credential -UserName "Administrador" -Message "Credenciales para $ComputerName"
    $cred | Export-CliXml -Path $credPath -Force
    Invoke-Command -ComputerName $ComputerName -Credential $cred -ScriptBlock $params.ScriptBlock -ArgumentList $text
}
Pause
