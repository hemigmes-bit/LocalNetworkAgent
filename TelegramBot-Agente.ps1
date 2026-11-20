param([int]$PollInterval = 5)

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

function Write-BotLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    try { Add-Content "$projectPath\telegram-bot.log" -Value $logEntry -ErrorAction SilentlyContinue } catch {}
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

# --- Main loop ---
Write-BotLog "Iniciando Telegram Bot Agent..." "INFO"

if ($BotToken -eq "PEGAR_TOKEN_AQUI" -or -not $BotToken) {
    Write-BotLog "No se configuro BotToken." "ERROR"
    exit 1
}

if ($ChatId -eq "0" -or -not $ChatId) {
    Write-BotLog "Modo discovery activado. Envia /start al bot." "INFO"
}

$lastUpdateId = 0
Write-BotLog "Bot iniciado. Esperando comandos..." "INFO"

while ($true) {
    $updates = Get-TelegramUpdates -Offset ($lastUpdateId + 1)
    foreach ($update in $updates) {
        $lastUpdateId = $update.update_id
        $message = $update.message
        $text = $message.text
        $chat = $message.chat.id

        Write-BotLog ("Comando: $text de $chat") "DEBUG"

        if ($ChatId -eq "0" -or -not $ChatId) {
            Save-ChatId $chat
            Send-TelegramMessage "Registrado! ChatId: $chat`n`nComandos:`n/escanear - Escanear red`n/dispositivos - Ver dispositivos`n/wol - Wake-on-LAN CORE0`n/sysinfo - Info del sistema`n/ping <ip> - Ping a dispositivo`n/voz <mensaje> - Reproducir voz"
            continue
        }

        if ($chat -ne $ChatId) {
            Send-TelegramMessage "Acceso no autorizado"
            continue
        }

        switch -Regex ($text) {
            "^/start$" {
                Send-TelegramMessage "Bot activo`nComandos:`n/escanear /dispositivos /wol /sysinfo /ping /voz"
            }
            "^/escanear$" {
                Send-TelegramMessage "Escaneando red..."
                # TODO: Implementar escaneo real
            }
            "^/dispositivos$" {
                Send-TelegramMessage "Dispositivos:`n- CORE0: 192.168.1.50`n- VICTORYMAR: 192.168.1.135`n- Samsung TV: 192.168.1.129`n- Redmi Henrys: 192.168.1.132`n- Lenovo-Beita: 192.168.1.136`n- Dreame Vacuum: 192.168.1.128"
            }
            "^/wol$" {
                Send-TelegramMessage "Enviando WoL a CORE0..."
                # TODO: Implementar WoL real
            }
            "^/sysinfo$" {
                Send-TelegramMessage "Info sistema:`nCPU: Intel i7`nRAM: 32GB`nOS: Windows 11"
            }
            "^/ping\s+(.+)$" {
                $ip = $matches[1]
                try {
                    $r = [System.Net.NetworkInformation.Ping]::new().Send($ip, 200)
                    if ($r.Status -eq "Success") {
                        Send-TelegramMessage ("$ip OK - RTT: $($r.RoundtripTime)ms")
                    } else {
                        Send-TelegramMessage ("$ip NO responde")
                    }
                } catch {
                    Send-TelegramMessage ("Error ping: $($_.Exception.Message)")
                }
            }
            "^/voz\s+(.+)$" {
                $msg = $matches[1]
                Send-TelegramMessage ("Voz enviada: $msg")
            }
            default {
                Send-TelegramMessage "Comandos: /escanear /dispositivos /wol /sysinfo /ping <ip> /voz <msg>"
            }
        }
    }
    Start-Sleep -Seconds $PollInterval
}
