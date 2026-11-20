$rules = Get-NetFirewallRule -DisplayName 'Block-YouTube-*' | Where-Object { $_.DisplayName -like '*64-233*' }
foreach ($r in $rules) {
    $r | Get-NetFirewallProfile | Select-Object Name, Enabled
}