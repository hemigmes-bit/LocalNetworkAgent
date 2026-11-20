param(
    [int]$PollInterval = 5,
    [string]$AIProvider = "openai",
    [string]$AIModel = "gpt-4o-mini",
    [string]$APIKey = ""
)

$configFile = "$PSScriptRoot\telegram-bot-config.json"
if (Test-Path $configFile) {
    $botConfig = Get-Content $configFile -Raw | ConvertFrom-Json
    $BotToken = $botConfig.BotToken
    $ChatId = $botConfig.ChatId
} else {
    $BotToken = "PEGAR_TOKEN_AQUI"
    $ChatId = "0"
}

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"

# Cargar configuración de IA
$aiConfigFile = "$PSScriptRoot\ai-config.json"
if (Test-Path $aiConfigFile) {
    $aiConfig = Get-Content $aiConfigFile -Raw | ConvertFrom-Json
    if ($aiConfig.APIKey) { $APIKey = $aiConfig.APIKey }
    if ($aiConfig.Provider) { $AIProvider = $aiConfig.Provider }
    if ($aiConfig.Model) { $AIModel = $aiConfig.Model }
}

function Write-BotLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    try { Add-Content "$projectPath\telegram-bot-ia.log" -Value $logEntry -ErrorAction SilentlyContinue } catch {}
}

function Get-TelegramUpdates {
    param([int]$Offset = 0)
    $url = "https://api.telegram.org/bot${BotToken}/getUpdates"
    if ($Offset -gt 0) { $url += "?offset=$Offset&timeout=30" }
    try {
        $response = Invoke-RestMethod -Uri $url -Method Post -TimeoutSec 35
        if ($response.ok -and $response.result) { return $response.result }
    } catch {
        Write-BotLog ("Error fetching updates: $($_.Exception.Message)") "ERROR"
    }
    return @()
}

function Send-TelegramMessage {
    param([string]$Message)
    if (-not $ChatId -or $ChatId -eq "0") { return }
    $url = "https://api.telegram.org/bot${BotToken}/sendMessage"
    $body = @{ chat_id = $ChatId; text = $Message; parse_mode = "HTML" }
    try {
        Invoke-RestMethod -Uri $url -Method Post -Body $body -TimeoutSec 10
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

function Call-AI {
    param([string]$UserMessage, [string]$SystemPrompt = "")
    if ($AIProvider -ne "ollama" -and -not $APIKey) { return "Error: No hay API key configurada" }

    try {
        if ($AIProvider -eq "openai") {
            $url = "https://api.openai.com/v1/chat/completions"
            $headers = @{ Authorization = "Bearer $APIKey"; "Content-Type" = "application/json" }
            $messages = @()
            if ($SystemPrompt) { $messages += @{ role = "system"; content = $SystemPrompt } }
            $messages += @{ role = "user"; content = $UserMessage }
            $body = @{
                model = $AIModel
                messages = $messages
                temperature = 0.7
                max_tokens = 2000
            } | ConvertTo-Json -Depth 5
            $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body -TimeoutSec 60
            return $response.choices[0].message.content.Trim()
        }
        elseif ($AIProvider -eq "anthropic") {
            $url = "https://api.anthropic.com/v1/messages"
            $headers = @{
                "x-api-key" = $APIKey
                "anthropic-version" = "2023-06-01"
                "Content-Type" = "application/json"
            }
            $body = @{
                model = $AIModel
                max_tokens = 2000
                messages = @(@{ role = "user"; content = $UserMessage })
            } | ConvertTo-Json -Depth 5
            $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body -TimeoutSec 60
            return $response.content[0].text.Trim()
        }
        elseif ($AIProvider -eq "ollama") {
            $url = "http://localhost:11434/api/chat"
            $body = @{
                model = $AIModel
                messages = @(@{ role = "user"; content = $UserMessage })
                stream = $false
            } | ConvertTo-Json -Depth 5
            $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -TimeoutSec 120
            return $response.message.content.Trim()
        }
    } catch {
        return "Error IA: $($_.Exception.Message)"
    }
    return "Proveedor no soportado"
}

# --- Main loop ---
Write-BotLog "Iniciando Telegram Bot con IA..." "INFO"

if ($BotToken -eq "PEGAR_TOKEN_AQUI" -or -not $BotToken) {
    Write-BotLog "No se configuro BotToken." "ERROR"
    exit 1
}

if (-not $APIKey) {
    Write-BotLog "No hay API key de IA configurada. Edita ai-config.json" "WARN"
}

if ($ChatId -eq "0" -or -not $ChatId) {
    Write-BotLog "Modo discovery activado. Envia /start al bot." "INFO"
}

$lastUpdateId = 0
Write-BotLog "Bot IA iniciado. Esperando mensajes..." "INFO"

while ($true) {
    $updates = Get-TelegramUpdates -Offset ($lastUpdateId + 1)
    foreach ($update in $updates) {
        $lastUpdateId = $update.update_id
        $message = $update.message
        $text = $message.text
        $chat = $message.chat.id

        Write-BotLog ("Mensaje: $text de $chat") "DEBUG"

        if ($ChatId -eq "0" -or -not $ChatId) {
            Save-ChatId $chat
            Send-TelegramMessage "Bot con IA activado! Escribe lo que quieras. Config: $AIProvider / $AIModel"
            continue
        }

        if ($chat -ne $ChatId) {
            Send-TelegramMessage "Acceso no autorizado"
            continue
        }

        if ($text -eq "/start") {
            Send-TelegramMessage "Bot IA listo. Proveedor: $AIProvider | Modelo: $AIModel`nEscribe cualquier cosa para chatear."
            continue
        }

        if ($text -eq "/config") {
            Send-TelegramMessage "Config actual:`nProveedor: $AIProvider`nModelo: $AIModel`nAPI Key: $(if ($APIKey) { "Configurada" } else { "FALTA" })"
            continue
        }

        if ($text -like "/model *") {
            $newModel = $text.Substring(7).Trim()
            $AIModel = $newModel
            if (Test-Path $aiConfigFile) {
                $aiConfig.Model = $newModel
                $aiConfig | ConvertTo-Json -Depth 3 | Set-Content $aiConfigFile -Encoding UTF8
            }
            Send-TelegramMessage "Modelo cambiado a: $AIModel"
            continue
        }

        # Enviar a IA
        Send-TelegramMessage "Pensando..."
        $aiResponse = Call-AI -UserMessage $text -SystemPrompt "Eres un asistente útil que controla una red local. Responde en español."
        Send-TelegramMessage $aiResponse
    }
    Start-Sleep -Seconds $PollInterval
}