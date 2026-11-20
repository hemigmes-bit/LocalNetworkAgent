$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$backupPath = "$hostsPath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
Copy-Item -Path $hostsPath -Destination $backupPath -Force

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

foreach ($domain in $domains) {
    $entry = "127.0.0.1 $domain"
    if ($hostsContent -notcontains $entry) {
        Add-Content -Path $hostsPath -Value $entry
        Write-Host "Added: $entry"
    } else {
        Write-Host "Already exists: $entry"
    }
}

Write-Host "Backup: $backupPath"
Write-Host "Run: ipconfig /flushdns"