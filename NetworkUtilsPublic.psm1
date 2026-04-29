# NetworkUtilsPublic.psm1 - Local Network Agent Core Utilities v2.4.0 (PRO)
# =============================================================================

$Global:ProjectRoot = $PSScriptRoot
$Global:CredPath = "$Global:ProjectRoot\core0-cred.xml"

function Get-StoredCredential {
    $path = "$PSScriptRoot\core0-cred.xml"
    if (Test-Path $path) {
        try {
            return Import-CliXml -Path $path -ErrorAction Stop
        } catch {
            Write-Host "[WARN] Credenciales corruptas o ilegibles. Eliminando..." -ForegroundColor Yellow
            Remove-Item $path -Force -ErrorAction SilentlyContinue
        }
    }
    return $null
}

function Get-NetworkConfig {
    param([string]$Path = "$Global:ProjectRoot\network-config.json")
    $defaults = @{ SubnetPrefix = "192.168.1"; Port = 5985; Computers = @(); NtfyTopic = "local-network-agent"; ScheduledTasks = @(); Core0MAC = "" }
    if (Test-Path $Path) {
        try {
            $config = Get-Content $Path -Raw | ConvertFrom-Json
            foreach ($key in $defaults.Keys) {
                if (-not ($config.PSObject.Properties.Name -contains $key)) { Add-Member -InputObject $config -MemberType NoteProperty -Name $key -Value $defaults[$key] -Force }
            }
            return $config
        } catch { }
    }
    return $defaults
}

function Set-NetworkConfig { param([object]$Config, [string]$Path = "$Global:ProjectRoot\network-config.json") $Config | ConvertTo-Json -Depth 5 | Set-Content $Path }

function Resolve-ComputerAddress {
    param([string]$ComputerName, $Config)
    
    # Buscar en la lista de equipos configurados
    if ($Config.Computers) {
        $match = $Config.Computers | Where-Object { $_.Hostname -eq $ComputerName -or $_.IPAddress -eq $ComputerName } | Select-Object -First 1
        if ($match) { return $match.IPAddress }
    }
    
    # Intentar resoluciÃ³n DNS
    try {
        $ip = [System.Net.Dns]::GetHostAddresses($ComputerName) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1
        if ($ip) { return $ip.IPAddressToString }
    } catch { }
    
    return $null
}

function Get-NetworkComputers {
    param([string]$SubnetPrefix = "192.168.1", [int]$Timeout = 800, [int]$MaxThreads = 60)
    $rsPool = [RunspaceFactory]::CreateRunspacePool(1, $MaxThreads); $rsPool.Open(); $jobs = @()
    for ($i = 1; $i -le 254; $i++) {
        $ip = "$SubnetPrefix.$i"; $ps = [PowerShell]::Create().AddScript({
            param($IPAddr, $TO)
            $p = New-Object System.Net.NetworkInformation.Ping
            try {
                $res = $p.Send($IPAddr, $TO)
                if ($res.Status -eq 'Success') {
                    try { $h = [System.Net.Dns]::GetHostEntry($IPAddr).HostName } catch { $h = $IPAddr }
                    $mac = "N/A"
                    try {
                        $nei = Get-NetNeighbor -IPAddress $IPAddr -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1
                        if ($nei -and $nei.LinkLayerAddress) { $mac = $nei.LinkLayerAddress }
                    } catch {}
                    if ($mac -eq "N/A") {
                        try {
                            $arpLine = arp -a $IPAddr 2>$null | Select-String $IPAddr | Select-Object -First 1
                            if ($arpLine) {
                                $parts = ($arpLine -replace '\s+', ' ').Trim().Split(' ')
                                if ($parts.Length -ge 2) { $mac = $parts[1] }
                            }
                        } catch {}
                    }
                    return [PSCustomObject]@{ IPAddress = $IPAddr; Hostname = $h; Status = "Online"; MACAddress = $mac }
                }
            } catch {}
            return $null
        }).AddArgument($ip).AddArgument($Timeout); $ps.RunspacePool = $rsPool; $jobs += @{ PS = $ps; Handle = $ps.BeginInvoke() }
    }
    $active = @(); foreach ($j in $jobs) { $res = $j.PS.EndInvoke($j.Handle); if ($res) { $active += $res }; $j.PS.Dispose() }
    $rsPool.Close(); $rsPool.Dispose(); return $active
}

function Merge-ComputerIPs {
    param([array]$ScannedComputers, [array]$ExistingComputers)
    $merged = @()
    # Mantener todo lo existente, actualizando estado a Offline si no se escaneÃ³
    foreach ($existing in $ExistingComputers) {
        $match = $ScannedComputers | Where-Object { $_.IPAddress -eq $existing.IPAddress -or $_.Hostname -eq $existing.Hostname }
        if ($match) { 
            $merged += [PSCustomObject]@{ IPAddress = $match.IPAddress; Hostname = $match.Hostname; MACAddress = $existing.MACAddress; Status = "Online" } 
        } else { 
            $merged += [PSCustomObject]@{ IPAddress = $existing.IPAddress; Hostname = $existing.Hostname; MACAddress = $existing.MACAddress; Status = "Offline" } 
        }
    }
    # AÃ±adir nuevos descubrimientos
    foreach ($scanned in $ScannedComputers) {
        if (-not ($merged | Where-Object { $_.IPAddress -eq $scanned.IPAddress })) { $merged += $scanned }
    }
    return $merged
}

# --- FUNCIONES DE ARCHIVOS MEJORADAS ---
function Get-RemoteDrives { 
    param($ComputerName, $Credential) 
    $p = @{ComputerName=$ComputerName; ScriptBlock={Get-CimInstance Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3} | Select-Object DeviceID, @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,2)}}}; ErrorAction='Stop'}
    if($Credential){$p.Credential=$Credential}
    try { return Invoke-Command @p } catch { return @() }
}

function Get-RemoteDirectory { 
    param($ComputerName, $Path, $Credential) 
    $p = @{ComputerName=$ComputerName; ScriptBlock={param($p) Get-ChildItem -Path $p -ErrorAction SilentlyContinue | Select-Object Name, @{N='Size';E={$_.Length}}, LastWriteTime, @{N='Type';E={if($_.PSIsContainer){'Dir'}else{'File'}}} }; ArgumentList=$Path; ErrorAction='Stop'}
    if($Credential){$p.Credential=$Credential}
    try { return Invoke-Command @p } catch { return @() }
}

function Copy-BetweenRemotes {
    param($SourceComp, $SourcePath, $DestComp, $DestPath, [PSCredential]$Credential)
    try {
        $tempFile = "$env:TEMP\net-transfer-$(Get-Random).tmp"
        Write-Host "Paso 1: Descargando desde $SourceComp..." -ForegroundColor Gray
        $s1 = New-PSSession -ComputerName $SourceComp -Credential $Credential
        Copy-Item -FromSession $s1 -Path $SourcePath -Destination $tempFile -Force
        Remove-PSSession $s1

        Write-Host "Paso 2: Subiendo a $DestComp..." -ForegroundColor Gray
        $s2 = New-PSSession -ComputerName $DestComp -Credential $Credential
        Copy-Item -ToSession $s2 -Path $tempFile -Destination $DestPath -Force
        Remove-PSSession $s2

        Remove-Item $tempFile -Force
        return $true
    } catch {
        Write-Host "Error en transferencia: $_" -ForegroundColor Red
        return $false
    }
}

function Invoke-RemoteCommand {
    param($ComputerName, $Command, $Credential)
    $p = @{ComputerName=$ComputerName; ScriptBlock=[scriptblock]::Create($Command); ErrorAction='Stop'}
    if($Credential){$p.Credential=$Credential}
    return Invoke-Command @p
}

function Invoke-RemoteVoice {
    param(
        [string]$ComputerName,
        [string]$Text,
        $Credential
    )
    if (-not $ComputerName -or -not $Text) { return $false }
    $sb = {
        param($msg)
        $voice = New-Object -ComObject SAPI.SpVoice
        $voice.Speak($msg)
    }
    $params = @{ ComputerName = $ComputerName; ScriptBlock = $sb; ArgumentList = $Text; ErrorAction = 'Stop' }
    if ($Credential) {
        $params.Credential = $Credential
    } else {
        $stored = Get-StoredCredential
        if ($stored) { $params.Credential = $stored }
    }
    try {
        Invoke-Command @params | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-RemoteSystemInfo {
    param($ComputerName, $Credential)
    $sb = {
        [PSCustomObject]@{
            OS = (Get-CimInstance Win32_OperatingSystem).Caption
            CPUCount = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
            TotalRAMGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
        }
    }
    $p = @{ComputerName=$ComputerName; ScriptBlock=$sb; ErrorAction='Stop'}
    if ($Credential) { $p.Credential = $Credential } else { $stored = Get-StoredCredential; if ($stored) { $p.Credential = $stored } }
    try { return Invoke-Command @p } catch { return @{ error = 'remote-fail' } }
}

function Get-RemoteResourceUsage {
    param($ComputerName, $Credential)
    $sb = {
        [PSCustomObject]@{
            CPUUsage = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue, 2)
            TotalRAMGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
            FreeRAMGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)
        }
    }
    $p = @{ComputerName=$ComputerName; ScriptBlock=$sb; ErrorAction='Stop'}
    if ($Credential) { $p.Credential = $Credential } else { $stored = Get-StoredCredential; if ($stored) { $p.Credential = $stored } }
    try { return Invoke-Command @p } catch { return @{ error = 'remote-fail' } }
}

function Test-Core0Status {
    param([int]$PingCount = 2, [int]$PingTimeout = 1500)

    $cfg = Get-NetworkConfig
    $target = Resolve-ComputerAddress 'CORE0' $cfg
    $status = @{ Host = 'CORE0'; Found = $false; Reachable = $false; WOLSent = $false; Info = $null; Error = $null }

    if (-not $target) {
        $status.Error = 'CORE0 no localizado en config ni DNS.'
        if ($cfg.Core0MAC) { $status.Info = 'Se intentarÃ¡ WOL por MAC.' }
    } else {
        $status.Found = $true
        $reachable = Test-Connection -ComputerName $target -Count $PingCount -Quiet -TimeoutSeconds ($PingTimeout/1000)
        $status.Reachable = $reachable
        $status.TargetIP = $target
        if ($reachable) {
            $status.Info = Get-RemoteSystemInfo $target
        }
    }

    if (-not $status.Reachable -and $cfg.Core0MAC) {
        $wolOk = Send-WakeOnLan $cfg.Core0MAC
        $status.WOLSent = $wolOk
        if ($wolOk) { $status.Error = 'WOL enviado a Core0 MAC.' } else { $status.Error = 'FallÃ³ envÃ­o WOL.' }
    }

    return $status
}

function Connect-RemoteComputer {
    param([Parameter(Mandatory=$true)]$ComputerName, $Credential)
    
    if([string]::IsNullOrWhiteSpace($ComputerName)) {
        Write-Host "[ERROR] ERROR: No se proporcionÃ³ ninguna direcciÃ³n IP" -ForegroundColor Red
        return
    }
    
    $ComputerName = $ComputerName.Trim()
    Write-Host "=== SHELL REMOTO A $ComputerName ===" -ForegroundColor Cyan

    try {
        Set-Item WSMan:\localhost\Client\TrustedHosts -Value $ComputerName -Concatenate -Force -ErrorAction SilentlyContinue
    } catch {}

    if (-not $Credential) { $Credential = Get-StoredCredential }

    if ($Credential) {
        Write-Host "[OK] Conectando con credenciales almacenadas..." -ForegroundColor Green
        Enter-PSSession -ComputerName $ComputerName -Credential $Credential
    } else {
        Write-Host "[WARN] Sin credenciales. Proporcione credenciales manualmente:" -ForegroundColor Yellow
        $manualCred = Get-Credential
        if ($manualCred) {
            Enter-PSSession -ComputerName $ComputerName -Credential $manualCred
        }
    }
}

# --- Funciones de Hardware/Software ---
function Get-RemoteHardwareInventory {
    param($ComputerName, $Credential)
    $sb = {
        [PSCustomObject]@{
            CPU = (Get-CimInstance Win32_Processor).Name
            RAM = "$([math]::Round((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Sum Capacity).Sum / 1GB, 2)) GB"
            Model = (Get-CimInstance Win32_ComputerSystem).Model
            Disk = (Get-CimInstance Win32_LogicalDisk | Where-Object {$_.DeviceID -eq 'C:'} | Select-Object @{N='Size';E={[math]::Round($_.Size/1GB,2)}}).Size
        }
    }
    $p = @{ComputerName=$ComputerName; ScriptBlock=$sb; ErrorAction='Stop'}
    if($Credential){$p.Credential=$Credential}
    return Invoke-Command @p
}

function Send-WakeOnLan {
    param(
        [string]$MACAddress,
        [int]$RepeatCount = 10,
        [int]$DelayMs = 50,
        [string]$BroadcastIP = "255.255.255.255"
    )
    if (-not $MACAddress -or $MACAddress -eq "N/A") { 
        Write-Host "Error: MAC address inválida: $MACAddress" -ForegroundColor Red
        return $false 
    }
    try {
        # Normalizar MAC address (quitar guiones, dos puntos, espacios)
        $cleanMAC = $MACAddress.Replace('-', '').Replace(':', '').Replace(' ', '').ToUpper()
        if ($cleanMAC.Length -ne 12) { 
            Write-Host "Error: MAC address con longitud incorrecta: $cleanMAC (longitud: $($cleanMAC.Length))" -ForegroundColor Red
            return $false 
        }
        
        Write-Host "=== ENVIANDO WOL A: $cleanMAC ===" -ForegroundColor Cyan
        
        # Convertir a bytes
        $macBytes = @()
        for ($i = 0; $i -lt 12; $i += 2) {
            $macBytes += [byte]::Parse($cleanMAC.Substring($i, 2), [System.Globalization.NumberStyles]::HexNumber)
        }
        
        # Crear Magic Packet (6 bytes 0xFF + 16 repeticiones de la MAC = 102 bytes)
        $packet = New-Object byte[] 102
        for ($i = 0; $i -lt 6; $i++) { $packet[$i] = 0xFF }
        for ($i = 0; $i -lt 16; $i++) {
            for ($j = 0; $j -lt 6; $j++) {
                $packet[6 + ($i * 6) + $j] = $macBytes[$j]
            }
        }
        
        Write-Host "Magic Packet: 6xFF + 16xMAC = 102 bytes" -ForegroundColor Yellow
        Write-Host "Broadcast IP: $BroadcastIP" -ForegroundColor Gray
        
        # Método: Usar Socket directamente
        $socket = New-Object System.Net.Sockets.Socket([System.Net.Sockets.AddressFamily]::InterNetwork, [System.Net.Sockets.SocketType]::Dgram, [System.Net.Sockets.ProtocolType]::Udp)
        $socket.EnableBroadcast = $true
        $socket.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::Socket, [System.Net.Sockets.SocketOptionName]::Broadcast, $true)
        
        # Bind to local port 0 (any available port)
        $socket.Bind((New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)))
        
        $endPoint = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse($BroadcastIP), 9)
        
        $sentCount = 0
        for ($r = 0; $r -lt $RepeatCount; $r++) {
            try {
                $bytesSent = $socket.SendTo($packet, $endPoint)
                Write-Host "  [$($r+1)/$RepeatCount] Enviado $bytesSent bytes a ${BroadcastIP}:9" -ForegroundColor Green
                $sentCount++
            } catch {
                Write-Host "  [$($r+1)/$RepeatCount] Error: $($_.Exception.Message)" -ForegroundColor Red
            }
            if ($r -lt ($RepeatCount - 1)) {
                Start-Sleep -Milliseconds $DelayMs
            }
        }
        
        $socket.Close()
        $socket.Dispose()
        
        Write-Host "WOL COMPLETADO: $sentCount/$RepeatCount paquetes enviados" -ForegroundColor Green
        
        return $true
    } catch {
        $err = $_
        Write-Host "Error crítico enviando WOL: $($err.Exception.Message)" -ForegroundColor Red
        Write-Host "StackTrace: $($err.ScriptStackTrace)" -ForegroundColor Yellow
        return $false
    }
}

function Get-ComputerMACAddress {
    param(
        [string]$ComputerName,
        $Credential
    )
    try {
        $sb = {
            $adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notlike "*Virtual*" -and $_.InterfaceDescription -notlike "*Hyper-V*" }
            foreach ($adapter in $adapters) {
                # Priorizar adaptadores Ethernet sobre Wi-Fi
                $isEthernet = $adapter.InterfaceDescription -notlike "*Wireless*" -and $adapter.InterfaceDescription -notlike "*Wi-Fi*"
                [PSCustomObject]@{
                    Name = $adapter.Name
                    MACAddress = $adapter.MacAddress
                    InterfaceDescription = $adapter.InterfaceDescription
                    IsEthernet = $isEthernet
                }
            }
        }
        $params = @{ ComputerName = $ComputerName; ScriptBlock = $sb; ErrorAction = 'Stop' }
        if ($Credential) { $params.Credential = $Credential }
        
        $adapters = Invoke-Command @params
        # Priorizar adaptador Ethernet
        $ethernet = $adapters | Where-Object { $_.IsEthernet } | Select-Object -First 1
        if ($ethernet) { return $ethernet.MACAddress }
        
        # Si no hay Ethernet, devolver el primero
        if ($adapters) { return $adapters[0].MACAddress }
        return $null
    } catch {
        return $null
    }
}

function Save-Core0MAC {
    param([bool]$Force = $false)
    $cfg = Get-NetworkConfig
    $cred = Get-StoredCredential
    
    # Si no es forzado y ya tenemos MAC, devolver la guardada
    if (-not $Force -and $cfg.Core0MAC -and $cfg.Core0MAC -ne "") {
        return $cfg.Core0MAC
    }
    
    # Intentar obtener la MAC de CORE0 por DNS
    $core0IP = Resolve-ComputerAddress "CORE0" $cfg
    if (-not $core0IP) {
        Write-NetworkLog "No se pudo resolver CORE0 por DNS" "WARN"
        if (-not $Force -and $cfg.Core0MAC -and $cfg.Core0MAC -ne "") {
            return $cfg.Core0MAC
        }
        return $null
    }
    
    # Verificar si CORE0 estÃ¡ accesible
    $reachable = Test-Connection -ComputerName $core0IP -Count 1 -Quiet -TimeoutSeconds 2
    if (-not $reachable) {
        Write-NetworkLog "CORE0 no esta accesible en $core0IP" "WARN"
        if (-not $Force -and $cfg.Core0MAC -and $cfg.Core0MAC -ne "") {
            return $cfg.Core0MAC
        }
        return $null
    }
    
    # Obtener MAC address
    $mac = Get-ComputerMACAddress -ComputerName $core0IP -Credential $cred
    if ($mac) {
        $cfg.Core0MAC = $mac
        Set-NetworkConfig $cfg
        Write-NetworkLog "MAC de CORE0 guardada: $mac (IP: $core0IP)" "INFO"
        return $mac
    }
    
    return $null
}
function Stop-RemoteComputer { param($ComputerName, $Credential) if($Credential){Stop-Computer -ComputerName $ComputerName -Credential $Credential -Force}else{Stop-Computer -ComputerName $ComputerName -Force} }
function Restart-RemoteComputer { param($ComputerName, $Credential) if($Credential){Restart-Computer -ComputerName $ComputerName -Credential $Credential -Force}else{Restart-Computer -ComputerName $ComputerName -Force} }



# --- Funciones de Programacion de Tareas ---
function Add-ScheduledTask {
    param(
        [string]$ComputerName,
        [string]$Action,
        [string]$Time,
        [array]$Days = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        [bool]$Enabled = $true
    )
    $cfg = Get-NetworkConfig
    if (-not $cfg.ScheduledTasks) { $cfg.ScheduledTasks = @() }
    
    $newTask = [PSCustomObject]@{
        ID = [guid]::NewGuid().ToString()
        ComputerName = $ComputerName
        Action = $Action
        Time = $Time
        Days = $Days
        Enabled = $Enabled
        LastRun = ""
    }
    
    $cfg.ScheduledTasks += $newTask
    Set-NetworkConfig $cfg
    return $newTask
}

function Remove-ScheduledTask {
    param([string]$ID)
    $cfg = Get-NetworkConfig
    if ($cfg.ScheduledTasks) {
        $cfg.ScheduledTasks = $cfg.ScheduledTasks | Where-Object { $_.ID -ne $ID }
        Set-NetworkConfig $cfg
        return $true
    }
    return $false
}

function Get-ScheduledTasks {
    $cfg = Get-NetworkConfig
    return $cfg.ScheduledTasks
}

function Invoke-ScheduledTasks {
    $cfg = Get-NetworkConfig
    if (-not $cfg.ScheduledTasks) { return }
    
    $now = Get-Date
    $currentTime = $now.ToString("HH:mm")
    $currentDay = $now.DayOfWeek.ToString()
    $todayStr = $now.ToString("yyyy-MM-dd")
    
    $updated = $false
    foreach ($task in $cfg.ScheduledTasks) {
        if ($task.Enabled -and $task.Time -eq $currentTime -and ($task.Days -contains $currentDay -or $task.Days -contains "Daily") -and $task.LastRun -ne $todayStr) {
            Write-Host "[SCHEDULER] Ejecutando tarea: $($task.Action) en $($task.ComputerName)" -ForegroundColor Cyan
            
            try {
                if ($task.Action -eq "PowerOn") {
                    # Buscar MAC para WoL
                    $comp = $cfg.Computers | Where-Object { $_.IPAddress -eq $task.ComputerName -or $_.Hostname -eq $task.ComputerName } | Select-Object -First 1
                    if ($comp -and $comp.MACAddress -and $comp.MACAddress -ne "N/A") {
                        Send-WakeOnLan -MACAddress $comp.MACAddress
                    } else {
                        Write-Host "[SCHEDULER] Error: No se encontro MAC para $($task.ComputerName)" -ForegroundColor Red
                    }
                } elseif ($task.Action -eq "PowerOff") {
                    Stop-RemoteComputer -ComputerName $task.ComputerName -Credential (Get-StoredCredential)
                } elseif ($task.Action -eq "Restart") {
                    Restart-RemoteComputer -ComputerName $task.ComputerName -Credential (Get-StoredCredential)
                }
                
                $task.LastRun = $todayStr
                $updated = $true
            } catch {
                Write-Host "[SCHEDULER] Error ejecutando tarea $($task.ID): $_" -ForegroundColor Red
            }
        }
    }
    
    if ($updated) {
        Set-NetworkConfig $cfg
    }
}


Export-ModuleMember -Function *
