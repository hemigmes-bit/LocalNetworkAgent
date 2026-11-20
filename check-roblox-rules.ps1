$rules = Get-NetFirewallRule -DisplayName 'Block-Roblox-*' -ErrorAction SilentlyContinue
Write-Host "Total Roblox block rules: $($rules.Count)"
$enabled = $rules | Where-Object { $_.Enabled -eq 'True' }
Write-Host "Enabled: $($enabled.Count)"
$enabled | Select-Object DisplayName, Enabled, Action, Direction | Sort-Object DisplayName | Format-Table -AutoSize