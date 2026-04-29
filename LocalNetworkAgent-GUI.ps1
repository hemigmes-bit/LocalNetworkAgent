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
$form.Size = New-Object System.Drawing.Size(1200, 750)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)
$form.ForeColor = [System.Drawing.Color]::White

$titlePanel = New-Object System.Windows.Forms.Panel
$titlePanel.Dock = "Top"
$titlePanel.Height = 60
$titlePanel.BackColor = [System.Drawing.Color]::FromArgb(45, 45, 60)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "LOCAL NETWORK AGENT"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 217, 255)
$lblTitle.Location = New-Object System.Drawing.Point(20, 15)
$titlePanel.Controls.Add($lblTitle)

$btnScan = New-Object System.Windows.Forms.Button
$btnScan.Text = "ESCANEAR RED"
$btnScan.Location = New-Object System.Drawing.Point(950, 15)
$btnScan.Size = New-Object System.Drawing.Size(120, 35)
$btnScan.FlatStyle = "Flat"
$btnScan.BackColor = [System.Drawing.Color]::FromArgb(0, 200, 83)
$btnScan.ForeColor = [System.Drawing.Color]::White
$btnScan.Add_Click({ Start-NetworkScan })
$titlePanel.Controls.Add($btnScan)

$form.Controls.Add($titlePanel)

$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Dock = "Left"
$leftPanel.Width = 350
$leftPanel.BackColor = [System.Drawing.Color]::FromArgb(35, 35, 50)

$lblDevices = New-Object System.Windows.Forms.Label
$lblDevices.Text = "DISPOSITIVOS EN RED"
$lblDevices.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$lblDevices.ForeColor = [System.Drawing.Color]::Cyan
$lblDevices.Location = New-Object System.Drawing.Point(15, 15)
$leftPanel.Controls.Add($lblDevices)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Clique en 'Escanear' para buscar dispositivos"
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblStatus.ForeColor = [System.Drawing.Color]::Silver
$lblStatus.Location = New-Object System.Drawing.Point(15, 40)
$lblStatus.Width = 320
$leftPanel.Controls.Add($lblStatus)

$deviceList = New-Object System.Windows.Forms.ListView
$deviceList.Location = New-Object System.Drawing.Point(10, 70)
$deviceList.Size = New-Object System.Drawing.Size(330, 450)
$deviceList.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 40)
$deviceList.ForeColor = [System.Drawing.Color]::White
$deviceList.FullRowSelect = $true
$deviceList.View = "Details"
$deviceList.Columns.Add("Nombre", 150)
$deviceList.Columns.Add("IP", 100)
$deviceList.Columns.Add("Estado", 60)
$deviceList.Add_DoubleClick({ Show-DeviceInfo })
$leftPanel.Controls.Add($deviceList)

$form.Controls.Add($leftPanel)

$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Dock = "Fill"
$rightPanel.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)

$infoPanel = New-Object System.Windows.Forms.Panel
$infoPanel.Location = New-Object System.Drawing.Point(10, 10)
$infoPanel.Size = New-Object System.Drawing.Size(780, 200)
$infoPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$infoPanel.BorderStyle = "FixedSingle"

$lblInfoTitle = New-Object System.Windows.Forms.Label
$lblInfoTitle.Text = "INFORMACION DEL DISPOSITIVO"
$lblInfoTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$lblInfoTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 217, 255)
$lblInfoTitle.Location = New-Object System.Drawing.Point(10, 10)
$infoPanel.Controls.Add($lblInfoTitle)

$lblInfo = New-Object System.Windows.Forms.Label
$lblInfo.Text = "Seleccione un dispositivo de la lista"
$lblInfo.Font = New-Object System.Drawing.Font("Consolas", 10)
$lblInfo.ForeColor = [System.Drawing.Color]::Silver
$lblInfo.Location = New-Object System.Drawing.Point(10, 45)
$lblInfo.Size = New-Object System.Drawing.Size(750, 140)
$infoPanel.Controls.Add($lblInfo)

$rightPanel.Controls.Add($infoPanel)

$actionPanel = New-Object System.Windows.Forms.Panel
$actionPanel.Location = New-Object System.Drawing.Point(10, 220)
$actionPanel.Size = New-Object System.Drawing.Size(780, 80)
$actionPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$actionPanel.BorderStyle = "FixedSingle"

$lblActions = New-Object System.Windows.Forms.Label
$lblActions.Text = "ACCIONES"
$lblActions.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblActions.ForeColor = [System.Drawing.Color]::Cyan
$lblActions.Location = New-Object System.Drawing.Point(10, 8)
$actionPanel.Controls.Add($lblActions)

$btnFiles = New-Object System.Windows.Forms.Button
$btnFiles.Text = "ARCHIVOS"
$btnFiles.Location = New-Object System.Drawing.Point(10, 35)
$btnFiles.Size = New-Object System.Drawing.Size(100, 35)
$btnFiles.FlatStyle = "Flat"
$btnFiles.BackColor = [System.Drawing.Color]::FromArgb(255, 184, 108)
$btnFiles.ForeColor = [System.Drawing.Color]::Black
$btnFiles.Add_Click({ Open-Files })
$actionPanel.Controls.Add($btnFiles)

$btnShell = New-Object System.Windows.Forms.Button
$btnShell.Text = "SHELL"
$btnShell.Location = New-Object System.Drawing.Point(120, 35)
$btnShell.Size = New-Object System.Drawing.Size(100, 35)
$btnShell.FlatStyle = "Flat"
$btnShell.BackColor = [System.Drawing.Color]::FromArgb(255, 121, 198)
$btnShell.ForeColor = [System.Drawing.Color]::Black
$btnShell.Add_Click({ Open-Shell })
$actionPanel.Controls.Add($btnShell)

$btnWoL = New-Object System.Windows.Forms.Button
$btnWoL.Text = "WOL"
$btnWoL.Location = New-Object System.Drawing.Point(230, 35)
$btnWoL.Size = New-Object System.Drawing.Size(100, 35)
$btnWoL.FlatStyle = "Flat"
$btnWoL.BackColor = [System.Drawing.Color]::FromArgb(0, 200, 83)
$btnWoL.ForeColor = [System.Drawing.Color]::White
$btnWoL.Add_Click({ Send-WoL })
$actionPanel.Controls.Add($btnWoL)

$btnSpeak = New-Object System.Windows.Forms.Button
$btnSpeak.Text = "VOZ"
$btnSpeak.Location = New-Object System.Drawing.Point(340, 35)
$btnSpeak.Size = New-Object System.Drawing.Size(100, 35)
$btnSpeak.FlatStyle = "Flat"
$btnSpeak.BackColor = [System.Drawing.Color]::FromArgb(255, 87, 34)
$btnSpeak.ForeColor = [System.Drawing.Color]::White
$btnSpeak.Add_Click({ Open-Voice })
$actionPanel.Controls.Add($btnSpeak)

$btnIntercom = New-Object System.Windows.Forms.Button
$btnIntercom.Text = "CHAT"
$btnIntercom.Location = New-Object System.Drawing.Point(450, 35)
$btnIntercom.Size = New-Object System.Drawing.Size(100, 35)
$btnIntercom.FlatStyle = "Flat"
$btnIntercom.BackColor = [System.Drawing.Color]::FromArgb(74, 42, 193)
$btnIntercom.ForeColor = [System.Drawing.Color]::White
$btnIntercom.Add_Click({ Open-Intercom })
$actionPanel.Controls.Add($btnIntercom)

$rightPanel.Controls.Add($actionPanel)

$apiPanel = New-Object System.Windows.Forms.Panel
$apiPanel.Location = New-Object System.Drawing.Point(10, 310)
$apiPanel.Size = New-Object System.Drawing.Size(780, 150)
$apiPanel.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 55)
$apiPanel.BorderStyle = "FixedSingle"

$lblApi = New-Object System.Windows.Forms.Label
$lblApi.Text = "API SERVER"
$lblApi.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$lblApi.ForeColor = [System.Drawing.Color]::Cyan
$lblApi.Location = New-Object System.Drawing.Point(10, 8)
$apiPanel.Controls.Add($lblApi)

$btnApi = New-Object System.Windows.Forms.Button
$btnApi.Text = "INICIAR API"
$btnApi.Location = New-Object System.Drawing.Point(10, 35)
$btnApi.Size = New-Object System.Drawing.Size(120, 35)
$btnApi.FlatStyle = "Flat"
$btnApi.BackColor = [System.Drawing.Color]::FromArgb(15, 52, 96)
$btnApi.ForeColor = [System.Drawing.Color]::White
$btnApi.Add_Click({ Toggle-Api })
$apiPanel.Controls.Add($btnApi)

$lblApiStatus = New-Object System.Windows.Forms.Label
$lblApiStatus.Text = "API: Detenida"
$lblApiStatus.Font = New-Object System.Drawing.Font("Consolas", 9)
$lblApiStatus.ForeColor = [System.Drawing.Color]::Silver
$lblApiStatus.Location = New-Object System.Drawing.Point(140, 40)
$apiPanel.Controls.Add($lblApiStatus)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Location = New-Object System.Drawing.Point(10, 75)
$txtLog.Size = New-Object System.Drawing.Size(760, 70)
$txtLog.Multiline = $true
$txtLog.BackColor = [System.Drawing.Color]::FromArgb(20, 20, 30)
$txtLog.ForeColor = [System.Drawing.Color]::Lime
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 8)
$txtLog.ReadOnly = $true
$txtLog.ScrollBars = "Vertical"
$apiPanel.Controls.Add($txtLog)

$rightPanel.Controls.Add($apiPanel)

$form.Controls.Add($rightPanel)

function Start-NetworkScan {
    if ($global:scanning) { return }
    $global:scanning = $true
    $lblStatus.Text = "Escaneando red..."
    $deviceList.Items.Clear()
    $btnScan.Enabled = $false
    
    $subnet = $global:config.SubnetPrefix
    
    $script:scanJob = {
        param($sn)
        $results = @()
        for ($i = 1; $i -le 254; $i++) {
            $ip = "$sn.$i"
            try {
                $ping = New-Object System.Net.NetworkInformation.Ping
                $res = $ping.Send($ip, 200)
                if ($res.Status -eq "Success") {
                    $hostname = $ip
                    try { $hostname = [System.Net.Dns]::GetHostEntry($ip).HostName } catch {}
                    $results += [PSCustomObject]@{
                        IP = $ip
                        Hostname = $hostname
                        Status = "Online"
                    }
                }
            } catch {}
            $ping.Dispose()
        }
        $results
    }
    
    $job = Start-Job -ScriptBlock $script:scanJob -ArgumentList $subnet
    
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 1000
    $timer.Add_Tick({
        if ($job.State -eq "Completed") {
            $results = Receive-Job -Job $job
            foreach ($r in $results) {
                $item = New-Object System.Windows.Forms.ListViewItem($r.Hostname)
                $item.SubItems.Add($r.IP) | Out-Null
                $item.SubItems.Add($r.Status) | Out-Null
                $item.Tag = $r
                if ($r.Hostname -eq $r.IP) { $item.ForeColor = [System.Drawing.Color]::Yellow }
                else { $item.ForeColor = [System.Drawing.Color]::Lime }
                $deviceList.Items.Add($item)
            }
            $lblStatus.Text = "Encontrados: $($results.Count) dispositivos"
            $global:scanning = $false
            $btnScan.Enabled = $true
            $timer.Stop()
            $timer.Dispose()
            Remove-Job $job -Force
        }
    })
    $timer.Start()
}

function Show-DeviceInfo {
    if ($deviceList.SelectedItems.Count -eq 0) { return }
    $item = $deviceList.SelectedItems[0]
    $global:selectedDevice = $item.Tag
    
    $info = "DISPOSITIVO: $($global:selectedDevice.Hostname)`n"
    $info += "IP: $($global:selectedDevice.IP)`n"
    $info += "ESTADO: $($global:selectedDevice.Status)`n"
    $info += "`n-- ACCIONES DISPONIBLES --`n"
    $info += "- Archivos: Navegar sistema de archivos`n"
    $info += "- Shell: Consola remota PowerShell`n"
    $info += "- WoL: Encender equipo remotamente`n"
    $info += "- Voz: Enviar mensaje de voz`n"
    $info += "- Chat: Chat de texto en tiempo real"
    
    $lblInfo.Text = $info
}

function Open-Files {
    if (-not $global:selectedDevice) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un dispositivo primero", "Aviso")
        return
    }
    Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -File `"$projectPath\Explorer_Agent.ps1`" -ComputerName $($global:selectedDevice.IP)" -WindowStyle Hidden
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
    [System.Windows.Forms.MessageBox]::Show("Paquete WoL enviado a $($global:selectedDevice.Hostname)", "WoL")
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
        $lblApiStatus.Text = "API: Ejecutando en puerto 8082"
        
        $timer = New-Object System.Windows.Forms.Timer
        $timer.Interval = 500
        $timer.Add_Tick({
            if (Test-Path "$projectPath\temp_api.log") {
                try {
                    $log = Get-Content "$projectPath\temp_api.log" -Tail 3 -ErrorAction SilentlyContinue
                    if ($log) {
                        $txtLog.AppendText(($log -join "`n") + "`n")
                    }
                } catch {}
            }
            if ($global:apiProcess.HasExited) {
                $btnApi.Text = "INICIAR API"
                $btnApi.BackColor = [System.Drawing.Color]::FromArgb(15, 52, 96)
                $lblApiStatus.Text = "API: Detenida"
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
        $lblApiStatus.Text = "API: Detenida"
    }
}

$form.Add_Shown({
    Start-NetworkScan
})

if ($Minimized) {
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
}
[System.Windows.Forms.Application]::Run($form)