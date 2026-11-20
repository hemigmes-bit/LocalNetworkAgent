param(
    [string]$MAC = "04:E4:B6:CF:89:38",
    [string]$Key = "KEY_POWER"
)

# Función para encontrar IP por MAC
function Find-TV-IP {
    param([string]$TargetMAC)
    $macSearch = $TargetMAC -replace ':', '-'
    $macSearch2 = $TargetMAC -replace '-', ':'
    
    # Método 1: ARP table
    try {
        $arpResult = arp -a
        $lines = $arpResult -split "`n"
        foreach ($line in $lines) {
            if ($line -like "*$macSearch*" -or $line -like "*$macSearch2*") {
                $parts = $line -split '\s+'
                foreach ($part in $parts) {
                    if ($part -match '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}') {
                        return $part
                    }
                }
            }
        }
    } catch { }
    
    # Método 2: Get-NetNeighbor
    try {
        $neighbors = Get-NetNeighbor -ErrorAction SilentlyContinue
        foreach ($n in $neighbors) {
            if ($n.LinkAddress -eq $TargetMAC -or $n.LinkAddress -eq $macSearch) {
                return $n.IPAddress
            }
        }
    } catch { }
    
    # Método 3: Ping sweep + check MAC via ARP refresh
    Write-Host "Escaneando red para encontrar TV..."
    for ($i = 1; $i -le 254; $i++) {
        $ip = "192.168.1.$i"
        $ping = Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 1 -ErrorAction SilentlyContinue
        if ($ping) {
            Start-Sleep -Milliseconds 50
            $arpRefresh = arp -a
            $lines = $arpRefresh -split "`n"
            foreach ($line in $lines) {
                if ($line -like "*$macSearch*" -or $line -like "*$macSearch2*") {
                    $parts = $line -split '\s+'
                    foreach ($part in $parts) {
                        if ($part -match '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}') {
                            return $part
                        }
                    }
                }
            }
        }
    }
    
    return $null
}

$IP = Find-TV-IP -TargetMAC $MAC
if (-not $IP) {
    Write-Warning "No se pudo encontrar la TV ($MAC) en la red"
    exit 1
}

Write-Host "TV encontrada en $IP"

$appName = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("LocalNetworkAgent"))
$url1 = "ws://" + $IP + ":8001/api/v2/channels/samsung.remote.control?name=" + $appName
$url2 = "wss://" + $IP + ":8002/api/v2/channels/samsung.remote.control?name=" + $appName
$endpoints = @($url1, $url2)

$payload = @{
    method = "ms.remote.control"
    params = @{
        Cmd = "Click"
        DataOfCmd = $Key
        Option = "false"
        TypeOfRemote = "SendRemoteKey"
    }
} | ConvertTo-Json -Compress

$sent = $false

foreach ($urlStr in $endpoints) {
    if ($sent) { break }
    try {
        $ws = [System.Net.WebSockets.ClientWebSocket]::new()
        if ($urlStr.StartsWith("wss://")) {
            $ws.Options.RemoteCertificateValidationCallback = { $true }
        }
        $cts = [System.Threading.CancellationTokenSource]::new(4000)
        $ws.ConnectAsync([Uri]$urlStr, $cts.Token).Wait()
        
        if ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
            $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
            $segment = [ArraySegment[byte]]::new($bytes)
            $ws.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token).Wait()
            Start-Sleep -Milliseconds 500
            $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $cts.Token).Wait()
            Write-Host "Comando $Key enviado exitosamente via $urlStr"
            $sent = $true
        }
        $ws.Dispose()
    } catch {
        Write-Host "Error en $urlStr : $($_.Exception.Message)"
    }
}

if (-not $sent) {
    Write-Warning "No se pudo conectar a la TV en $IP"
    exit 1
}