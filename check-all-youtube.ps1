$rules = Get-NetFirewallRule -DisplayName 'Block-YouTube-*' | Sort-Object DisplayName
foreach ($r in $rules) {
    Write-Host "=== $($r.DisplayName) ==="
    Write-Host "Enabled: $($r.Enabled)"
    Write-Host "Action: $($r.Action)"
    Write-Host "Direction: $($r.Direction)"
    Write-Host "Profile: $($r.Profile)"
    Write-Host "Priority: $($r.Priority)"
    $r | Get-NetFirewallAddressFilter | Select-Object RemoteAddress
    $r | Get-NetFirewallApplicationFilter | Select-Object Program
    Write-Host ""
}