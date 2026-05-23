$cred = Get-Credential
$cred | Export-CliXml "C:\Users\Usuario\LocalNetworkAgent\victorymar-cred.xml"
Write-Host "Credenciales guardadas"