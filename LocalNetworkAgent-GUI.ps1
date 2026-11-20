param([switch]$Minimized = $false)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$configPath = Join-Path $projectPath "network-config.json"

$global:scanning = $false
$global:selectedDevice = $null

if (Test-Path $configPath) {
    $global:config = Get-Content $configPath -Raw | ConvertFrom-Json
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Local Network Agent v2.4.0"
$form.Size = New-Object System.Drawing.Size(1300, 800)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "Sizable"
$form.MinimumSize = New-Object System.Drawing.Size(1100, 700)
$form.Font = New-Object System.Drawing.Font("Tahoma", 8.25)
$form.BackColor = [System.Drawing.SystemColors]::Control

$neonCyan    = [System.Drawing.Color]::FromArgb(0, 0, 160)        # azul (títulos)
$neonMagenta = [System.Drawing.Color]::FromArgb(0, 0, 128)        # azul oscuro
$neonGreen   = [System.Drawing.Color]::FromArgb(0, 128, 0)        # verde (online)
$neonOrange  = [System.Drawing.Color]::FromArgb(160, 80, 0)       # naranja oscuro
$neonBlue    = [System.Drawing.Color]::FromArgb(0, 0, 160)        # azul
$darkest     = [System.Drawing.SystemColors]::Control             # gris (barras)
$dark        = [System.Drawing.SystemColors]::Control             # gris
$medium      = [System.Drawing.SystemColors]::Control             # gris (paneles)
$light       = [System.Drawing.SystemColors]::ControlLight        # gris claro
$headerBg    = [System.Drawing.Color]::FromArgb(200, 210, 235)    # azul claro (cabeceras)
$textDim     = [System.Drawing.Color]::FromArgb(96, 96, 96)       # texto atenuado
$textBright  = [System.Drawing.Color]::Black                      # texto normal

function New-CyberButton {
    param($Text, $X, $Y, $W, $H, $Color, $Action)
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $Text
    $btn.Location = New-Object System.Drawing.Point($X, $Y)
    $btn.Size = New-Object System.Drawing.Size($W, $H)
    $btn.FlatStyle = [System.Windows.Forms.FlatStyle]::Standard
    $btn.UseVisualStyleBackColor = $true
    $btn.Font = New-Object System.Drawing.Font("Tahoma", 8.25)
    $btn.Cursor = [System.Windows.Forms.Cursors]::Default
    $btn.TextAlign = "MiddleCenter"
    $btn.Add_Click($Action)
    return $btn
}

# ─── Menu Strip ─────────────────────────────────────────────────────────────
$menuStrip = New-Object System.Windows.Forms.MenuStrip
$menuStrip.BackColor = $darkest
$menuStrip.ForeColor = $textBright

$archivoMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$archivoMenu.Text = "Archivo"
$archivoMenu.ForeColor = $textBright

$salirItem = New-Object System.Windows.Forms.ToolStripMenuItem
$salirItem.Text = "Salir"
$salirItem.Add_Click({ $form.Close() })
$archivoMenu.DropDownItems.Add($salirItem) | Out-Null

$herramientasMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$herramientasMenu.Text = "Herramientas"
$herramientasMenu.ForeColor = $textBright

$scanToolItem = New-Object System.Windows.Forms.ToolStripMenuItem
$scanToolItem.Text = "Escanear red"
$scanToolItem.Add_Click({ Start-NetworkScan })
$herramientasMenu.DropDownItems.Add($scanToolItem) | Out-Null

$apiToolItem = New-Object System.Windows.Forms.ToolStripMenuItem
$apiToolItem.Text = "Iniciar / Detener API"
$apiToolItem.Add_Click({ Toggle-Api })
$herramientasMenu.DropDownItems.Add($apiToolItem) | Out-Null

$ayudaMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$ayudaMenu.Text = "Ayuda"
$ayudaMenu.ForeColor = $textBright

$aboutItem = New-Object System.Windows.Forms.ToolStripMenuItem
$aboutItem.Text = "Acerca de..."
$aboutItem.Add_Click({ [System.Windows.Forms.MessageBox]::Show("Local Network Agent v2.4.0`nControl total de tu red local", "Acerca de") })
$ayudaMenu.DropDownItems.Add($aboutItem) | Out-Null

$menuStrip.Items.Add($archivoMenu) | Out-Null
$menuStrip.Items.Add($herramientasMenu) | Out-Null
$menuStrip.Items.Add($ayudaMenu) | Out-Null

$form.Controls.Add($menuStrip)

# ─── Header Title ────────────────────────────────────────────────────────────
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "Local Network Agent"
$lblTitle.Font = New-Object System.Drawing.Font("Tahoma", 14, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 0, 128)
$lblTitle.Location = New-Object System.Drawing.Point(20, 35)
$lblTitle.AutoSize = $true
$form.Controls.Add($lblTitle)

$lblVersion = New-Object System.Windows.Forms.Label
$lblVersion.Text = "v2.4.0"
$lblVersion.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblVersion.ForeColor = $textDim
$lblVersion.Location = New-Object System.Drawing.Point(25, 75)
$lblVersion.AutoSize = $true
$form.Controls.Add($lblVersion)

$btnScan = New-CyberButton -Text "ESCANEAR RED" -X 1050 -Y 40 -W 150 -H 40 -Color $neonGreen -Action { Start-NetworkScan }
$form.Controls.Add($btnScan)

$global:lblStatus = New-Object System.Windows.Forms.Label
$global:lblStatus.Text = "[ Presione ESCANEAR ]"
$global:lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$global:lblStatus.ForeColor = $textDim
$global:lblStatus.Location = New-Object System.Drawing.Point(1050, 85)
$global:lblStatus.AutoSize = $true
$form.Controls.Add($global:lblStatus)

# ─── Separator line ─────────────────────────────────────────────────────────
$sepLine = New-Object System.Windows.Forms.Panel
$sepLine.Location = New-Object System.Drawing.Point(15, 105)
$sepLine.Size = New-Object System.Drawing.Size(1260, 2)
$sepLine.BackColor = [System.Drawing.SystemColors]::ControlDark
$form.Controls.Add($sepLine)

# ─── Left Panel - Device List ───────────────────────────────────────────────
$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Location = New-Object System.Drawing.Point(15, 115)
$leftPanel.Size = New-Object System.Drawing.Size(350, 620)
$leftPanel.BackColor = $medium
$leftPanel.BorderStyle = "Fixed3D"
$form.Controls.Add($leftPanel)

$lblDevices = New-Object System.Windows.Forms.Label
$lblDevices.Text = "DISPOSITIVOS EN RED"
$lblDevices.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblDevices.ForeColor = $neonCyan
$lblDevices.Location = New-Object System.Drawing.Point(12, 12)
$lblDevices.AutoSize = $true
$leftPanel.Controls.Add($lblDevices)

$global:deviceList = New-Object System.Windows.Forms.ListView
$global:deviceList.Location = New-Object System.Drawing.Point(12, 40)
$global:deviceList.Size = New-Object System.Drawing.Size(322, 560)
$global:deviceList.BackColor = [System.Drawing.Color]::White
$global:deviceList.ForeColor = $textBright
$global:deviceList.FullRowSelect = $true
$global:deviceList.View = "Details"
$global:deviceList.GridLines = $false
$global:deviceList.HideSelection = $false
$global:deviceList.BorderStyle = "Fixed3D"

$null = $global:deviceList.Columns.Add("NOMBRE", 150)
$null = $global:deviceList.Columns.Add("IP", 90)
$null = $global:deviceList.Columns.Add("ESTADO", 60)

$global:deviceList.Add_DoubleClick({ Show-DeviceInfo })
$global:deviceList.Add_SelectedIndexChanged({
    if ($global:deviceList.SelectedItems.Count -gt 0) {
        $global:selectedDevice = $global:deviceList.SelectedItems[0].Tag
        Show-DeviceInfo
    }
})

# Context menu (right-click)
$contextMenu = New-Object System.Windows.Forms.ContextMenuStrip
$contextMenu.BackColor = $darkest
$contextMenu.ForeColor = $textBright

$ctxShell = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxShell.Text = "Shell remoto"
$ctxShell.Add_Click({ Open-Shell })
$contextMenu.Items.Add($ctxShell) | Out-Null

$ctxFiles = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxFiles.Text = "Explorar archivos"
$ctxFiles.Add_Click({ Open-Files })
$contextMenu.Items.Add($ctxFiles) | Out-Null

$ctxWoL = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxWoL.Text = "Wake-on-LAN"
$ctxWoL.Add_Click({ Send-WoL })
$contextMenu.Items.Add($ctxWoL) | Out-Null

$ctxForce = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxForce.Text = "Forzar deteccion"
$ctxForce.Add_Click({ Force-Detect })
$contextMenu.Items.Add($ctxForce) | Out-Null

$ctxRemote = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxRemote.Text = "Acceso remoto (TV/RDP/Capture)"
$ctxRemote.Add_Click({ Open-Monitor })
$contextMenu.Items.Add($ctxRemote) | Out-Null

$global:deviceList.ContextMenuStrip = $contextMenu
$leftPanel.Controls.Add($global:deviceList)

# ─── Right Panel - Info & Actions ───────────────────────────────────────────
$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Location = New-Object System.Drawing.Point(380, 115)
$rightPanel.Size = New-Object System.Drawing.Size(900, 620)
$rightPanel.BackColor = $medium
$rightPanel.BorderStyle = "Fixed3D"
$form.Controls.Add($rightPanel)

# ─ Info Banner ─
$infoHeader = New-Object System.Windows.Forms.Panel
$infoHeader.Location = New-Object System.Drawing.Point(0, 0)
$infoHeader.Size = New-Object System.Drawing.Size(898, 30)
$infoHeader.BackColor = $headerBg
$rightPanel.Controls.Add($infoHeader)

$lblInfoTitle = New-Object System.Windows.Forms.Label
$lblInfoTitle.Text = "INFORMACION DEL DISPOSITIVO"
$lblInfoTitle.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblInfoTitle.ForeColor = $neonMagenta
$lblInfoTitle.Location = New-Object System.Drawing.Point(15, 6)
$lblInfoTitle.AutoSize = $true
$infoHeader.Controls.Add($lblInfoTitle)

$global:txtInfo = New-Object System.Windows.Forms.RichTextBox
$global:txtInfo.Location = New-Object System.Drawing.Point(15, 40)
$global:txtInfo.Size = New-Object System.Drawing.Size(870, 260)
$global:txtInfo.Font = New-Object System.Drawing.Font("Cascadia Code", 10)
$global:txtInfo.ForeColor = $textDim
$global:txtInfo.BackColor = [System.Drawing.Color]::White
$global:txtInfo.ReadOnly = $true
$global:txtInfo.BorderStyle = "Fixed3D"
$global:txtInfo.ScrollBars = "Vertical"
$rightPanel.Controls.Add($global:txtInfo)

# ─ Actions ─
$actionHeader = New-Object System.Windows.Forms.Panel
$actionHeader.Location = New-Object System.Drawing.Point(0, 310)
$actionHeader.Size = New-Object System.Drawing.Size(898, 30)
$actionHeader.BackColor = $headerBg
$rightPanel.Controls.Add($actionHeader)

$lblActions = New-Object System.Windows.Forms.Label
$lblActions.Text = "ACCIONES"
$lblActions.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblActions.ForeColor = $neonCyan
$lblActions.Location = New-Object System.Drawing.Point(15, 6)
$lblActions.AutoSize = $true
$actionHeader.Controls.Add($lblActions)

$actionPanel = New-Object System.Windows.Forms.Panel
$actionPanel.Location = New-Object System.Drawing.Point(15, 345)
$actionPanel.Size = New-Object System.Drawing.Size(870, 60)
$actionPanel.BackColor = $dark
$rightPanel.Controls.Add($actionPanel)

$actionPanel.Controls.Add((New-CyberButton -Text "ARCHIVOS" -X 10 -Y 10 -W 120 -H 40 -Color $neonOrange -Action { Open-Files }))
$actionPanel.Controls.Add((New-CyberButton -Text "SHELL" -X 145 -Y 10 -W 100 -H 40 -Color ([System.Drawing.Color]::FromArgb(255, 80, 200)) -Action { Open-Shell }))
$actionPanel.Controls.Add((New-CyberButton -Text "WOL" -X 260 -Y 10 -W 80 -H 40 -Color $neonGreen -Action { Send-WoL }))
$actionPanel.Controls.Add((New-CyberButton -Text "VOZ" -X 355 -Y 10 -W 80 -H 40 -Color $neonOrange -Action { Open-Voice }))
$actionPanel.Controls.Add((New-CyberButton -Text "CHAT" -X 450 -Y 10 -W 80 -H 40 -Color $neonBlue -Action { Open-Intercom }))
$actionPanel.Controls.Add((New-CyberButton -Text "MONITOR" -X 545 -Y 10 -W 100 -H 40 -Color ([System.Drawing.Color]::FromArgb(0, 210, 190)) -Action { Open-Monitor }))

# ─ API Server ─
$apiHeader = New-Object System.Windows.Forms.Panel
$apiHeader.Location = New-Object System.Drawing.Point(0, 415)
$apiHeader.Size = New-Object System.Drawing.Size(898, 30)
$apiHeader.BackColor = $headerBg
$rightPanel.Controls.Add($apiHeader)

$lblApiTitle = New-Object System.Windows.Forms.Label
$lblApiTitle.Text = "API SERVER"
$lblApiTitle.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblApiTitle.ForeColor = $neonCyan
$lblApiTitle.Location = New-Object System.Drawing.Point(15, 6)
$lblApiTitle.AutoSize = $true
$apiHeader.Controls.Add($lblApiTitle)

$apiPanel = New-Object System.Windows.Forms.Panel
$apiPanel.Location = New-Object System.Drawing.Point(15, 450)
$apiPanel.Size = New-Object System.Drawing.Size(870, 160)
$apiPanel.BackColor = $dark
$rightPanel.Controls.Add($apiPanel)

$global:btnApi = New-CyberButton -Text "INICIAR" -X 10 -Y 10 -W 120 -H 35 -Color $neonBlue -Action { Toggle-Api }
$apiPanel.Controls.Add($global:btnApi)

$global:lblApiStatus = New-Object System.Windows.Forms.Label
$global:lblApiStatus.Text = "Detenido"
$global:lblApiStatus.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$global:lblApiStatus.ForeColor = [System.Drawing.Color]::Gray
$global:lblApiStatus.Location = New-Object System.Drawing.Point(140, 18)
$global:lblApiStatus.AutoSize = $true
$apiPanel.Controls.Add($global:lblApiStatus)

$global:txtLog = New-Object System.Windows.Forms.TextBox
$global:txtLog.Location = New-Object System.Drawing.Point(10, 55)
$global:txtLog.Size = New-Object System.Drawing.Size(850, 95)
$global:txtLog.Multiline = $true
$global:txtLog.BackColor = [System.Drawing.Color]::White
$global:txtLog.ForeColor = [System.Drawing.Color]::Black
$global:txtLog.Font = New-Object System.Drawing.Font("Cascadia Code", 9)
$global:txtLog.ReadOnly = $true
$global:txtLog.BorderStyle = "Fixed3D"
$global:txtLog.ScrollBars = "Vertical"
$apiPanel.Controls.Add($global:txtLog)

# ─── Status Bar ──────────────────────────────────────────────────────────────
$statusBar = New-Object System.Windows.Forms.StatusStrip
$statusBar.BackColor = $darkest
$statusBar.ForeColor = $textDim
$statusBar.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = "Listo"
$statusLabel.ForeColor = $textDim
$statusBar.Items.Add($statusLabel) | Out-Null

$statusTime = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusTime.Text = ""
$statusTime.ForeColor = $textDim
$statusTime.Alignment = "Right"
$statusBar.Items.Add($statusTime) | Out-Null

$form.Controls.Add($statusBar)

# Update clock
$clockTimer = New-Object System.Windows.Forms.Timer
$clockTimer.Interval = 1000
$clockTimer.Add_Tick({ $statusTime.Text = Get-Date -Format "HH:mm:ss  dd/MM/yyyy" })
$clockTimer.Start()

# ─── Global Vars ─────────────────────────────────────────────────────────────
$global:apiProcess = $null
$global:apiTimer = $null

# ─── Functions ────────────────────────────────────────────────────────────────
function Invoke-PingSweep {
    param([string]$Subnet, [string[]]$ExtraIps = @())
    $targets = New-Object System.Collections.Generic.List[string]
    1..100 | ForEach-Object { $targets.Add("$Subnet.$_") }
    foreach ($ip in $ExtraIps) { if ($ip) { $targets.Add($ip) } }
    $pings = New-Object System.Collections.Generic.List[System.Net.NetworkInformation.Ping]
    $tasks = New-Object System.Collections.Generic.List[System.Threading.Tasks.Task]
    foreach ($ip in $targets) {
        try {
            $p = [System.Net.NetworkInformation.Ping]::new()
            $pings.Add($p)
            $tasks.Add($p.SendPingAsync($ip, 60))
        } catch {}
    }
    if ($tasks.Count -gt 0) {
        try { [System.Threading.Tasks.Task]::WaitAll($tasks.ToArray(), 5000) } catch {}
    }
    foreach ($p in $pings) { try { $p.Dispose() } catch {} }
}

function Get-RouterIP {
    $router = $global:config.Computers | Where-Object { $_.Name -match 'router' } | Select-Object -First 1
    if ($router -and $router.IP) { return $router.IP }
    try {
        $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -First 1).NextHop
        if ($gw) { return $gw }
    } catch {}
    return "$($global:config.SubnetPrefix).1"
}

function Test-IsLocalIP {
    param([string]$Ip)
    $local = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -ne '127.0.0.1' } |
        Select-Object -ExpandProperty IPAddress)
    return ($local -contains $Ip)
}

function Start-NetworkScan {
    if ($global:scanning) { return }
    $global:scanning = $true
    $global:lblStatus.Text = "[ Escaneando... ]"
    $global:deviceList.Items.Clear()
    $btnScan.Enabled = $false
    [System.Windows.Forms.Application]::DoEvents()
    
    if (-not $global:config) {
        $global:lblStatus.Text = "[ Error: config no cargada ]"
        $btnScan.Enabled = $true; $global:scanning = $false; return
    }
    
    $subnet = $global:config.SubnetPrefix
    
    # STEP 1: Ping sweep to refresh ARP (1..100 fast, then sparse beyond)
    $global:lblStatus.Text = "[ Ping sweep... ]"
    [System.Windows.Forms.Application]::DoEvents()
    $extraIps = $global:config.Computers | Where-Object { $_.IP } | ForEach-Object {
        $ipParts = $_.IP -split '\.'
        if ([int]$ipParts[3] -gt 100) { $_.IP }
    }
    Invoke-PingSweep -Subnet $subnet -ExtraIps $extraIps
    
    # STEP 2: Read all ARP entries (any state)
    $arpTable = Get-NetNeighbor | Where-Object {
        $_.IPAddress -match "^$([regex]::Escape($subnet))\." -and
        $_.LinkLayerAddress -and $_.LinkLayerAddress -ne "00-00-00-00-00-00" -and $_.LinkLayerAddress -ne "FF-FF-FF-FF-FF-FF"
    }
    
    $macToIp = @{}
    foreach ($entry in $arpTable) {
        $mac = $entry.LinkLayerAddress.ToLower() -replace "-", ":"
        $macToIp[$mac] = $entry.IPAddress
    }
    
    # STEP 3: Check each configured device
    $changed = $false
    $online = 0; $offline = 0
    $seenIps = @{}  # track which IPs already shown
    
    foreach ($pc in $global:config.Computers) {
        $name = $pc.Name; $cfgIp = $pc.IP; $isPhone = ($pc.Type -eq "phone")
        $pcMac = if ($pc.MAC) { $pc.MAC.ToLower() } else { $null }
        
        # Resolve actual IP: MAC → ARP → fallback
        $actualIp = $null
        if ($name -match "^$([regex]::Escape($env:COMPUTERNAME))" -or (Test-IsLocalIP $cfgIp)) {
            $localIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -match "^$([regex]::Escape($subnet))\." } | Select-Object -First 1).IPAddress
            if ($localIp) { $actualIp = $localIp }
        }
        if ($pcMac -and $macToIp.ContainsKey($pcMac)) { $actualIp = $macToIp[$pcMac] }
        if (-not $actualIp -and $name -eq "CORE0") {
            $cm = ($global:config.Core0MAC -replace "-", ":").ToLower()
            if ($macToIp.ContainsKey($cm)) { $actualIp = $macToIp[$cm] }
        }
        if (-not $actualIp -and $global:config.KnownMacs) {
            foreach ($km in $global:config.KnownMacs.PSObject.Properties) {
                if ($km.Value -eq $name) {
                    $k = $km.Name.ToLower()
                    if ($macToIp.ContainsKey($k)) { $actualIp = $macToIp[$k]; break }
                }
            }
        }
        if (-not $actualIp) { $actualIp = $cfgIp }
        
        # Auto-update config
        if ($actualIp -ne $cfgIp) { $pc.IP = $actualIp; $changed = $true }
        
        # Online check: ping + TCP fallback
        $isOnline = $false; $viaTcp = $false
        if ($name -match "^$([regex]::Escape($env:COMPUTERNAME))" -or (Test-IsLocalIP $actualIp)) {
            $isOnline = $true
        } else {
            try { $r = [System.Net.NetworkInformation.Ping]::new().Send($actualIp, 150); if ($r.Status -eq "Success") { $isOnline = $true } } catch {}
        }
        [System.Windows.Forms.Application]::DoEvents()
        
        if (-not $isOnline) {
            $port = if ($isPhone) { 5555 } else { 5985 }
            try {
                $t = New-Object System.Net.Sockets.TcpClient
                $c = $t.BeginConnect($actualIp, $port, $null, $null)
                if ($c.AsyncWaitHandle.WaitOne(300)) { $isOnline = $true; $viaTcp = $true; $t.EndConnect($c) }
                $t.Close()
            } catch {}
            [System.Windows.Forms.Application]::DoEvents()
        }
        
        # Render
        $st = if ($isOnline) { "Conectado" } else { "Offline" }
        if ($isOnline) {
            $clr = if ($viaTcp) { [System.Drawing.Color]::FromArgb(0, 0, 200) } else { $neonGreen }
        } else { $clr = [System.Drawing.Color]::FromArgb(120, 120, 140) }
        
        $it = New-Object System.Windows.Forms.ListViewItem($name)
        $it.SubItems.Add($actualIp) | Out-Null
        $it.SubItems.Add($st) | Out-Null
        $it.Tag = @{ IP = $actualIp; Host = $name; Status = $st; Phone = $isPhone }
        $it.ForeColor = $clr
        $global:deviceList.Items.Add($it) | Out-Null
        $seenIps[$actualIp] = $true
        if ($isOnline) { $online++ } else { $offline++ }
    }
    
    # STEP 4: Show unknown devices found in ARP (not in config)
    $unknownColor = [System.Drawing.Color]::FromArgb(128, 128, 0)
    foreach ($entry in $arpTable) {
        $ip = $entry.IPAddress
        if ($seenIps.ContainsKey($ip)) { continue }
        $seenIps[$ip] = $true
        
        # DNS resolution for hostname
        $devName = $ip
        try {
            $dnsEntry = [System.Net.Dns]::GetHostEntry($ip)
            if ($dnsEntry.HostName -and $dnsEntry.HostName -ne $ip) { $devName = $dnsEntry.HostName }
        } catch {}
        
        # Quick online check
        $isOnline = $false
        try { $r = [System.Net.NetworkInformation.Ping]::new().Send($ip, 200); if ($r.Status -eq "Success") { $isOnline = $true } } catch {}
        if (-not $isOnline) { try { $t = New-Object System.Net.Sockets.TcpClient; $c = $t.BeginConnect($ip, 445, $null, $null); if ($c.AsyncWaitHandle.WaitOne(200)) { $isOnline = $true; $t.EndConnect($c) }; $t.Close() } catch {} }
        
        $st = if ($isOnline) { "Conectado" } else { "Offline" }
        $it = New-Object System.Windows.Forms.ListViewItem($devName)
        $it.SubItems.Add($ip) | Out-Null
        $it.SubItems.Add($st) | Out-Null
        $it.Tag = @{ IP = $ip; Host = $devName; Status = $st; Phone = $false }
        $it.ForeColor = $unknownColor
        $global:deviceList.Items.Add($it) | Out-Null
        if ($isOnline) { $online++ } else { $offline++ }
        [System.Windows.Forms.Application]::DoEvents()
    }
    
    # Save config if IPs changed (already updated in-memory above)
    if ($changed) {
        $global:config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
        $global:lblStatus.Text = "Online: $online | Offline: $offline [IPs actualizadas]"
    } else {
        $global:lblStatus.Text = "Online: $online | Offline: $offline"
    }
    
    $btnScan.Enabled = $true
    $global:scanning = $false
}

# ─── Resolve device IP by MAC before any action ─────────────────────────────
function Resolve-DeviceIP {
    param($device)
    $hostname = $device.Host
    $currentIp = $device.IP
    if ($currentIp -eq (Get-RouterIP) -or (Test-IsLocalIP $currentIp)) { return $currentIp }
    
    # Get MAC for this device
    $pcCfg = $global:config.Computers | Where-Object { $_.Name -eq $hostname }
    $devMac = $null
    if ($pcCfg -and $pcCfg.MAC) { $devMac = $pcCfg.MAC.ToLower() }
    if (-not $devMac -and $hostname -eq "CORE0") { $devMac = ($global:config.Core0MAC -replace "-", ":").ToLower() }
    if (-not $devMac) { return $currentIp }
    
    # Quick ping sweep to refresh ARP (parallel)
    $subnet = $global:config.SubnetPrefix
    Invoke-PingSweep -Subnet $subnet
    
    # Look up MAC in ARP
    $arpEntry = Get-NetNeighbor | Where-Object {
        $_.IPAddress -match "^$([regex]::Escape($subnet))\." -and
        ($_.LinkLayerAddress.ToLower() -replace "-", ":") -eq $devMac -and
        $_.LinkLayerAddress -ne "00-00-00-00-00-00"
    }
    
    if ($arpEntry) {
        $realIp = $arpEntry[0].IPAddress
        if ($realIp -ne $currentIp) {
            # Auto-update config silently
            if ($pcCfg) { $pcCfg.IP = $realIp }
            $global:config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
            $global:config = Get-Content $configPath -Raw | ConvertFrom-Json
            $global:lblStatus.Text = "[ $hostname → $realIp ]"
        }
        return $realIp
    }
    return $currentIp
}

# ─── Force detection for a single device ─────────────────────────────────────
function Force-Detect {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $hostname = $global:selectedDevice.Host
    $ip = $global:selectedDevice.IP
    [System.Windows.Forms.Application]::DoEvents()
    
    # Ping sweep to refresh ARP (parallel)
    $subnet = $global:config.SubnetPrefix
    Invoke-PingSweep -Subnet $subnet
    
    # Search for this device's MAC in ARP
    $foundIp = $null
    $pcCfg = $global:config.Computers | Where-Object { $_.Name -eq $hostname }
    $devMac = $null
    if ($pcCfg -and $pcCfg.MAC) { $devMac = $pcCfg.MAC.ToLower() }
    if (-not $devMac -and $hostname -eq "CORE0") { $devMac = ($global:config.Core0MAC -replace "-", ":").ToLower() }
    
    if ($devMac) {
        $arpEntry = Get-NetNeighbor | Where-Object {
            $_.IPAddress -match "^$([regex]::Escape($subnet))\." -and
            ($_.LinkLayerAddress.ToLower() -replace "-", ":") -eq $devMac -and
            $_.LinkLayerAddress -ne "00-00-00-00-00-00"
        }
        if ($arpEntry) { $foundIp = $arpEntry[0].IPAddress }
    }
    
    if ($foundIp) {
        # Update config
        $global:lblStatus.Text = "[ $hostname detectado en $foundIp ]"
        if ($pcCfg) { $pcCfg.IP = $foundIp }
        $global:config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
        $global:config = Get-Content $configPath -Raw | ConvertFrom-Json
        Start-NetworkScan
        return
    }
    
    # Try TCP ping to the configured IP directly
    $isOnline = $false
    try { $r = [System.Net.NetworkInformation.Ping]::new().Send($ip, 500); if ($r.Status -eq "Success") { $isOnline = $true } } catch {}
    if (-not $isOnline) {
        $port = if ($global:selectedDevice.Phone) { 5555 } else { 5985 }
        try {
            $t = New-Object System.Net.Sockets.TcpClient
            $c = $t.BeginConnect($ip, $port, $null, $null)
            if ($c.AsyncWaitHandle.WaitOne(500)) { $isOnline = $true; $viaTcp = $true; $t.EndConnect($c) }
            $t.Close()
        } catch {}
    }
    
    if ($isOnline) {
        $global:lblStatus.Text = "[ $hostname responde en $ip ]"
    } else {
        [System.Windows.Forms.MessageBox]::Show("$hostname no responde en $ip`nMAC: $devMac`nARP: No encontrada`nVerificar conexion fisica", "Deteccion fallida")
        $global:lblStatus.Text = "[ $hostname no detectado ]"
    }
    Start-NetworkScan
}

function Show-DeviceInfo {
    if ($global:deviceList.SelectedItems.Count -eq 0) { return }
    $item = $global:deviceList.SelectedItems[0]
    $global:selectedDevice = $item.Tag
    $ip = $global:selectedDevice.IP
    $hostname = $global:selectedDevice.Host
    $status = $global:selectedDevice.Status
    
    # Get MAC info from ARP
    $arpMatch = Get-NetNeighbor | Where-Object { $_.IPAddress -eq $ip -and $_.LinkLayerAddress -and $_.LinkLayerAddress -ne "00-00-00-00-00-00" }
    $macStr = if ($arpMatch) { $arpMatch[0].LinkLayerAddress.ToLower() -replace "-", ":" } else { "No encontrada en ARP" }
    
    # Config vs actual IP
    $pcCfg = $global:config.Computers | Where-Object { $_.Name -eq $hostname }
    $cfgIp = if ($pcCfg) { $pcCfg.IP } else { "-" }
    $ipMismatch = if ($cfgIp -ne $ip -and $cfgIp -ne "-") { " <<< DIFERENTE!" } else { "" }
    
    $info = "+" + ("=" * 50) + "+`n"
    $info += "|  " + $hostname.PadRight(46) + " |`n"
    $info += "+" + ("=" * 50) + "+`n"
    $info += "|  IP actual:   " + $ip.PadRight(34) + " |`n"
    $info += "|  IP config:   " + ($cfgIp + $ipMismatch).PadRight(34) + " |`n"
    $info += "|  MAC:         " + $macStr.PadRight(34) + " |`n"
    $info += "|  Estado:      " + $status.PadRight(34) + " |`n"
    
    if ($pcCfg) {
        if ($pcCfg.OS) { $info += "|  SO:          " + ([string]$pcCfg.OS).PadRight(34) + " |`n" }
        if ($pcCfg.OpenPorts) { $info += "|  Puertos:     " + ([string]$pcCfg.OpenPorts).PadRight(34) + " |`n" }
    }
    
    $info += "+" + ("=" * 50) + "+`n"
    $info += "|  ACCIONES DISPONIBLES:" + (" " * 31) + " |`n"
    $info += "|  [1] Shell remoto" + (" " * 34) + " |`n"
    $info += "|  [2] Explorar archivos" + (" " * 31) + " |`n"
    $info += "|  [3] Wake-on-LAN" + (" " * 37) + " |`n"
    $info += "|  [4] Voz remota" + (" " * 38) + " |`n"
    $info += "|  [5] Chat en tiempo real" + (" " * 29) + " |`n"
    $info += "|  [6] Acceso remoto (TV/RDP/Capture)" + (" " * 21) + " |`n"
    if ($status -eq "Offline") {
        $info += "|" + (" " * 50) + "|`n"
        $info += "|  [!] Offline? Prueba: Forzar deteccion (click derecho)" + " |`n"
    }
    $info += "+" + ("=" * 50) + "+"
    
    $global:txtInfo.Text = $info
}

function Open-Files {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $ip = Resolve-DeviceIP $global:selectedDevice
    $name = $global:selectedDevice.Host
    $isPhone = $global:selectedDevice.Phone
    
    # Router: abrir admin web (HTTP)
    if ($ip -eq (Get-RouterIP)) {
        Start-Process "http://$ip"
        return
    }
    
    # Phone: usar ADB Explorer
    if ($isPhone) {
        $adb = "$env:LOCALAPPDATA\AndroidPlatformTools\platform-tools\adb.exe"
        if (-not (Test-Path $adb)) {
            [System.Windows.Forms.MessageBox]::Show("ADB no encontrado en $adb`nInstale platform-tools", "ADB no disponible")
            return
        }
        Start-Process powershell.exe -WindowStyle Normal -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$projectPath\ADB-Explorer.ps1", "-IP", $ip, "-ADB", $adb
        return
    }
    
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$projectPath\Explorer_Agent.ps1`" -ComputerName $ip"
}

function Open-Shell {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $ip = Resolve-DeviceIP $global:selectedDevice
    if (Test-IsLocalIP $ip) { [System.Windows.Forms.MessageBox]::Show("Use PowerShell directo"); return }
    
    $isPhone = $global:selectedDevice.Phone
    if ($isPhone) {
        $adb = "$env:LOCALAPPDATA\AndroidPlatformTools\platform-tools\adb.exe"
        if (-not (Test-Path $adb)) {
            [System.Windows.Forms.MessageBox]::Show("ADB no encontrado en $adb`nInstale platform-tools", "ADB no disponible")
            return
        }
        $scriptPath = "$env:TEMP\adb_shell_$PID.ps1"
        $content = @"
`$adb = "$adb"
`$ip = "$ip"
& `$adb connect `$ip 2>`$null
Write-Host "=== ADB Shell (`$ip) ===" -ForegroundColor Cyan
& `$adb -s `$ip shell
"@
        [System.IO.File]::WriteAllText($scriptPath, $content, [System.Text.Encoding]::UTF8)
        Start-Process powershell.exe -WindowStyle Normal -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $scriptPath
        return
    }
    
    $credFile = "$projectPath\core0-cred.xml"
    if (Test-Path $credFile) {
        $arg = "-NoExit -Command `"Enter-PSSession -ComputerName '$ip' -Credential (Import-Clixml '$credFile')`""
    } else {
        $arg = "-NoExit -Command `"Enter-PSSession -ComputerName '$ip'`""
    }
    Start-Process powershell.exe -ArgumentList $arg
}

function Send-WoL {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $mac = $global:config.Core0MAC
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -Command `"Import-Module '$projectPath\NetworkUtilsPublic.psm1'; Send-WakeOnLan -MACAddress '$mac'`""
    [System.Windows.Forms.MessageBox]::Show("WoL enviado", "WOL")
}

function Open-Voice {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $ip = Resolve-DeviceIP $global:selectedDevice
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$projectPath\Speak-Remote.ps1`" -ComputerName $ip"
}

function Open-Intercom {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $ip = Resolve-DeviceIP $global:selectedDevice
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$projectPath\Intercom.ps1`" -ComputerName $ip"
}

function Open-Monitor {
    if (-not $global:selectedDevice) { [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo"); return }
    $ip = Resolve-DeviceIP $global:selectedDevice
        if (Test-IsLocalIP $ip) { [System.Windows.Forms.MessageBox]::Show("No soportado en local"); return }
    $isPhone = $global:selectedDevice.Phone
    if ($isPhone) {
        $tvExe = "C:\Program Files\TeamViewer\TeamViewer.exe"
        if (-not (Test-Path $tvExe)) { $tvExe = "C:\Program Files (x86)\TeamViewer\TeamViewer.exe" }
        if (Test-Path $tvExe) {
            $result = [System.Windows.Forms.MessageBox]::Show("TeamViewer detectado localmente.`nSeleccionar metodo al conectar.", "Acceso Remoto", "OKCancel")
            if ($result -eq "Cancel") { return }
        }
    }
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$projectPath\RemoteMonitor.ps1`" -ComputerName $ip" -WindowStyle Normal
}

function Toggle-Api {
    if ($global:apiProcess -eq $null) {
        $global:apiProcess = Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-ExecutionPolicy Bypass -File `"$projectPath\API-Server.ps1`"" -PassThru -RedirectStandardOutput "$projectPath\temp_api.log"
        $global:btnApi.Text = "DETENER"
        $global:btnApi.ForeColor = [System.Drawing.Color]::FromArgb(180, 0, 0)
        $global:lblApiStatus.Text = "Ejecutando"
        $global:lblApiStatus.ForeColor = $neonGreen
        
        if ($global:apiTimer) { try { $global:apiTimer.Stop(); $global:apiTimer.Dispose() } catch {} }
        $global:apiTimer = New-Object System.Windows.Forms.Timer
        $global:apiTimer.Interval = 500
        $global:apiTimer.Add_Tick({
            try {
                if (Test-Path "$projectPath\temp_api.log") {
                    $log = Get-Content "$projectPath\temp_api.log" -Tail 3 -ErrorAction SilentlyContinue
                    if ($log -and $global:txtLog) { $global:txtLog.AppendText(($log -join "`n") + "`n") }
                }
                if ($global:apiProcess -ne $null -and $global:apiProcess.HasExited) {
                    $global:btnApi.Text = "INICIAR"
                    $global:btnApi.ForeColor = [System.Drawing.Color]::Black
                    $global:lblApiStatus.Text = "Detenido"
                    $global:lblApiStatus.ForeColor = [System.Drawing.Color]::Gray
                    $global:apiProcess = $null
                    $global:apiTimer.Stop()
                    $global:apiTimer.Dispose()
                    $global:apiTimer = $null
                }
            } catch {}
        })
        $global:apiTimer.Start()
    } else {
        try { if (-not $global:apiProcess.HasExited) { $global:apiProcess.Kill() } } catch {}
        $global:apiProcess = $null
        if ($global:apiTimer) { try { $global:apiTimer.Stop(); $global:apiTimer.Dispose() } catch {} }
        $global:apiTimer = $null
        $global:btnApi.Text = "INICIAR"
        $global:btnApi.ForeColor = [System.Drawing.Color]::Black
        $global:lblApiStatus.Text = "Detenido"
        $global:lblApiStatus.ForeColor = [System.Drawing.Color]::Gray
    }
}

$form.Add_Shown({
    $startTimer = New-Object System.Windows.Forms.Timer
    $startTimer.Interval = 300
    $startTimer.Add_Tick({
        $this.Stop()
        $this.Dispose()
        try { Toggle-Api } catch {}
        try { Start-NetworkScan } catch {}
    })
    $startTimer.Start()
})

if ($Minimized) {
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
}

try {
    [System.Windows.Forms.Application]::Run($form)
} finally {
    # Limpieza al cerrar: matar SOLO procesos hijos de esta GUI
    # (los lanzados con -File "...LocalNetworkAgent\*.ps1" o desde $projectPath),
    # nunca otras ventanas PowerShell del usuario.
    try {
        $mypid = $PID
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessId -ne $mypid -and
                $_.CommandLine -and
                $_.CommandLine -match [regex]::Escape($projectPath)
            } |
            ForEach-Object {
                Write-Host "Cerrando proceso residual PID $($_.ProcessId)..."
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
    } catch {}

    if ($global:apiProcess -ne $null) {
        try { if (-not $global:apiProcess.HasExited) { $global:apiProcess.Kill() } } catch {}
    }
}