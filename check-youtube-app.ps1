$rule = Get-NetFirewallRule -DisplayName 'Block-YouTube-64-233-160.0-19'
if ($rule) {
    $rule | Get-NetFirewallApplicationFilter | Select-Object *
} else {
    Write-Host "Rule not found: Block-YouTube-64-233-160.0-19"
    # Try the other one
    $rule2 = Get-NetFirewallRule -DisplayName 'Block-YouTube-64-233-160-0-19'
    if ($rule2) {
        $rule2 | Get-NetFirewallApplicationFilter | Select-Object *
    }
}