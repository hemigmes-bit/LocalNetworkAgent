# Add-NortonExclusion.ps1 - Ejecutar como Administrador

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"

Write-Host "=== Exclusion para antivirus ===" -ForegroundColor Cyan
Write-Host ""

# Agregar exclusion a Windows Defender
Add-MpPreference -ExclusionPath $projectPath -ErrorAction SilentlyContinue
Write-Host "[OK] Windows Defender: exclusion agregada" -ForegroundColor Green

# Mostrar lista para agregar manualmente en Norton
Write-Host ""
Write-Host "=== MANUALMENTE EN NORTON ===" -ForegroundColor Cyan
Write-Host "1. Abre Norton Security"
Write-Host "2. Configuracion > Analisis y riesgos"
Write-Host "3. Exclusiones > Agregar exclusion"
Write-Host "4. Selecciona: $projectPath"
Write-Host ""

# Crear lista
$list = @"
Archivos a excluir en Norton:
$projectPath\LocalNetworkAgent.exe
$projectPath\LocalNetworkAgent-GUI.ps1
$projectPath\Explorer_Agent.ps1
$projectPath\NetworkUtilsPublic.psm1
"@
$list | Out-File "$projectPath\norton-exclusion.txt" -Encoding UTF8

Write-Host "Lista guardada en: norton-exclusion.txt" -ForegroundColor Green