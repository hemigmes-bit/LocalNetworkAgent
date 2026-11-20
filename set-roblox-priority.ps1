$robloxRanges = @(
    '128.116.0.0/17',
    '103.140.28.0/23',
    '141.193.3.0/24',
    '204.9.184.0/24',
    '205.201.62.0/24',
    '204.13.168.0/21',
    '209.206.40.0/21',
    '23.173.192.0/24',
    '64.125.149.0/24',
    '208.185.116.0/25',
    '208.185.166.232/29',
    '208.185.166.240/29',
    '208.185.173.0/24',
    '216.200.230.0/24',
    '107.180.192.0/19'
)
$pri = 100
foreach ($range in $robloxRanges) {
    $safeName = $range.Replace('/', '-').Replace('.', '-')
    $ruleName = "Block-Roblox-$safeName"
    netsh advfirewall firewall delete rule name="$ruleName" 2>$null
    netsh advfirewall firewall add rule name="$ruleName" dir=out action=block remoteip=$range protocol=TCP profile=any priority=$pri description="Block Roblox traffic" enable=yes
    Write-Host "Created: $ruleName priority=$pri"
    $pri++
}