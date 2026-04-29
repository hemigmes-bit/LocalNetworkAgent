# =============================================================================
# Voice Control - Integración con Windows Speech Recognition
# =============================================================================
# Control por voz del Local Network Agent usando reconocimiento de voz de Windows
# =============================================================================

param(
    [switch]$EnableDebug = $false,
    [string]$ApiBaseUrl = "http://localhost:8080",
    [string]$ApiTokenPath = "$PSScriptRoot\api-token.json"
)

# =============================================================================
# Configuración
# =============================================================================
$VoiceControlVersion = "1.0.0"
$LogFile = "$PSScriptRoot\network-agent.log"

# Comandos de voz disponibles
$VoiceCommands = @{
    # Escaneo
    "escanear red" = { Invoke-ApiScan }
    "escanea la red" = { Invoke-ApiScan }
    "buscar equipos" = { Invoke-ApiScan }

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
    "comandos disponibles" = { Show-VoiceHelp }
}

# =============================================================================
# Funciones de Logging y Utilidad
# =============================================================================

function Write-VoiceLog {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [VOICE] [$Level] $Message"
    try {
        Add-Content $LogFile -Value $logEntry -ErrorAction SilentlyContinue
    } catch {}

    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "Cyan" }
    }
    Write-Host $logEntry -ForegroundColor $color
}

function Get-ApiToken {
    param([string]$Path = $ApiTokenPath)
    if (Test-Path $Path) {
        $config = Get-Content $Path -Raw | ConvertFrom-Json
        return $config.Token
    }
    return $null
}

function Invoke-ApiRequest {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [object]$Body = $null
    )

    $token = Get-ApiToken
    $url = "$ApiBaseUrl$Endpoint"

    $headers = @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
    }

    try {
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $headers
            UseBasicParsing = $true
        }

        if ($Body) {
            $params.Body = $Body | ConvertTo-Json
        }

        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        Write-VoiceLog "Error en API request ($Method $Endpoint): $_" "ERROR"
        return $null
    }
}

function Speak-Text {
    param([string]$Text, [int]$Rate = 0, [int]$Volume = 100)

    try {
        $synth = New-Object -ComObject SAPI.SpVoice
        $synth.Rate = $Rate
        $synth.Volume = $Volume
        $synth.Speak($Text)

        # Liberar COM
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($synth) | Out-Null
    }
    catch {
        Write-VoiceLog "Error en síntesis de voz: $_" "ERROR"
        Write-Host "  [VOICE] $Text" -ForegroundColor Yellow
    }
}

# =============================================================================
# Funciones de Reconocimiento de Voz
# =============================================================================

function Initialize-SpeechRecognition {
    Write-VoiceLog "Iniciando reconocimiento de voz de Windows..."

    try {
        # Crear objetos SAPI
        $script:SpeechRecognizer = New-Object -ComObject SAPI.SpSharedRecognizer
        $script:SpeechContext = $script:SpeechRecognizer.CreateRecoContext()

        # Crear gramática
        $grammar = $script:SpeechContext.CreateGrammar()

        # Construir lista de comandos
        $commands = @()
        foreach ($cmd in $VoiceCommands.Keys) {
            $commands += $cmd
        }

        # Crear reglas de gramática dinámicas
        $rule = $grammar.Rules.Add("Comandos", 0, 1)

        foreach ($cmd in $commands) {
            $rule.InitialState.AddWordTransition($null, $cmd)
            $rule.AddRule($cmdRule)
        }

        $grammar.Rules.Commit(); $grammar.Rules.Item("Comandos").State = 1  # Activa
        $grammar.CmdLoad()

        # Configurar evento de reconocimiento
        Register-ObjectEvent -InputObject $script:SpeechContext -EventName Recognition -Action {
            $result = $Event.SourceEventArgs.Result
            $recognizedText = $result.PhraseInfo.GetText(0)

            Write-VoiceLog "Comando reconocido: '$recognizedText'" "SUCCESS"
            Speak-Text "Procesando: $recognizedText"

            # Ejecutar comando
            Invoke-VoiceCommand -CommandText $recognizedText
        } | Out-Null

        # Iniciar reconocimiento
        $script:SpeechRecognizer.AudioInput = $null  # Usar micrófono por defecto

        Write-VoiceLog "Reconocimiento de voz iniciado correctamente" "SUCCESS"
        Speak-Text "Control por voz activado. Di 'ayuda' para ver los comandos disponibles."

        return $true
    }
    catch {
        Write-VoiceLog "Error inicializando reconocimiento de voz: $_" "ERROR"
        Write-Host "  No se pudo iniciar el reconocimiento de voz. Verifica que Windows Speech Recognition esté instalado." -ForegroundColor Red
        return $false
    }
}

function Start-VoiceListening {
    param([int]$Timeout = -1)

    if (-not $script:SpeechRecognizer) {
        Write-VoiceLog "El reconocimiento de voz no está inicializado" "ERROR"
        return
    }

    try {
        $script:SpeechRecognizer.SetRecoState(1)  # SRStateListening

        if ($Timeout -gt 0) {
            Start-Sleep -Seconds $Timeout
            $script:SpeechRecognizer.SetRecoState(0)  # SRStateInactive
        }
    }
    catch {
        Write-VoiceLog "Error en escucha de voz: $_" "ERROR"
    }
}

function Stop-VoiceListening {
    if ($script:SpeechRecognizer) {
        try {
            $script:SpeechRecognizer.SetRecoState(0)  # SRStateInactive
            Write-VoiceLog "Reconocimiento de voz detenido"
        }
        catch {
            Write-VoiceLog "Error deteniendo reconocimiento: $_" "ERROR"
        }
    }
}

# =============================================================================
# Ejecución de Comandos de Voz
# =============================================================================

function Invoke-VoiceCommand {
    param([string]$CommandText)

    $commandText = $CommandText.ToLower().Trim()

    # Buscar comando exacto o parcial
    $matchedCommand = $null
    $matchedKey = $null

    foreach ($key in $VoiceCommands.Keys) {
        if ($commandText -eq $key) {
            $matchedCommand = $VoiceCommands[$key]
            $matchedKey = $key
            break
        }
        elseif ($commandText -like "*$key*") {
            $matchedCommand = $VoiceCommands[$key]
            $matchedKey = $key
        }
    }

    if ($matchedCommand) {
        Write-VoiceLog "Ejecutando comando: $matchedKey"

        try {
            $context = @{
                OriginalText = $CommandText
                MatchedPattern = $matchedKey
            }

            & $matchedCommand -Context $context
        }
        catch {
            Write-VoiceLog "Error ejecutando comando: $_" "ERROR"
            Speak-Text "Error al ejecutar el comando"
        }
    }
    else {
        Write-VoiceLog "Comando no reconocido: $commandText" "WARN"
        Speak-Text "Comando no reconocido. Di ayuda para ver los comandos disponibles."
    }
}

# =============================================================================
# Implementación de Comandos de Voz
# =============================================================================

function Invoke-ApiScan {
    Write-VoiceLog "Iniciando escaneo de red..."
    Speak-Text "Escaneando la red en busca de equipos"

    $result = Invoke-ApiRequest -Endpoint "/api/scan" -Method "POST"

    if ($result -and $result.data) {
        $count = $result.data.count
        Write-VoiceLog "Escaneo completado: $count equipos encontrados" "SUCCESS"
        Speak-Text "Escaneo completado. Se encontraron $count equipos en la red."
    }
    else {
        Speak-Text "Error al escanear la red"
    }
}

function Get-ServerStatus {
    $result = Invoke-ApiRequest -Endpoint "/api/status"

    if ($result -and $result.data) {
        $status = $result.data.status
        $version = $result.data.version
        Write-VoiceLog "Estado del servidor: $status (v$version)" "SUCCESS"
        Speak-Text "El servidor está $status. Versión $version"
    }
    else {
        Speak-Text "No se pudo obtener el estado del servidor"
    }
}

function Get-ComputersList {
    $result = Invoke-ApiRequest -Endpoint "/api/computers"

    if ($result -and $result.data -and $result.data.computers) {
        $computers = $result.data.computers

        Write-Host "`n=== Equipos en Red ===" -ForegroundColor Cyan
        foreach ($c in $computers) {
            Write-Host "  $($c.ipAddress) - $($c.hostname)" -ForegroundColor Green
        }

        if ($computers.Count -gt 0) {
            $names = ($computers | Select-Object -First 5 | ForEach-Object { $_.hostname -replace '\.', '' }) -join ", "
            Speak-Text "Hay $($computers.Count) equipos. $names"
        }
        else {
            Speak-Text "No hay equipos en la red"
        }
    }
    else {
        Speak-Text "No hay equipos registrados"
    }
}

function Get-ComputersCount {
    $result = Invoke-ApiRequest -Endpoint "/api/computers"

    if ($result -and $result.data) {
        $count = $result.data.computers.Count
        Speak-Text "Hay $count equipos en la red"
    }
    else {
        Speak-Text "No se pudo obtener la lista de equipos"
    }
}

function Stop-RemoteComputerVoice {
    param($Context)

    # Intentar extraer IP o nombre del comando
    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "Qué equipo quieres apagar? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        Write-VoiceLog "Enviando comando de apagado a $ip"
        Speak-Text "Apagando equipo $ip"

        $body = @{ force = $false } | ConvertTo-Json
        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/shutdown" -Method "POST" -Body $body

        if ($result -and $result.data.success) {
            Speak-Text "Comando de apagado enviado a $ip"
        }
        else {
            Speak-Text "Error al apagar el equipo"
        }
    }
}

function Restart-RemoteComputerVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "Qué equipo quieres reiniciar? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        Write-VoiceLog "Enviando comando de reinicio a $ip"
        Speak-Text "Reiniciando equipo $ip"

        $body = @{ force = $false } | ConvertTo-Json
        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/restart" -Method "POST" -Body $body

        if ($result -and $result.data.success) {
            Speak-Text "Comando de reinicio enviado a $ip"
        }
        else {
            Speak-Text "Error al reiniciar el equipo"
        }
    }
}

function Start-RemoteComputerVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "Qué equipo quieres encender? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        Write-VoiceLog "Enviando Wake-on-LAN a $ip"
        Speak-Text "Encendiendo equipo $ip"

        $body = @{} | ConvertTo-Json
        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/power-on" -Method "POST" -Body $body

        if ($result -and $result.data) {
            if ($result.data.isOnline) {
                Speak-Text "Equipo $ip encendido y verificado"
            }
            else {
                Speak-Text "Wake-on-LAN enviado, pero no se confirmó el encendido"
            }
        }
        else {
            Speak-Text "Error al encender el equipo"
        }
    }
}

function Get-ComputerInfoVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "De qué equipo quieres información? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        Speak-Text "Obteniendo información de $ip"

        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/info"

        if ($result -and $result.data) {
            $info = $result.data
            Write-Host "`n=== Información de $ip ===" -ForegroundColor Cyan
            Write-Host "  Hostname: $($info.hostname)" -ForegroundColor White
            Write-Host "  SO: $($info.os)" -ForegroundColor White
            Write-Host "  CPU: $($info.cpuModel)" -ForegroundColor White
            Write-Host "  RAM: $($info.totalRAM_GB) GB" -ForegroundColor White

            Speak-Text "$($info.hostname). Sistema operativo $($info.os). $($info.totalRAM_GB) gigabytes de RAM"
        }
        else {
            Speak-Text "No se pudo obtener información del equipo"
        }
    }
}

function Get-ComputerResourcesVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "De qué equipo quieres ver recursos? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/resources"

        if ($result -and $result.data) {
            $res = $result.data
            Write-Host "`n=== Recursos de $ip ===" -ForegroundColor Cyan
            Write-Host "  CPU: $($res.cpuUsage)%" -ForegroundColor $(if($res.cpuUsage -gt 80){"Red"}elseif($res.cpuUsage -gt 50){"Yellow"}else{"Green"})
            Write-Host "  RAM: $($res.ramUsagePercent)% ($($res.usedRAM_MB) MB / $($res.totalRAM_MB) MB)" -ForegroundColor Yellow

            Speak-Text "Uso de CPU $($res.cpuUsage) por ciento. Uso de memoria $($res.ramUsagePercent) por ciento"
        }
        else {
            Speak-Text "No se pudo obtener uso de recursos"
        }
    }
}

function Get-ComputerHardwareVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        Speak-Text "De qué equipo quieres ver hardware? Di la dirección IP"
        $ip = Read-Host "  IP del equipo"
    }

    if ($ip) {
        Speak-Text "Obteniendo inventario de hardware de $ip"

        $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/hardware"

        if ($result -and $result.data) {
            $hw = $result.data
            Write-Host "`n=== Hardware de $ip ===" -ForegroundColor Cyan
            Write-Host "  CPU: $($hw.cpu) ($($hw.cpuCores) núcleos)" -ForegroundColor White
            Write-Host "  RAM: $($hw.totalRAM_GB) GB" -ForegroundColor White
            Write-Host "  GPU: $($hw.gpu)" -ForegroundColor White

            Speak-Text "Procesador $($hw.cpu). $($hw.totalRAM_GB) gigabytes de RAM. Gráficos $($hw.gpu)"
        }
        else {
            Speak-Text "No se pudo obtener inventario de hardware"
        }
    }
}

function Execute-RemoteCommandVoice {
    param($Context)

    $ip = Extract-IPFromCommand -Text $Context.OriginalText

    if (-not $ip) {
        # Obtener primer equipo disponible
        $computers = Invoke-ApiRequest -Endpoint "/api/computers"
        if ($computers -and $computers.data.computers.Count -gt 0) {
            $ip = $computers.data.computers[0].ipAddress
            Speak-Text "En qué equipo? Usando $ip"
        }
        else {
            Speak-Text "Qué equipo? Di la dirección IP"
            $ip = Read-Host "  IP del equipo"
        }
    }

    if ($ip) {
        Speak-Text "Qué comando quieres ejecutar?"
        $command = Read-Host "  Comando"

        if ($command) {
            Speak-Text "Ejecutando $command en $ip"

            $body = @{ command = $command } | ConvertTo-Json
            $result = Invoke-ApiRequest -Endpoint "/api/computer/$ip/command" -Method "POST" -Body $body

            if ($result -and $result.data) {
                Write-Host "`n=== Resultado ===" -ForegroundColor Cyan
                Write-Host $result.data.output
                Speak-Text "Comando ejecutado"
            }
            else {
                Speak-Text "Error al ejecutar el comando"
            }
        }
    }
}

function Get-RecentLogs {
    $result = Invoke-ApiRequest -Endpoint "/api/logs?lines=10"

    if ($result -and $result.data.logs) {
        Write-Host "`n=== Logs Recientes ===" -ForegroundColor Cyan
        foreach ($log in $result.data.logs) {
            Write-Host "  $log" -ForegroundColor Gray
        }
        Speak-Text "Logs recientes mostrados en pantalla"
    }
    else {
        Speak-Text "No se pudieron obtener los logs"
    }
}

function Show-VoiceHelp {
    $helpText = @"

COMANDOS DE VOZ DISPONIBLES:

  ESCANEO:
    - "Escanear red" - Busca equipos en la red
    - "Buscar equipos" - Igual que escanear

  ESTADO:
    - "Estado del servidor" - Ver estado del API
    - "Estado" - Igual que arriba

  CONTROL DE ENERGÍA:
    - "Apagar equipo [IP]" - Apaga un equipo
    - "Reiniciar equipo [IP]" - Reinicia un equipo
    - "Encender equipo [IP]" - Wake-on-LAN

  INFORMACIÓN:
    - "Lista de equipos" - Muestra todos los equipos
    - "Información de [IP]" - Info detallada
    - "Recursos de [IP]" - CPU/RAM en tiempo real
    - "Hardware de [IP]" - Inventario hardware

  UTILIDADES:
    - "Logs recientes" - Ver últimos logs
    - "Cuantos equipos" - Contar equipos

  AYUDA:
    - "Ayuda" - Muestra esta ayuda
    - "Que puedo decir" - Igual que ayuda

"@

    Write-Host $helpText -ForegroundColor Cyan
    Speak-Text "Ayuda mostrada en pantalla. Los comandos incluyen escanear red, estado, apagar equipo, reiniciar equipo, encender equipo, lista de equipos, información, recursos, hardware, logs, y ayuda."
}

# =============================================================================
# Utilidades
# =============================================================================

function Extract-IPFromCommand {
    param([string]$Text)

    # Patrón para IP (xxx.xxx.xxx.xxx)
    if ($Text -match '(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})') {
        return $matches[1]
    }

    # Buscar por hostname en configuración
    $configPath = "$PSScriptRoot\network-config.json"
    if (Test-Path $configPath) {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        foreach ($computer in $config.computers) {
            if ($computer.hostname -and $Text -like "*$($computer.hostname)*") {
                return $computer.ipAddress
            }
        }
    }

    return $null
}

# =============================================================================
# Programa Principal
# =============================================================================

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

