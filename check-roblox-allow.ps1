$rules = Get-NetFirewallRule -Action Allow -Direction Outbound
foreach ($r in $rules) {
    if ($r.DisplayName -like '*Roblox*' -or $r.DisplayName -like '*roblox*') {
        Write-Host "ALLOW ROBLOX RULE FOUND:"
        Write-Host "  DisplayName: $($r.DisplayName)"
        Write-Host "  Enabled: $($r.Enabled)"
        Write-Host "  Action: $($r.Action)"
        Write-Host "  Direction: $($r.Direction)"
        Write-Host "  Profile: $($r.Profile)"
        Write-Host "  Priority: $($r.Priority)"
    }
}