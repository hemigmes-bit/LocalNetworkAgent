# ============================================================================
# Voice Control - Integración con Windows Speech Recognition
# ============================================================================
# Control por voz del Local Network Agent usando reconocimiento de voz de Windows
# ============================================================================

param(
    [switch]$EnableDebug = $false,
    [string]$ApiBaseUrl = "http://localhost:8080",
    [string]$ApiTokenPath = "$PSScriptRoot\api-token.json"
)

# ============================================================================
# Configuración
# ============================================================================
$VoiceControlVersion = "1.0.0"
$LogFile = "$PSScriptRoot\network-agent.log"

# Comandos de voz disponibles
$VoiceCommands = @{
    # Escaneo
    "escanear red" = { Invoke-ApiScan }
    "escanea la red" = { Invoke-ApiScan }
    "buscar equipos" = { Invoke-ApiScan }

    # Texto a voz
    "decir" = { Invoke-VoiceSay }
    "decir texto" = { Invoke-VoiceSay }
    "diga" = { Invoke-VoiceSay }
    "diga texto" = { Invoke-VoiceSay }

    # Información de estado
    "estado del servidor" = { Get-ServerStatus }
    "como esta el servidor" = { Get-ServerStatus }
    "estado" = { Get-ServerStatus }

    # Control de energía
    "apagar equipo" = { param($ctx) Stop-RemoteComputerVoice -Context $ctx }
    "apaga el equipo" = { param($ctx) Stop-RemoteComputerVoice -Context $ctx }
    "reiniciar equipo" = { param($ctx) Restart-RemoteComputerVoice -Context $ctx }
    "reinicia el equipo" = { param($ctx) Restart-RemoteComputerVoice -Context $ctx }
    "encender equipo" = { param($ctx) Start-RemoteComputerVoice -Context $ctx }
    "enciende el equipo" = { param($ctx) Start-RemoteComputerVoice -Context $ctx }

    # Información de equipos
    "informacion de" = { param($ctx) Get-ComputerInfoVoice -Context $ctx }
    "info de" = { param($ctx) Get-ComputerInfoVoice -Context $ctx }
    "recursos de" = { param($ctx) Get-ComputerResourcesVoice -Context $ctx }
    "hardware de" = { param($ctx) Get-ComputerHardwareVoice -Context $ctx }

    # Comandos remotos
    "ejecutar comando" = { param($ctx) Execute-RemoteCommandVoice -Context $ctx }
    "ejecuta" = { param($ctx) Execute-RemoteCommandVoice -Context $ctx }

    # Utilidades
    "lista de equipos" = { Get-ComputersList }
    "listar equipos" = { Get-ComputersList }
    "cuantos equipos" = { Get-ComputersCount }
    "logs recientes" = { Get-RecentLogs }
    "ver logs" = { Get-RecentLogs }

    # Ayuda
    "ayuda" = { Show-VoiceHelp }
    "que puedo decir" = { Show-VoiceHelp }
}

# =============================================================================
# Nueva función: Hablar texto personalizado por voz
# =============================================================================
function Invoke-VoiceSay {
    param([string]$Text)
    if (-not $Text -or $Text.Trim() -eq "") {
        # Si no hay texto especificado, pedirlo
        $Text = Read-Host "  ¿Qué texto quieres que diga?"
    }
    if ($Text -and $Text.Trim()) {
        Write-VoiceLog "Sintetizando voz: $Text"
        Speak-Text $Text
        Speak-Text "Texto enviado: $Text"
    }
}

# ============================================================================
# Programa Principal
# ============================================================================

function Start-VoiceControl {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "        VOICE CONTROL - Local Network Agent v$VoiceControlVersion" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "API Base URL: $ApiBaseUrl" -ForegroundColor Yellow
    Write-Host ""

    # Verificar token API
    $token = Get-ApiToken
    if (-not $token) {
        Write-Host "ERROR: No se encontró token API. Inicia el API-Server primero." -ForegroundColor Red
        return
    }

    # Inicializar reconocimiento de voz
    if (Initialize-SpeechRecognition) {
        Write-Host ""
        Write-Host "Escuchando comandos de voz..." -ForegroundColor Green
        Write-Host "Presiona Ctrl+C para salir" -ForegroundColor Yellow
        Write-Host ""

        # Mantener escuchando
        Start-VoiceListening -Timeout -1
    }
}

# Ejecutar si se llama directamente
if ($MyInvocation.MyCommand.CommandType -eq "ExternalScript" -or $MyInvocation.ScriptName) {
    Start-VoiceControl
}
