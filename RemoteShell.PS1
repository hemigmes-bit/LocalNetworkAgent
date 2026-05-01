param($IP)
if (-not $IP) { Write-Host "Uso: RemoteShell.PS1 -IP 192.168.1.17"; exit }
$cred = "$PSScriptRoot\core0-cred.xml"
if (Test-Path $cred) {
    $c = Import-CliXml $cred
    Enter-PSSession -ComputerName $IP -Credential $c
} else {
    Enter-PSSession -ComputerName $IP
}