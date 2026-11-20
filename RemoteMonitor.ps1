param([string]$ComputerName="", [int]$Port=9876, [int]$Interval=2000)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$credFile = Join-Path $projectPath "core0-cred.xml"

# ─── Detection Form ──────────────────────────────────────────────────────────
$form = New-Object System.Windows.Forms.Form
$form.Text = "Acceso Remoto: $ComputerName"
$form.Size = New-Object System.Drawing.Size(620, 380)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::FromArgb(10, 10, 20)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "DETECTANDO METODOS DE ACCESO REMOTO"
$lblTitle.Location = New-Object System.Drawing.Point(20, 15)
$lblTitle.Size = New-Object System.Drawing.Size(580, 25)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(0, 230, 200)
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($lblTitle)

$lblDevice = New-Object System.Windows.Forms.Label
$lblDevice.Text = "Dispositivo: $ComputerName"
$lblDevice.Location = New-Object System.Drawing.Point(20, 42)
$lblDevice.Size = New-Object System.Drawing.Size(580, 18)
$lblDevice.ForeColor = [System.Drawing.Color]::FromArgb(140, 140, 160)
$lblDevice.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Controls.Add($lblDevice)

$listBox = New-Object System.Windows.Forms.ListBox
$listBox.Location = New-Object System.Drawing.Point(20, 70)
$listBox.Size = New-Object System.Drawing.Size(580, 200)
$listBox.BackColor = [System.Drawing.Color]::FromArgb(5, 5, 15)
$listBox.ForeColor = [System.Drawing.Color]::FromArgb(220, 220, 240)
$listBox.Font = New-Object System.Drawing.Font("Cascadia Code", 10)
$listBox.BorderStyle = "None"
$form.Controls.Add($listBox)

$statusLbl = New-Object System.Windows.Forms.Label
$statusLbl.Text = "Detectando..."
$statusLbl.Location = New-Object System.Drawing.Point(20, 280)
$statusLbl.Size = New-Object System.Drawing.Size(580, 20)
$statusLbl.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 120)
$statusLbl.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Controls.Add($statusLbl)

$btn = New-Object System.Windows.Forms.Button
$btn.Text = "  CONECTAR"
$btn.Location = New-Object System.Drawing.Point(240, 310)
$btn.Size = New-Object System.Drawing.Size(130, 30)
$btn.FlatStyle = "Flat"
$btn.FlatAppearance.BorderSize = 1
$btn.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(0, 210, 190)
$btn.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 48)
$btn.ForeColor = [System.Drawing.Color]::FromArgb(0, 210, 190)
$btn.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btn.Enabled = $false
$form.Controls.Add($btn)

# ─── Detection ────────────────────────────────────────────────────────────────
$cred = $null
if (Test-Path $credFile) { try { $cred = Import-Clixml $credFile } catch {} }

$script:methods = @()

function Add-Method {
    param($name, $type, $desc, $extra)
    $m = @{ Name = $name; Type = $type; Desc = $desc }
    if ($extra) { $m.Extra = $extra }
    $script:methods += $m
    $listBox.Items.Add($name.PadRight(20) + "  " + $desc)
}

# Timer: runs detection after form is visible, keeps UI responsive
$detectTimer = New-Object System.Windows.Forms.Timer
$detectTimer.Interval = 50
$detectTimer.Add_Tick({
    $detectTimer.Stop()

    # 1. Check RDP port 3389
    $statusLbl.Text = "Verificando RDP (puerto 3389)..."
    [System.Windows.Forms.Application]::DoEvents()
    try {
        $t = New-Object System.Net.Sockets.TcpClient
        $c = $t.BeginConnect($ComputerName, 3389, $null, $null)
        if ($c.AsyncWaitHandle.WaitOne(300)) {
            Add-Method -name "RDP (Escritorio Remoto)" -type "rdp" -desc "Control remoto completo, baja latencia"
            $t.EndConnect($c)
        }
        $t.Close()
    } catch {}
    [System.Windows.Forms.Application]::DoEvents()

    # 2. Check TeamViewer via WinRM
    $statusLbl.Text = "Verificando TeamViewer (via WinRM)..."
    [System.Windows.Forms.Application]::DoEvents()
    try {
        $session = New-PSSession -ComputerName $ComputerName -Credential $cred -ErrorAction Stop
        $tvInfo = Invoke-Command -Session $session -ScriptBlock {
            $installed = (Test-Path "C:\Program Files\TeamViewer\TeamViewer.exe") -or
                          (Test-Path "C:\Program Files (x86)\TeamViewer\TeamViewer.exe")
            $id = $null
            if ($installed) {
                try { $id = (Get-ItemProperty "HKLM:\SOFTWARE\TeamViewer" -ErrorAction SilentlyContinue).ClientID } catch {}
            }
            return @{ Installed = $installed; ID = $id }
        }
        Remove-PSSession $session

        if ($tvInfo.Installed) {
            $tvDesc = "Baja latencia, control remoto completo"
            if ($tvInfo.ID) { $tvDesc += " | ID: $($tvInfo.ID)" }
            Add-Method -name "TeamViewer" -type "teamviewer" -desc $tvDesc -extra @{ TVId = $tvInfo.ID }
        }
    } catch {
        $statusLbl.Text = "WinRM no disponible: deteccion de TeamViewer omitida"
        [System.Windows.Forms.Application]::DoEvents()
    }
    [System.Windows.Forms.Application]::DoEvents()

    # 3. Always add CaptureServer as fallback
    Add-Method -name "CaptureServer (HTTP)" -type "capture" -desc "Captura de pantalla via WinRM + HTTP (solo vista)"

    # Auto-select first item
    if ($listBox.Items.Count -gt 0) {
        $listBox.SelectedIndex = 0
        $btn.Enabled = $true
    }

    $statusLbl.Text = "Seleccione un metodo de acceso y presione CONECTAR"
    [System.Windows.Forms.Application]::DoEvents()
})
$detectTimer.Start()

# ─── Action ──────────────────────────────────────────────────────────────────
$btn.Add_Click({
    if ($listBox.SelectedIndex -lt 0) { return }
    $selected = $methods[$listBox.SelectedIndex]
    $form.Close()

    switch ($selected.Type) {
        "rdp" {
            Start-Process "mstsc.exe" -ArgumentList "/v:$ComputerName"
        }
        "teamviewer" {
            $tvExe = "C:\Program Files\TeamViewer\TeamViewer.exe"
            if (-not (Test-Path $tvExe)) { $tvExe = "C:\Program Files (x86)\TeamViewer\TeamViewer.exe" }
            if (Test-Path $tvExe) {
                $args = @()
                if ($selected.Extra.TVId) { $args += "--id"; $args += $selected.Extra.TVId; $args += "--mode"; $args += "remotecontrol" }
                $pwdFile = Join-Path $projectPath "tv-pwd-$ComputerName.txt"
                if (Test-Path $pwdFile) {
                    $pwd = Get-Content $pwdFile -Raw -ErrorAction SilentlyContinue
                    if ($pwd) { $args += "--password"; $args += $pwd.Trim() }
                }
                if ($args.Count -gt 0) {
                    Start-Process $tvExe -ArgumentList $args
                } else {
                    Start-Process $tvExe
                }
            } else {
                [System.Windows.Forms.MessageBox]::Show("TeamViewer no encontrado en este equipo", "Error")
            }
        }
        "capture" {
            # ─── Run inline viewer (original RemoteMonitor logic) ─────────────
            Add-Type -AssemblyName System.Drawing

            $vForm = New-Object System.Windows.Forms.Form
            $vForm.Text = "Monitor: $ComputerName (CaptureServer)"
            $vForm.Size = New-Object System.Drawing.Size(1024, 700)
            $vForm.StartPosition = "CenterScreen"
            $vForm.BackColor = [System.Drawing.Color]::FromArgb(10, 10, 20)

            $pic = New-Object System.Windows.Forms.PictureBox
            $pic.Dock = "Fill"
            $pic.SizeMode = "Zoom"
            $pic.BackColor = [System.Drawing.Color]::Black
            $vForm.Controls.Add($pic)

            $lbl = New-Object System.Windows.Forms.Label
            $lbl.Dock = "Top"
            $lbl.Text = "Conectando a $ComputerName..."
            $lbl.Height = 25
            $lbl.BackColor = [System.Drawing.Color]::FromArgb(0, 50, 0)
            $lbl.ForeColor = [System.Drawing.Color]::Lime
            $lbl.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
            $vForm.Controls.Add($lbl)

            function Write-Log { param($msg) $lbl.Text = "$msg - $(Get-Date -Format 'HH:mm:ss')"; [System.Windows.Forms.Application]::DoEvents() }

            # Deploy and start CaptureServer remotely
            $deployOk = $false
            try {
                $session = New-PSSession -ComputerName $ComputerName -Credential $cred -ErrorAction Stop
                $exists = Invoke-Command -Session $session -ScriptBlock { param($p) Test-Path (Join-Path $p "CaptureServer.ps1") } -ArgumentList $projectPath
                if (-not $exists) {
                    Write-Log "Desplegando CaptureServer.ps1 en remoto..."
                    Copy-Item -ToSession $session -Path (Join-Path $projectPath "CaptureServer.ps1") -Destination (Join-Path $projectPath "CaptureServer.ps1") -Force
                }
                Write-Log "Iniciando CaptureServer remoto..."
                Invoke-Command -Session $session -ScriptBlock {
                    param($port, $interval, $remotePath)
                    schtasks /End /TN "CaptureServer_$port" 2>$null
                    schtasks /Delete /TN "CaptureServer_$port" /F 2>$null
                    schtasks /Create /TN "CaptureServer_$port" /SC ONCE /ST 00:00 /TR "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File '$remotePath\CaptureServer.ps1' -Port $port -Interval $interval -Scale 0.5" /RU INTERACTIVE /F 2>$null
                    schtasks /Run /TN "CaptureServer_$port" 2>$null
                    Start-Sleep -Seconds 2
                } -ArgumentList $Port, $Interval, $projectPath
                Remove-PSSession $session
                $deployOk = $true
            } catch {
                Write-Log "WinRM error: $($_.Exception.Message)"
            }

            if (-not $deployOk) {
                Write-Log "No se pudo iniciar CaptureServer remoto."
            }

            $url = "http://${ComputerName}:$Port/screen.jpg"
            $lastDisplay = ""

            $timer = New-Object System.Windows.Forms.Timer
            $timer.Interval = $Interval
            $timer.Add_Tick({
                try {
                    $wc = New-Object System.Net.WebClient
                    $wc.Headers.Add("User-Agent", "Mozilla/5.0")
                    $wc.Headers.Add("Cache-Control", "no-cache")
                    $bytes = $wc.DownloadData($url)
                    $wc.Dispose()
                    if ($bytes.Length -gt 500) {
                        $ms = New-Object System.IO.MemoryStream(, $bytes)
                        $img = [System.Drawing.Image]::FromStream($ms)
                        $ms.Dispose()
                        if ($pic.Image) { $pic.Image.Dispose() }
                        $pic.Image = $img
                        $lbl.Text = "Monitor: $ComputerName - $(Get-Date -Format 'HH:mm:ss')"
                    } else {
                        Write-Log "Esperando captura..."
                    }
                } catch {
                    $msg = $_.Exception.Message
                    if ($msg.Length -gt 50) { $msg = $msg.Substring(0, 50) }
                    if ($msg -ne $lastDisplay) { Write-Log "Error: $msg"; $lastDisplay = $msg }
                }
            })
            $timer.Start()

            $stopServer = { param($p) schtasks /End /TN "CaptureServer_$p" 2>$null; schtasks /Delete /TN "CaptureServer_$p" /F 2>$null }
            $vForm.Add_FormClosing({
                $timer.Stop()
                try {
                    $s = New-PSSession -ComputerName $ComputerName -Credential $cred -ErrorAction SilentlyContinue
                    if ($s) { Invoke-Command -Session $s -ScriptBlock $stopServer -ArgumentList $Port; Remove-PSSession $s }
                } catch {}
            })

            [System.Windows.Forms.Application]::Run($vForm)
        }
    }
})

# Keep form alive with modal message pump
$form.ShowDialog()
