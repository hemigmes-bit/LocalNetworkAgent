param([string]$ComputerName="192.168.1.17",[string]$Message="Hola")
$text=$Message
if(-not $text){$text="Hola"}
Write-Host "Enviando voz a $ComputerName" -ForegroundColor Cyan

# Reproducir localmente primero
Write-Host "Reproduciendo aqui..." -ForegroundColor Cyan
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Speak($text)
Write-Host "OK voz local" -ForegroundColor Green

$cp=Join-Path $PSScriptRoot "core0-cred.xml"
$cred=$null
if(Test-Path $cp){$cred=Import-Clixml $cp}

# Intentar via WinRM
Write-Host "Intentando via WinRM..." -ForegroundColor Yellow
try{
    $splat=@{ComputerName=$ComputerName;ScriptBlock={param($m) Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;$v.Speak($m)};ArgumentList=$text;ErrorAction="Stop"}
    if($cred){$splat.Credential=$cred}
    Invoke-Command @splat
    Write-Host "OK via WinRM" -ForegroundColor Green
}catch{
    Write-Host "WinRM error:" -NoNewline; Write-Host $_.Exception.Message -ForegroundColor Red
}