$youtubeRanges = @(
    '64.233.160.0/19',
    '66.102.0.0/20',
    '66.249.64.0/19',
    '72.14.192.0/18',
    '74.125.0.0/16',
    '172.217.0.0/16',
    '172.253.0.0/16',
    '209.85.128.0/17',
    '216.58.192.0/19',
    '216.239.32.0/19'
)
foreach ($range in $youtubeRanges) {
    $ruleName = 'Block-YouTube-' + $range.Replace('/', '-')
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Outbound -RemoteAddress $range -Action Block -Protocol TCP -Description 'Block YouTube'
        Write-Host "Created: $ruleName"
    } else {
        Write-Host "Exists: $ruleName"
    }
}