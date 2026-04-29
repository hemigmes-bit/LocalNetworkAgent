param([string]$Subnet)
$config = Get-Content "C:\Users\Usuario\LocalNetworkAgent\network-config.json" | ConvertFrom-Json
if (-not $Subnet) { $Subnet = $config.SubnetPrefix }

Write-Host "=== ESCANEO ($Subnet.0/24) ===" -ForegroundColor Cyan

$results = @()
for ($i = 1; $i -le 254; $i++) {
    $ip = "$Subnet.$i"
    $p = New-Object System.Net.NetworkInformation.Ping
    try {
        $r = $p.Send($ip, 150)
        if ($r.Status -eq 'Success') {
            $name = ""
            $desc = "Desconocido"
            $hostname = $ip
            
            try { $hostname = [System.Net.Dns]::GetHostEntry($ip).HostName } catch {}
            if ($hostname -ne $ip) { $name = $hostname }
            
            $isWindows = $false
            $isSSH = $false
            $isWeb = $false
            
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                if ($tcp.ConnectAsync($ip, 445).Wait(50)) { $isWindows = $true; $tcp.Close() }
            } catch {}
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                if ($tcp.ConnectAsync($ip, 22).Wait(50)) { $isSSH = $true; $tcp.Close() }
            } catch {}
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                if ($tcp.ConnectAsync($ip, 80).Wait(50)) { $isWeb = $true; $tcp.Close() }
            } catch {}
            
            if ($ip -match "\.1$") { $desc = "Router" }
            elseif ($name -match "livebox|router|modem|fiber") { $desc = "Router" }
            elseif ($isWindows) { $desc = "Windows" }
            elseif ($isSSH) { $desc = "Linux" }
            elseif ($isWeb) { $desc = "Web" }
            
            $displayName = if ($name) { "$name ($desc)" } else { $desc }
            $results += [PSCustomObject]@{ IP=$ip; Dispositivo=$displayName }
            Write-Host "$ip -> $displayName" -ForegroundColor Green
        }
    } catch {}
    $p.Dispose()
}

$results | Format-Table IP, Dispositivo -AutoSize
Write-Host "Encontrados: $($results.Count) equipos" -ForegroundColor Green