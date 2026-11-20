$tvMac = "04:E4:B6:CF:89:38"
$tvMac2 = $tvMac -replace ':', '-'

# 1. Buscar en ARP de todas las interfaces
Write-Host "Buscando en ARP..."
$arpResult = arp -a
$lines = $arpResult -split "`n"
$foundIP = $null
foreach ($line in $lines) {
    if ($line -like "*$tvMac*" -or $line -like "*$tvMac2*") {
        $parts = $line -split '\s+'
        foreach ($part in $parts) {
            if ($part -match '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}') {
                $foundIP = $part
                Write-Host "TV encontrada en ARP: $foundIP"
                break
            }
        }
        if ($foundIP) { break }
    }
}

if (-not $foundIP) {
    Write-Host "TV no encontrada en ARP. Escaneando red 192.168.1.0/24..."
    $foundIPs = @()
    for ($i = 1; $i -le 254; $i++) {
        $ip = "192.168.1.$i"
        $tcp = Test-NetConnection -ComputerName $ip -Port 8001 -InformationLevel Quiet -TimeoutSeconds 1 -ErrorAction SilentlyContinue
        if ($tcp.TcpTestSucceeded) {
            Write-Host "TV encontrada en: $ip (puerto 8001)"
            $foundIPs += $ip
            break
        }
    }
    if ($foundIPs.Count -gt 0) {
        $foundIP = $foundIPs[0]
    }
}

if ($foundIP) {
    Write-Host "Verificando TV en $foundIP..."
    try {
        $res = Invoke-RestMethod -Uri "http://${foundIP}:8001/api/v2/" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "TV activa - Modelo: $($res.device.model) - Estado: $($res.device.PowerState)"
    } catch {
        Write-Host "TV responde en $foundIP pero API no disponible"
    }
} else {
    Write-Host "TV no encontrada en la red 192.168.1.0/24"
    Write-Host "La TV puede estar en standby profundo o en otra subred"
}