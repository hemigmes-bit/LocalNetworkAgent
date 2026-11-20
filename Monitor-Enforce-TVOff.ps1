param(
    [string]$MAC = "04:E4:B6:CF:89:38",
    [int]$CheckIntervalSeconds = 15
)

# Definir horario de bloqueo
$startTime = 16
$endTime = 19

# Comprobar si estamos en horario de bloqueo
$now = Get-Date
$isWeekday = ($now.DayOfWeek -ge [DayOfWeek]::Monday -and $now.DayOfWeek -le [DayOfWeek]::Friday)
$isWithinTime = ($now.Hour -ge $startTime -and $now.Hour -lt $endTime)

if (-not ($isWeekday -and $isWithinTime)) {
    Write-Host "Fuera de horario de bloqueo o fin de semana. No se aplica restricción."
    exit 0
}

# Check if today is a national holiday in Spain (fiesta nacional)
$today = (Get-Date).ToString('yyyy-MM-dd')
$holidays = @('2026-10-12')
if ($holidays -contains $today) {
    Write-Host "Hoy es fiesta nacional ($today). No se aplicará bloqueo de TV."
    exit 0
}

$scriptPath = Join-Path $PSScriptRoot "TurnOff-SamsungTV.ps1"
if (-not (Test-Path $scriptPath)) {
    $scriptPath = "C:\Users\Usuario\LocalNetworkAgent\TurnOff-SamsungTV.ps1"
}

# --- Función robusta para encontrar IP por MAC ---
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
    Write-Host "Error: No se encontró la TV ($MAC) en la red"
    exit 1
}

Write-Host "TV encontrada en $IP. Iniciando bloqueo hasta las $endTime:00..."

# --- Bloqueo de YouTube a nivel de firewall ---
$youtubeIPs = @("172.217.0.0/16", "142.250.0.0/15", "209.85.0.0/17")

foreach ($cidr in $youtubeIPs) {
    $ruleName = "Block-YouTube-TV-" + $cidr.Replace(".", "_").Replace("/", "_")
    try {
        netsh advfirewall firewall delete rule name="$ruleName" > $null 2>&1
        netsh advfirewall firewall add rule name="$ruleName" dir=out action=block remoteip=$cidr localip=$IP profile=any | Out-Null
    } catch { }
}

# --- Monitoreo ---
while ((Get-Date).Hour -lt $endTime) {
    Start-Sleep -Seconds $CheckIntervalSeconds
    
    # Re-verificar IP dinámica
    $newIP = Find-TV-IP -TargetMAC $MAC
    if ($newIP -and $newIP -ne $IP) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] IP de TV cambió: $IP -> $newIP"
        $IP = $newIP
        # Actualizar reglas de firewall con nueva IP
        foreach ($cidr in $youtubeIPs) {
            $ruleName = "Block-YouTube-TV-" + $cidr.Replace(".", "_").Replace("/", "_")
            try {
                netsh advfirewall firewall delete rule name="$ruleName" > $null 2>&1
                netsh advfirewall firewall add rule name="$ruleName" dir=out action=block remoteip=$cidr localip=$IP profile=any | Out-Null
            } catch { }
        }
    }
    
    try {
        $res = Invoke-RestMethod -Uri "http://${IP}:8001/api/v2/" -TimeoutSec 3 -ErrorAction Stop
        if ($res.device.PowerState -eq "on") {
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] TV detectada encendida. Apagando..."
            & $scriptPath -IP $IP -Key "KEY_POWER"
        }
    } catch { }
}

# --- Limpieza ---
foreach ($cidr in $youtubeIPs) {
    $ruleName = "Block-YouTube-TV-" + $cidr.Replace(".", "_").Replace("/", "_")
    netsh advfirewall firewall delete rule name="$ruleName" > $null 2>&1
}

Write-Host "Periodo de restricción finalizado."