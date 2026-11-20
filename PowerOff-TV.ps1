param([string]$IP = "192.168.1.131")

$appName = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("LocalNetworkAgent"))
$urlString = "ws://$IP:8001/api/v2/channels/samsung.remote.control?name=$appName"
$url = [Uri]$urlString

$ws = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationTokenSource(10000)

try {
    $ws.ConnectAsync($url, $cts.Token).Wait()
    Write-Host "Conectado: $($ws.State)"

    if ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        # Enviar KEY_POWER
        $payload = @{
            method = "ms.remote.control"
            params = @{
                Cmd = "Click"
                DataOfCmd = "KEY_POWER"
                Option = "false"
                TypeOfRemote = "SendRemoteKey"
            }
        } | ConvertTo-Json -Compress

        $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
        $segment = [ArraySegment[byte]]::new($bytes)
        $ws.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token).Wait()
        Write-Host "KEY_POWER enviado"

        # Esperar respuesta
        Start-Sleep -Seconds 2

        # Recibir respuesta
        $buffer = New-Object byte[4096]
        $offset = 0
        $response = ""
        try {
            $result = $ws.ReceiveAsync([ArraySegment[byte]]::new($buffer), $cts.Token)
            if ($result.Wait(3000)) {
                $response = [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Result.Count)
                Write-Host "Respuesta: $response"
            }
        } catch {
            Write-Host "Sin respuesta del WebSocket"
        }

        $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $cts.Token).Wait()
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)"
} finally {
    $ws.Dispose()
}

# Verificar estado
Start-Sleep -Seconds 3
try {
    $res = Invoke-RestMethod -Uri "http://$IP:8001/api/v2/" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "Estado final: $($res.device.PowerState)"
} catch {
    Write-Host "No se puede verificar el estado"
}