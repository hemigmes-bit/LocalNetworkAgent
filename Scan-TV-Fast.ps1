# Escaneo rápido de red usando System.Net.Sockets
$targetPort = 8001
$timeout = 500  # ms
$foundIPs = @()

Write-Host "Escaneando red 192.168.1.0/24 en puerto $targetPort..."

for ($i = 1; $i -le 254; $i++) {
    $ip = "192.168.1.$i"
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connectTask = $client.ConnectAsync($ip, $targetPort)
        if ($connectTask.Wait($timeout)) {
            if ($client.Connected) {
                Write-Host "TV ENCONTRADA en: $ip"
                $foundIPs += $ip
            }
            $client.Close()
        }
    } catch {
        # Ignorar errores
    }
}

if ($foundIPs.Count -gt 0) {
    Write-Host "`nTV encontrada en: $($foundIPs -join ', ')"
    foreach ($ip in $foundIPs) {
        try {
            $res = Invoke-RestMethod -Uri "http://${ip}:8001/api/v2/" -TimeoutSec 3 -ErrorAction Stop
            Write-Host "Estado: $($res.device.PowerState) - Modelo: $($res.device.model)"
        } catch {
            Write-Host "API no disponible en $ip"
        }
    }
} else {
    Write-Host "`nTV no encontrada en la subred 192.168.1.0/24"
    Write-Host "Posibles causas:"
    Write-Host "1. Cable Ethernet desconectado"
    Write-Host "2. TV en standby profundo"
    Write-Host "3. IP fuera de la subred 192.168.1.x"
}