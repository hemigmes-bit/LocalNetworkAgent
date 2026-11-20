$ws = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationTokenSource(5000)
$appName = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('LocalNetworkAgent'))
$urlString = 'ws://192.168.1.129:8001/api/v2/channels/samsung.remote.control?name=' + $appName
$url = [Uri]$urlString
try {
    $ws.ConnectAsync($url, $cts.Token).Wait()
    Write-Host "Connected: $($ws.State)"
    if ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $payload = @{
            method = 'ms.remote.control'
            params = @{
                Cmd = 'Click'
                DataOfCmd = 'KEY_POWEROFF'
                Option = 'false'
                TypeOfRemote = 'SendRemoteKey'
            }
        } | ConvertTo-Json -Compress
        $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
        $segment = [ArraySegment[byte]]::new($bytes)
        $ws.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token).Wait()
        Start-Sleep -Milliseconds 300
        $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, 'Done', $cts.Token).Wait()
        Write-Host "Comando enviado"
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}