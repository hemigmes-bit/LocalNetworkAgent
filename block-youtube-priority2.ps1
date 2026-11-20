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
$pri = 100
foreach ($range in $youtubeRanges) {
    $safeName = $range.Replace('/', '-').Replace('.', '-')
    $ruleName = "Block-YouTube-$safeName"
    netsh advfirewall firewall delete rule name="$ruleName" 2>$null
    netsh advfirewall firewall add rule name="$ruleName" dir=out action=block remoteip=$range protocol=TCP profile=any priority=$pri description="Block YouTube traffic" enable=yes
    Write-Host "Created: $ruleName priority=$pri"
    $pri++
}