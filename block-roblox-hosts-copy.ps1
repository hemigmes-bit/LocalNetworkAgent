$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$tempPath = "$env:TEMP\hosts.tmp"
$backupPath = "$hostsPath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"

# Backup
Copy-Item -Path $hostsPath -Destination $backupPath -Force

# Copy to temp, modify, copy back
Copy-Item -Path $hostsPath -Destination $tempPath -Force

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

$content = Get-Content -Path $tempPath

foreach ($domain in $domains) {
    $entry = "127.0.0.1 $domain"
    if ($content -notcontains $entry) {
        $content += "`n$entry"
        Write-Host "Will add: $entry"
    } else {
        Write-Host "Already exists: $entry"
    }
}

Set-Content -Path $tempPath -Value $content -Encoding ASCII -Force

# Now copy back (this needs admin)
Write-Host "Copying back to $hostsPath (requires admin)..."
Copy-Item -Path $tempPath -Destination $hostsPath -Force

Write-Host "Backup: $backupPath"
Write-Host "Done. Run: ipconfig /flushdns"