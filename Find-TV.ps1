$tvMac = "04:E4:B6:CF:89:38"
$tvMac2 = $tvMac -replace ':', '-'

Write-Host "Buscando TV en la red..."

# Buscar por ARP
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
    Write-Host "TV no encontrada en ARP. Buscando por escaneo de red..."
    # Buscar por ping masivo
    for ($i = 1; $i -le 254; $i++) {
        $ip = "192.168.1.$i"
        $ping = Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 1
        if ($ping) {
            Write-Host "Host activo: $ip"
        }
    }
} else {
    # Verificar puerto 8001
    $tcp = Test-NetConnection -ComputerName $foundIP -Port 8001 -InformationLevel Quiet -TimeoutSeconds 2
    if ($tcp) {
        Write-Host "Puerto 8001 abierto en $foundIP - TV activa"
    } else {
        Write-Host "Puerto 8001 cerrado en $foundIP - TV en standby"
    }
}