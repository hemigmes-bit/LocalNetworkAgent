$rules = Get-NetFirewallRule -DisplayName 'Block-YouTube-*' | Sort-Object DisplayName
Write-Host "Total YouTube block rules: $($rules.Count)"
Write-Host ""
foreach ($r in $rules) {
    $appFilter = $r | Get-NetFirewallApplicationFilter
    Write-Host "$($r.DisplayName) | Enabled: $($r.Enabled) | Action: $($r.Action) | Dir: $($r.Direction) | Profile: $($r.Profile) | App: $($appFilter.Program)"
}