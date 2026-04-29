# Configura las credenciales de red
$credPath = Join-Path $PSScriptRoot "core0-cred.xml"
Write-Host "=== CONFIGURADOR DE CREDENCIALES DE RED ===" -ForegroundColor Cyan
Write-Host "Introduzca usuario (ej: .\Administrador) y contraseña"
$cred = Get-Credential
if ($cred) {
    $cred | Export-CliXml -Path $credPath
    Write-Host "✅ Credenciales guardadas en: $credPath" -ForegroundColor Green
}
