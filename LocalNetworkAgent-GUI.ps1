param([switch]$Minimized = $false)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$configPath = Join-Path $projectPath "network-config.json"
$credPath = Join-Path $projectPath "core0-cred.xml"

$global:devices = @()
$global:scanning = $false
$global:selectedDevice = $null

if (Test-Path $configPath) {
    $global:config = Get-Content $configPath -Raw | ConvertFrom-Json
}

if (Test-Path $credPath) {
    $global:cred = Import-CliXml $credPath
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Local Network Agent v2.2.0"
$form.Size = New-Object System.Drawing.Size(1120, 680)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "Fixed3D"
$form.MaximizeBox = $false
$form.MinimizeBox = $true

$global:titlePanel = New-Object System.Windows.Forms.Panel
$global:titlePanel.Location = New-Object System.Drawing.Point(0, 0)
$global:titlePanel.Size = New-Object System.Drawing.Size(1120, 65)
$global:titlePanel.BackColor = [System.Drawing.Color]::FromArgb(45, 45, 60)
$global:titlePanel.BorderStyle = "FixedSingle"

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "LOCAL NETWORK AGENT"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 217, 255)
$lblTitle.Location = New-Object System.Drawing.Point(20, 15)
$lblTitle.AutoSize = $true
$global:titlePanel.Controls.Add($lblTitle)

$btnScan = New-Object System.Windows.Forms.Button
$btnScan.Text = "ESCANEAR RED"
$btnScan.Location = New-Object System.Drawing.Point(850, 15)
$btnScan.Size = New-Object System.Drawing.Size(120, 35)
$btnScan.FlatStyle = "Flat"
$btnScan.FlatAppearance.BorderSize = 0
$btnScan.BackColor = [System.Drawing.Color]::FromArgb(0, 200, 83)
$btnScan.ForeColor = [System.Drawing.Color]::White
$btnScan.Add_Click({ Start-NetworkScan })
$global:titlePanel.Controls.Add($btnScan)

$form.Controls.Add($global:titlePanel)

$global:leftPanel = New-Object System.Windows.Forms.Panel
$global:leftPanel.Location = New-Object System.Drawing.Point(10, 70)
$global:leftPanel.Size = New-Object System.Drawing.Size(300, 570)
$global:leftPanel.BackColor = [System.Drawing.Color]::FromArgb(35, 35, 50)
$global:leftPanel.BorderStyle = "FixedSingle"

$lblDevices = New-Object System.Windows.Forms.Label
$lblDevices.Text = "DISPOSITIVOS EN RED"
$lblDevices.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblDevices.ForeColor = [System.Drawing.Color]::Cyan
$lblDevices.Location = New-Object System.Drawing.Point(10, 10)
$lblDevices.AutoSize = $true
$global:leftPanel.Controls.Add($lblDevices)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Clique en Escanear para buscar"
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$lblStatus.ForeColor = [System.Drawing.Color]::Silver
$lblStatus.Location = New-Object System.Drawing.Point(10, 35)
$lblStatus.AutoSize = $true
$global:leftPanel.Controls.Add($lblStatus)

$global:deviceList = New-Object System.Windows.Forms.ListView
$global:deviceList.Location = New-Object System.Drawing.Point(10, 60)
$global:deviceList.Size = New-Object System.Drawing.Size(280, 500)
$global:deviceList.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 40)
$global:deviceList.ForeColor = [System.Drawing.Color]::White
$global:deviceList.FullRowSelect = $true
$global:deviceList.View = "Details"
$global:deviceList.Columns.Add("Nombre", 130)
$global:deviceList.Columns.Add("IP", 80)
$global:deviceList.Columns.Add("Estado", 50)
$global:deviceList.Add_DoubleClick({ Show-DeviceInfo })
$global:leftPanel.Controls.Add($global:deviceList)

$form.Controls.Add($global:leftPanel)

$global:rightPanel = New-Object System.Windows.Forms.Panel
$global:rightPanel.Location = New-Object System.Drawing.Point(320, 70)
$global:rightPanel.Size = New-Object System.Drawing.Size(770, 570)
$global:rightPanel.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)

$global:infoPanel = New-Object System.Windows.Forms.Panel
$global:infoPanel.Location = New-Object System.Drawing.Point(0, 0)
$global:infoPanel.Size = New-Object System.Drawing.Size(770, 180)
$global:infoPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$global:infoPanel.BorderStyle = "FixedSingle"

$lblInfoTitle = New-Object System.Windows.Forms.Label
$lblInfoTitle.Text = "INFORMACION DEL DISPOSITIVO"
$lblInfoTitle.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblInfoTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 217, 255)
$lblInfoTitle.Location = New-Object System.Drawing.Point(10, 10)
$lblInfoTitle.AutoSize = $true
$global:infoPanel.Controls.Add($lblInfoTitle)

$global:lblInfo = New-Object System.Windows.Forms.Label
$global:lblInfo.Text = "Seleccione un dispositivo de la lista"
$global:lblInfo.Font = New-Object System.Drawing.Font("Consolas", 9)
$global:lblInfo.ForeColor = [System.Drawing.Color]::Silver
$global:lblInfo.Location = New-Object System.Drawing.Point(10, 40)
$global:lblInfo.Size = New-Object System.Drawing.Size(750, 130)
$global:infoPanel.Controls.Add($global:lblInfo)

$global:rightPanel.Controls.Add($global:infoPanel)

$global:actionPanel = New-Object System.Windows.Forms.Panel
$global:actionPanel.Location = New-Object System.Drawing.Point(0, 190)
$global:actionPanel.Size = New-Object System.Drawing.Size(770, 70)
$global:actionPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$global:actionPanel.BorderStyle = "FixedSingle"

$lblActions = New-Object System.Windows.Forms.Label
$lblActions.Text = "ACCIONES"
$lblActions.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblActions.ForeColor = [System.Drawing.Color]::Cyan
$lblActions.Location = New-Object System.Drawing.Point(10, 8)
$lblActions.AutoSize = $true
$global:actionPanel.Controls.Add($lblActions)

$btnFiles = New-Object System.Windows.Forms.Button
$btnFiles.Text = "ARCHIVOS"
$btnFiles.Location = New-Object System.Drawing.Point(10, 32)
$btnFiles.Size = New-Object System.Drawing.Size(90, 30)
$btnFiles.FlatStyle = "Flat"
$btnFiles.FlatAppearance.BorderSize = 0
$btnFiles.BackColor = [System.Drawing.Color]::FromArgb(255, 184, 108)
$btnFiles.ForeColor = [System.Drawing.Color]::Black
$btnFiles.Add_Click({ Open-Files })
$global:actionPanel.Controls.Add($btnFiles)

$btnShell = New-Object System.Windows.Forms.Button
$btnShell.Text = "SHELL"
$btnShell.Location = New-Object System.Drawing.Point(110, 32)
$btnShell.Size = New-Object System.Drawing.Size(90, 30)
$btnShell.FlatStyle = "Flat"
$btnShell.FlatAppearance.BorderSize = 0
$btnShell.BackColor = [System.Drawing.Color]::FromArgb(255, 121, 198)
$btnShell.ForeColor = [System.Drawing.Color]::Black
$btnShell.Add_Click({ Open-Shell })
$global:actionPanel.Controls.Add($btnShell)

$btnWoL = New-Object System.Windows.Forms.Button
$btnWoL.Text = "WOL"
$btnWoL.Location = New-Object System.Drawing.Point(210, 32)
$btnWoL.Size = New-Object System.Drawing.Size(90, 30)
$btnWoL.FlatStyle = "Flat"
$btnWoL.FlatAppearance.BorderSize = 0
$btnWoL.BackColor = [System.Drawing.Color]::FromArgb(0, 200, 83)
$btnWoL.ForeColor = [System.Drawing.Color]::White
$btnWoL.Add_Click({ Send-WoL })
$global:actionPanel.Controls.Add($btnWoL)

$btnSpeak = New-Object System.Windows.Forms.Button
$btnSpeak.Text = "VOZ"
$btnSpeak.Location = New-Object System.Drawing.Point(310, 32)
$btnSpeak.Size = New-Object System.Drawing.Size(90, 30)
$btnSpeak.FlatStyle = "Flat"
$btnSpeak.FlatAppearance.BorderSize = 0
$btnSpeak.BackColor = [System.Drawing.Color]::FromArgb(255, 87, 34)
$btnSpeak.ForeColor = [System.Drawing.Color]::White
$btnSpeak.Add_Click({ Open-Voice })
$global:actionPanel.Controls.Add($btnSpeak)

$btnIntercom = New-Object System.Windows.Forms.Button
$btnIntercom.Text = "CHAT"
$btnIntercom.Location = New-Object System.Drawing.Point(410, 32)
$btnIntercom.Size = New-Object System.Drawing.Size(90, 30)
$btnIntercom.FlatStyle = "Flat"
$btnIntercom.FlatAppearance.BorderSize = 0
$btnIntercom.BackColor = [System.Drawing.Color]::FromArgb(74, 42, 193)
$btnIntercom.ForeColor = [System.Drawing.Color]::White
$btnIntercom.Add_Click({ Open-Intercom })
$global:actionPanel.Controls.Add($btnIntercom)

$global:rightPanel.Controls.Add($global:actionPanel)

$global:apiPanel = New-Object System.Windows.Forms.Panel
$global:apiPanel.Location = New-Object System.Drawing.Point(0, 270)
$global:apiPanel.Size = New-Object System.Drawing.Size(770, 290)
$global:apiPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$global:apiPanel.BorderStyle = "FixedSingle"

$lblApi = New-Object System.Windows.Forms.Label
$lblApi.Text = "API SERVER"
$lblApi.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$lblApi.ForeColor = [System.Drawing.Color]::Cyan
$lblApi.Location = New-Object System.Drawing.Point(10, 8)
$lblApi.AutoSize = $true
$global:apiPanel.Controls.Add($lblApi)

$btnApi = New-Object System.Windows.Forms.Button
$btnApi.Text = "INICIAR API"
$btnApi.Location = New-Object System.Drawing.Point(10, 32)
$btnApi.Size = New-Object System.Drawing.Size(100, 30)
$btnApi.FlatStyle = "Flat"
$btnApi.FlatAppearance.BorderSize = 0
$btnApi.BackColor = [System.Drawing.Color]::FromArgb(15, 52, 96)
$btnApi.ForeColor = [System.Drawing.Color]::White
$btnApi.Add_Click({ Toggle-Api })
$global:apiPanel.Controls.Add($btnApi)

$global:lblApiStatus = New-Object System.Windows.Forms.Label
$global:lblApiStatus.Text = "API: Detenida"
$global:lblApiStatus.Font = New-Object System.Drawing.Font("Consolas", 8)
$global:lblApiStatus.ForeColor = [System.Drawing.Color]::Silver
$global:lblApiStatus.Location = New-Object System.Drawing.Point(120, 38)
$global:lblApiStatus.AutoSize = $true
$global:apiPanel.Controls.Add($global:lblApiStatus)

$global:txtLog = New-Object System.Windows.Forms.TextBox
$global:txtLog.Location = New-Object System.Drawing.Point(10, 70)
$global:txtLog.Size = New-Object System.Drawing.Size(750, 210)
$global:txtLog.Multiline = $true
$global:txtLog.BackColor = [System.Drawing.Color]::FromArgb(20, 20, 30)
$global:txtLog.ForeColor = [System.Drawing.Color]::Lime
$global:txtLog.Font = New-Object System.Drawing.Font("Consolas", 8)
$global:txtLog.ReadOnly = $true
$global:txtLog.ScrollBars = "Vertical"
$global:apiPanel.Controls.Add($global:txtLog)

$global:rightPanel.Controls.Add($global:apiPanel)

$form.Controls.Add($global:rightPanel)

function Start-NetworkScan {
    if ($global:scanning) { return }
    $global:scanning = $true
    
    $lblStatus.Text = "Buscando..."
    $global:deviceList.Items.Clear()
    $btnScan.Enabled = $false
    
    if (-not $global:config) {
        $lblStatus.Text = "Error config"
        $btnScan.Enabled = $true
        $global:scanning = $false
        return
    }
    
    $ips = @()
    $global:config.Computers | ForEach-Object { if ($_.IP) { $ips += $_.IP } }
    
    $lblStatus.Text = "Revisando $($ips.Count) equipos..."
    
    $results = @()
    foreach ($ip in $ips) {
        try {
            $p = New-Object System.Net.NetworkInformation.Ping
            $r = $p.Send($ip, 300)
            if ($r.Status -eq "Success") {
                $name = $ip
                try { $name = ([System.Net.Dns]::GetHostEntry($ip)).HostName } catch {}
                $results += @{ IP = $ip; Host = $name; Status = "Online" }
            }
            $p.Dispose()
        } catch {}
    }
    
    foreach ($res in $results) {
        $it = New-Object System.Windows.Forms.ListViewItem($res.Host)
        $it.SubItems.Add($res.IP) | Out-Null
        $it.SubItems.Add($res.Status) | Out-Null
        $it.Tag = $res
        $it.ForeColor = [System.Drawing.Color]::Lime
        $global:deviceList.Items.Add($it)
    }
    
    $lblStatus.Text = "Encontrados: $($results.Count)"
    $btnScan.Enabled = $true
    $global:scanning = $false
}

function Show-DeviceInfo {
    if ($global:deviceList.SelectedItems.Count -eq 0) { return }
    $item = $global:deviceList.SelectedItems[0]
    $global:selectedDevice = $item.Tag
    
    $info = "DISPOSITIVO: $($global:selectedDevice.Hostname)`n"
    $info += "IP: $($global:selectedDevice.IP)`n"
    $info += "ESTADO: $($global:selectedDevice.Status)`n`n"
    $info += "--- ACCIONES ---`n"
    $info += "Archivos: Navegar archivos`n"
    $info += "Shell: Consola remota`n"
    $info += "WoL: Encender equipo`n"
    $info += "Voz: Mensaje de voz`n"
    $info += "Chat: Chat en tiempo real"
    
    $global:lblInfo.Text = $info
}

function Open-Files {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    $ip = $global:selectedDevice.IP
    $name = $global:selectedDevice.Hostname
    Start-Process powershell.exe -ArgumentList "-NoExit -File `"$projectPath\Explorer_Agent.ps1`" -ComputerName $ip"
}

function Open-Shell {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -Command `"Import-Module '$projectPath\NetworkUtilsPublic.psm1'; Connect-RemoteComputer -ComputerName $($global:selectedDevice.IP)`"" -WindowStyle Hidden
}

function Send-WoL {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"Import-Module '$projectPath\NetworkUtilsPublic.psm1'; Send-WakeOnLan -MACAddress (Get-Content '$projectPath\network-config.json' | ConvertFrom-Json).Core0MAC`"" -WindowStyle Hidden
    [System.Windows.Forms.MessageBox]::Show("Paquete WoL enviado", "WoL")
}

function Open-Voice {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -File `"$projectPath\Speak-Remote.ps1`" -ComputerName $($global:selectedDevice.IP)" -WindowStyle Hidden
}

function Open-Intercom {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -File `"$projectPath\Intercom.ps1`" -ComputerName $($global:selectedDevice.IP)" -WindowStyle Hidden
}

$global:apiProcess = $null

function Toggle-Api {
    if ($global:apiProcess -eq $null) {
        $global:apiProcess = Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$projectPath\API-Server.ps1`"" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectPath\temp_api.log"
        $btnApi.Text = "DETENER API"
        $btnApi.BackColor = [System.Drawing.Color]::FromArgb(233, 69, 96)
        $global:lblApiStatus.Text = "API: Ejecutando"
        
        $timer = New-Object System.Windows.Forms.Timer
        $timer.Interval = 500
        $timer.Add_Tick({
            if (Test-Path "$projectPath\temp_api.log") {
                try {
                    $log = Get-Content "$projectPath\temp_api.log" -Tail 3 -ErrorAction SilentlyContinue
                    if ($log) {
                        $global:txtLog.AppendText(($log -join "`n") + "`n")
                    }
                } catch {}
            }
            if ($global:apiProcess.HasExited) {
                $btnApi.Text = "INICIAR API"
                $btnApi.BackColor = [System.Drawing.Color]::FromArgb(15, 52, 96)
                $global:lblApiStatus.Text = "API: Detenida"
                $global:apiProcess = $null
                $timer.Stop()
                $timer.Dispose()
            }
        })
        $timer.Start()
    } else {
        $global:apiProcess.Kill()
        $global:apiProcess = $null
        $btnApi.Text = "INICIAR API"
        $btnApi.BackColor = [System.Drawing.Color]::FromArgb(15, 52, 96)
        $global:lblApiStatus.Text = "API: Detenida"
    }
}

$form.Add_Shown({
    Start-NetworkScan
})

if ($Minimized) {
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
}

try {
    [System.Windows.Forms.Application]::Run($form)
} catch {
    Write-Host "Error: $_"
} finally {
    Start-Sleep -Seconds 1
}