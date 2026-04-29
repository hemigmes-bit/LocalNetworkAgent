# Script para agregar exclusiones en Norton Security
# Ejecutar como Administrador

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$exePath = Join-Path $projectPath "LocalNetworkAgent.exe"

Write-Host "=== Agregar exclusiones en Norton ===" -ForegroundColor Cyan
Write-Host ""

# Método 1: Intentar agregar a través de WMI (si Norton lo soporta)
try {
    $nortonService = Get-WmiObject -Namespace "ROOT\Symantec" -Class "Exclusion" -ErrorAction Stop
    Write-Host "[Norton] Servicio WMI encontrado" -ForegroundColor Green
} catch {
    Write-Host "[Norton] Servicio WMI no disponible, se requiere configuración manual" -ForegroundColor Yellow
}

# Método 2: Crear archivo de configuración para Norton
$configContent = @"
<?xml version="1.0" encoding="UTF-8"?>
<!-- Norton Security Exclusions Configuration -->
<Exclusions>
  <Files>
    <File Path="$exePath" Type="Exclude" />
  </Files>
  <Directories>
    <Directory Path="$projectPath" Type="Exclude" />
  </Directories>
  <Processes>
    <Process Name="LocalNetworkAgent.exe" Type="Exclude" />
  </Processes>
</Exclusions>
"@

$configPath = Join-Path $projectPath "norton-exclusions.xml"
$configContent | Out-File -FilePath $configPath -Encoding UTF8
Write-Host "[Archivo] Creado: $configPath" -ForegroundColor Green

Write-Host ""
Write-Host "=== Instrucciones para agregar exclusiones en Norton ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Abra Norton Security" -ForegroundColor White
Write-Host "2. Vaya a Configuración > Antivirus > Exclusiones y bajo riesgo" -ForegroundColor White
Write-Host "3. En 'Elementos excluidos del análisis', haga clic en 'Agregar carpetas'" -ForegroundColor White
Write-Host "4. Agregue: $projectPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "5. En 'Excluir del Control de inteligencia artificial', agregue:" -ForegroundColor White
Write-Host "   $exePath" -ForegroundColor Cyan
Write-Host ""
Write-Host "El ejecutable ya está firmado digitalmente, lo que reduce las advertencias." -ForegroundColor Green
Write-Host "Certificado: CN=LocalNetworkAgent (Thumbprint: A8894D32DB33D37E050A0BDD291ED2147720E995)" -ForegroundColor Green
Write-Host ""
Write-Host "Presione cualquier tecla para continuar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")