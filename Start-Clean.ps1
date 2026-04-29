Write-Host 'Limpiando procesos antiguos...' -ForegroundColor Cyan
Get-Process LocalNetworkAgent, LocalNetworkAgent_Debug, VoiceControl -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host 'Arrancando v2.0.4...' -ForegroundColor Green
Start-Process '.\LocalNetworkAgent.exe'
