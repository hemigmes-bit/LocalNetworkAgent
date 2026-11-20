# Bloqueo de Roblox mediante archivo hosts (redirige dominios a 127.0.0.1)
Write-Host "Creando copia de seguridad del archivo hosts..."
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$backupPath = "$hostsPath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
Copy-Item -Path $hostsPath -Destination $backupPath -Force -ErrorAction SilentlyContinue

Write-Host "Añadiendo dominios de Roblox al archivo hosts..."
$domains = @(
    "roblox.com",
    "www.roblox.com", 
    "api.roblox.com",
    "client.roblox.com",
    "setup.roblox.com",
    "auth.roblox.com",
    "authentication.roblox.com",
    "telemetry.roblox.com",
    "status.roblox.com",
    "eula.roblox.com"
)

$hostsContent = Get-Content -Path $hostsPath
$newEntries = @()

foreach ($domain in $domains) {
    $entry = "127.0.0.1 $domain"
    if ($hostsContent -notcontains $entry) {
        $newEntries += $entry
        Write-Host "Añadido: $entry"
    } else {
        Write-Host "Ya existe: $entry"
    }
}

if ($newEntries.Count -gt 0) {
    $content = $hostsContent + "`n" + ($newEntries -join "`n")
    $content | Out-File -Path $hostsPath -Encoding ASCII -Force
    Write-Host "--- Archivo hosts actualizado ---"
    Write-Host "Se añadieron $($newEntries.Count) entradas de Roblox"
    Write-Host "Se ha creado respaldo en: $backupPath"
} else {
    Write-Host "No se añadieron nuevas entradas (ya existían)."
}

Write-Host "--- Recomendación ---"
Write-Host "Para que surta efecto, reinicia el servicio DNS o reinicia el equipo:"
Write-Host "  ipconfig /flushdns"
Write-Host "O reinicia el equipo para aplicar cambios completos."