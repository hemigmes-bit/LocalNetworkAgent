# Wake-on-LAN para CORE0
# Usa la MAC address del network-config.json

$mac = "5C:85:7E:41:80:2B"
$broadcast = "192.168.1.255"

Write-Host "Enviando magic packet a CORE0 ($mac)..." -ForegroundColor Yellow

# Convertir MAC a bytes
$macBytes = $mac -split ":" | ForEach-Object { [byte]::Parse($_, [System.Globalization.NumberStyles]) }

# Construir magic packet: 6 bytes de FF + 16 veces la MAC
$packet = New-Object byte[] 102
for ($i = 0; $i -lt 6; $i++) { $packet[$i] = 0xFF }
for ($i = 0; $i -lt 16; $i++) {
    for ($j = 0; $j -lt 6; $j++) {
        $packet[6 + $i * 6 + $j] = $macBytes[$j]
    }
}

# Enviar por UDP
$udp = New-Object System.Net.Sockets.UdpClient
$udp.EnableBroadcast = $true
$udp.Send($packet, $packet.Length, $broadcast, 4000)
$udp.Close()

Write-Host "Magic packet enviado." -ForegroundColor Green
Write-Host "Esperando 5 segundos..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Verificar si respondió (IP desde config)
$configPath = Join-Path $PSScriptRoot "network-config.json"
$core0Ip = "192.168.1.50"
if (Test-Path $configPath) {
    $cfg = Get-Content $configPath -Raw | ConvertFrom-Json
    $core0 = $cfg.Computers | Where-Object { $_.Name -eq "CORE0" } | Select-Object -First 1
    if ($core0 -and $core0.IP) { $core0Ip = $core0.IP }
}
$online = Test-Connection -ComputerName $core0Ip -Count 1 -Quiet
if ($online) {
    Write-Host "CORE0 está ONLINE!" -ForegroundColor Green
} else {
    Write-Host "CORE0 no responde aún. Verifica que:" -ForegroundColor Yellow
    Write-Host "  - El cable Ethernet está conectado" -ForegroundColor Yellow
    Write-Host "  - WoL está habilitado en BIOS/UEFI" -ForegroundColor Yellow
    Write-Host "  - El adaptador tiene alimentación" -ForegroundColor Yellow
}