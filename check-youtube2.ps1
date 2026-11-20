$rules = Get-NetFirewallRule -DisplayName 'Block-YouTube-*' | Where-Object { $_.DisplayName -like '*64-233*' }
foreach ($r in $rules) {
    Write-Host "DisplayName: $($r.DisplayName)"
    Write-Host "Enabled: $($r.Enabled)"
    Write-Host "Action: $($r.Action)"
    Write-Host "Direction: $($r.Direction)"
    Write-Host "Priority: $($r.Priority)"
    Write-Host "Profile: $($r.Profile)"
    Write-Host "---"
    $r | Get-NetFirewallApplicationFilter | Select-Object *
}