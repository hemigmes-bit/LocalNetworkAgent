$testIPs = @('64.233.166.136', '142.250.185.46', '172.217.16.206', '216.58.213.14')
foreach ($ip in $testIPs) {
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $result = $socket.BeginConnect($ip, 443, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne(3000)
        if ($success -and $socket.Connected) {
            $socket.Close()
            Write-Host "$ip:443 -> CONECTADO (fallo firewall)"
        } else {
            Write-Host "$ip:443 -> BLOQUEADO"
        }
    } catch {
        Write-Host "$ip:443 -> BLOQUEADO"
    }
}