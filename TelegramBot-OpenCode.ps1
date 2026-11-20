param([int]$PollInterval = 2)

$configFile = "$PSScriptRoot\telegram-bot-config.json"
if (Test-Path $configFile) {
    $botConfig = Get-Content $configFile -Raw | ConvertFrom-Json
    $BotToken = $botConfig.BotToken
    $ChatId = $botConfig.ChatId
    $SessionId = $botConfig.SessionId
    $OpenCodePassword = $botConfig.OpenCodePassword
} else {
    exit 1
}

if (-not $OpenCodePassword) { $OpenCodePassword = "RedAgent2026!" }
$OpenCodeUrl = "http://127.0.0.1:4096"
$projectPath = "C:\Users\Usuario\LocalNetworkAgent"

$ModelProvider = if ($botConfig.ModelProvider) { $botConfig.ModelProvider } else { "deepseek" }
$ModelId = if ($botConfig.ModelId) { $botConfig.ModelId } else { "deepseek-flash" }

function Write-BotLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    try { [IO.File]::AppendAllText("$projectPath\telegram-bot-ia.log", $logEntry + "`r`n", (New-Object Text.UTF8Encoding($true))) } catch {}
}

function ConvertFrom-Utf8Response {
    param($Response)
    $json = [Text.Encoding]::UTF8.GetString($Response.RawContentStream.ToArray())
    return ($json | ConvertFrom-Json)
}

function Get-OCHeaders {
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("opencode:$OpenCodePassword"))
    return @{ "Authorization" = "Basic $auth"; "Content-Type" = "application/json" }
}

function Test-OpenCodeServer {
    try {
        $r = Invoke-RestMethod -Uri "$OpenCodeUrl/session" -Headers (Get-OCHeaders) -TimeoutSec 5
        return $true
    } catch { return $false }
}

function Connect-OpenCodeSession {
    if ($SessionId) {
        try {
            $null = Invoke-RestMethod -Uri "$OpenCodeUrl/session/$SessionId" -Headers (Get-OCHeaders) -TimeoutSec 10
            Write-BotLog "Sesión existente reutilizada: $SessionId" "INFO"
            return $SessionId
        } catch {
            Write-BotLog "Sesión anterior no válida, creando nueva" "WARN"
        }
    }
    $session = Invoke-RestMethod -Uri "$OpenCodeUrl/session" -Method Post -Headers (Get-OCHeaders) -Body (@{ title = "Telegram - Red Local" } | ConvertTo-Json) -TimeoutSec 15
    $botConfig.SessionId = $session.id
    $botConfig | ConvertTo-Json -Depth 3 | Set-Content $configFile -Encoding UTF8
    Write-BotLog "Nueva sesión creada: $($session.id)" "INFO"
    return $session.id
}

function Send-ToAgent {
    param([string]$Message)
    $headers = Get-OCHeaders
    $body = @{
        parts = @(@{ type = "text"; text = $Message })
        model = @{ providerID = $ModelProvider; modelID = $ModelId }
    } | ConvertTo-Json -Depth 5
    $bodyBytes = [Text.Encoding]::UTF8.GetBytes($body)
    $wr = Invoke-WebRequest -Uri "$OpenCodeUrl/session/$SessionId/message" -Method Post -Headers $headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec 900
    $response = ConvertFrom-Utf8Response $wr
    $textParts = $response.parts | Where-Object { $_.type -eq "text" } | ForEach-Object { $_.text }
    $result = ($textParts -join "`n").Trim()
    if (-not $result) { $result = "(sin respuesta de texto)" }
    return $result
}

function Get-TelegramUpdates {
    param([int]$Offset = 0)
    $url = "https://api.telegram.org/bot${BotToken}/getUpdates"
    if ($Offset -gt 0) { $url += "?offset=$Offset&timeout=20" }
    try {
        $wr = Invoke-WebRequest -Uri $url -Method Post -UseBasicParsing -TimeoutSec 30
        $response = ConvertFrom-Utf8Response $wr
        if ($response.ok -and $response.result) { return $response.result }
    } catch {
        Write-BotLog ("Error fetching updates: $($_.Exception.Message)") "WARN"
    }
    return @()
}

function Send-TelegramMessage {
    param([string]$Message)
    if (-not $ChatId -or $ChatId -eq "0") { return }
    $url = "https://api.telegram.org/bot${BotToken}/sendMessage"
    if ($Message.Length -gt 4000) { $Message = $Message.Substring(0, 4000) + "`n...(truncado)" }
    $payload = @{ chat_id = $ChatId; text = $Message; disable_web_page_preview = $true } | ConvertTo-Json -Compress
    $bodyBytes = [Text.Encoding]::UTF8.GetBytes($payload)
    try {
        Invoke-RestMethod -Uri $url -Method Post -Body $bodyBytes -ContentType "application/json; charset=utf-8" -TimeoutSec 15
    } catch {
        Write-BotLog ("Error sending message: $($_.Exception.Message)") "ERROR"
    }
}

function Save-ChatId {
    param([string]$NewChatId)
    $botConfig.ChatId = $NewChatId
    $botConfig | ConvertTo-Json -Depth 3 | Set-Content $configFile -Encoding UTF8
    $ChatId = $NewChatId
    Write-BotLog ("ChatId guardado: $NewChatId") "INFO"
}

# --- Main ---
Write-BotLog "Iniciando puente Telegram <-> OpenCode Agent..." "INFO"

if (-not (Test-OpenCodeServer)) {
    Write-BotLog "OpenCode server no responde en $OpenCodeUrl" "ERROR"
    Send-TelegramMessage "ERROR: El servidor OpenCode no está activo. Inicia: opencode serve"
    exit 1
}

$SessionId = Connect-OpenCodeSession
$lastUpdateId = 0
try {
    $tailWr = Invoke-WebRequest -Uri ("https://api.telegram.org/bot${BotToken}/getUpdates?offset=-1") -UseBasicParsing -TimeoutSec 15
    $tailObj = ConvertFrom-Utf8Response $tailWr
    if ($tailObj.ok -and $tailObj.result) { $lastUpdateId = [int64](($tailObj.result | Select-Object -Last 1).update_id) }
} catch { Write-BotLog "No se pudo leer el offset inicial: $($_.Exception.Message)" "WARN" }
Write-BotLog "Offset inicial: $lastUpdateId (no se reprocesan mensajes previos al reinicio)" "INFO"
Write-BotLog "Puente activo. Sesión: $SessionId" "INFO"

while ($true) {
    try {
        $updates = Get-TelegramUpdates -Offset ($lastUpdateId + 1)
        if ($updates.Count -gt 0) {
            $maxId = ($updates | Measure-Object -Property update_id -Maximum).Maximum
            $lastUpdateId = $maxId
            try {
                $confirmUrl = "https://api.telegram.org/bot${BotToken}/getUpdates?offset=$($maxId + 1)&limit=1&timeout=0"
                $null = Invoke-RestMethod -Uri $confirmUrl -Method Post -TimeoutSec 15
            } catch {
                Write-BotLog ("Error confirmando updates: $($_.Exception.Message)") "WARN"
            }
        }
        foreach ($update in $updates) {
            $lastUpdateId = $update.update_id
            $message = $update.message
            if (-not $message -or -not $message.text) { continue }
            $text = $message.text
            $chat = $message.chat.id

            Write-BotLog ("Mensaje: $text de $chat") "DEBUG"

            if ($ChatId -eq "0" -or -not $ChatId) {
                Save-ChatId $chat
                Send-TelegramMessage "Conectado al agente OpenCode. Escribe cualquier cosa para gestionar tu red."
                continue
            }

            if ($chat -ne $ChatId) {
                Send-TelegramMessage "Acceso no autorizado"
                continue
            }

            if ($text -eq "/start") {
                Send-TelegramMessage "Agente OpenCode conectado.`n`nPuedes pedirme cualquier cosa sobre tu red:`n- Escanear dispositivos`n- Encender CORE0 (WoL)`n- Hacer ping`n- Ejecutar comandos`n- Modificar configuracion`n`nComandos: /reset (nueva conversacion) /status"
                continue
            }

            if ($text -eq "/reset") {
                $botConfig.SessionId = $null
                $botConfig | ConvertTo-Json -Depth 3 | Set-Content $configFile -Encoding UTF8
                $SessionId = Connect-OpenCodeSession
                Send-TelegramMessage "Nueva sesion iniciada."
                continue
            }

            if ($text -eq "/status") {
                $ok = Test-OpenCodeServer
                Send-TelegramMessage "Servidor OpenCode: $(if ($ok) { 'OK' } else { 'CAIDO' })`nSesion: $SessionId"
                continue
            }

            # Guardia: bloquear apagado/reinicio de VICTORYMAR (maquina local que ejecuta el bot)
            $shutdownIntent = ($text -match '(?i)(apag|shutdown|reinici|restart|stop-computer|suspend)') -and ($text -match '(?i)(victorymar|victoria mar|m[aá]quina|ordenador|computador|\bpc\b|equipo|servidor|sistema|local)')
            $confirmPhrase = $text -match 'CONFIRMO APAGAR VICTORYMAR'
            $isQuestionOrNegation = ($text -match '\?') -or ($text -match '(?i)(por ?qu[eé]|porque|has apagado|apagaste|quieres|deja de|dejar de|no apag|no reinic|no quiero)')
            if ($shutdownIntent -and -not $confirmPhrase -and -not $isQuestionOrNegation) {
                Write-BotLog "BLOQUEADO intento de apagado/reinicio de VICTORYMAR: $text" "WARN"
                Send-TelegramMessage "BLOQUEADO: no apago ni reinicio VICTORYMAR, porque es la maquina que ejecuta este bot y el servidor de Telegram (si se apaga, pierdes el control remoto). Si de verdad quieres apagarla, envia exactamente: CONFIRMO APAGAR VICTORYMAR"
                continue
            }

            Send-TelegramMessage "Procesando..."
            try {
                $response = Send-ToAgent -Message $text
                Send-TelegramMessage $response
            } catch {
                Write-BotLog ("Error agente: $($_.Exception.Message)") "ERROR"
                Send-TelegramMessage "Error del agente: $($_.Exception.Message)"
            }
        }
    } catch {
        Write-BotLog ("Error loop: $($_.Exception.Message)") "ERROR"
        Start-Sleep -Seconds 5
    }
    Start-Sleep -Seconds $PollInterval
}