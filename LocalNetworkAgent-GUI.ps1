# LocalNetworkAgent-GUI.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"

$form = New-Object System.Windows.Forms.Form
$form.Text = "Local Network Agent v2.1.0"
$form.Size = New-Object System.Drawing.Size(470, 520)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::FromArgb(26, 26, 46)
$form.FormBorderStyle = "FixedDialog"

function New-Btn($text, $x, $y, $w, $h, $bg, $fg) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.Location = New-Object System.Drawing.Point($x, $y)
    $b.Size = New-Object System.Drawing.Size($w, $h)
    $b.FlatStyle = "Flat"
    $b.BackColor = $bg
    $b.ForeColor = if ($fg) { $fg } else { [System.Drawing.Color]::White }
    $b
}

$btnScan = New-Btn "ESCANEAR" 30 70 90 35 ([System.Drawing.Color]::FromArgb(0, 217, 255)) ([System.Drawing.Color]::Black)
$btnFiles = New-Btn "ARCHIVOS" 130 70 90 35 ([System.Drawing.Color]::FromArgb(255, 184, 108)) ([System.Drawing.Color]::Black)
$btnShell = New-Btn "SHELL" 230 70 90 35 ([System.Drawing.Color]::FromArgb(255, 121, 198)) ([System.Drawing.Color]::Black)
$btnVoice = New-Btn "VOZ" 330 70 90 35 ([System.Drawing.Color]::FromArgb(15, 52, 96))

$btnIntercom = New-Btn "CHAT CORE0" 30 120 190 35 ([System.Drawing.Color]::FromArgb(74, 42, 193))
$btnSpeak = New-Btn "VOZ CORE0" 230 120 190 35 ([System.Drawing.Color]::FromArgb(255, 87, 34))

$btnWoL = New-Btn "ENCENDER CORE0 (WoL)" 30 170 390 40 ([System.Drawing.Color]::FromArgb(0, 200, 83))
$btnWoL.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)

$title = New-Object System.Windows.Forms.Label
$title.Text = "LOCAL NETWORK AGENT"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(0, 217, 255)
$title.Location = New-Object System.Drawing.Point(70, 20)
$title.Size = New-Object System.Drawing.Size(330, 35)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "v2.1.0 - Red y Megafonia"
$lblStatus.Location = New-Object System.Drawing.Point(30, 225)
$lblStatus.Size = New-Object System.Drawing.Size(400, 20)
$lblStatus.ForeColor = [System.Drawing.Color]::Cyan

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ReadOnly = $true
$txtLog.Location = New-Object System.Drawing.Point(30, 255)
$txtLog.Size = New-Object System.Drawing.Size(400, 180)
$txtLog.BackColor = [System.Drawing.Color]::Black
$txtLog.ForeColor = [System.Drawing.Color]::Lime
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 8)

$btnScan.Add_Click({
    Start-Process powershell -ArgumentList "-NoExit -File `"$projectPath\Scan-Network.ps1`""
})

$btnFiles.Add_Click({
    $ip = [Microsoft.VisualBasic.Interaction]::InputBox("IP:", "Archivos", "192.168.1.14")
    if ($ip) {
        Start-Process powershell -ArgumentList "-NoExit -File `"$projectPath\Explorer_Agent.ps1`" -ComputerName $ip"
    }
})

$btnShell.Add_Click({
    $ip = [Microsoft.VisualBasic.Interaction]::InputBox("IP:", "Shell", "192.168.1.14")
    if ($ip) {
        Start-Process powershell -ArgumentList "-NoExit -Command `"Import-Module '$projectPath\NetworkUtilsPublic.psm1'; Connect-RemoteComputer -ComputerName $ip`""
    }
})

$btnVoice.Add_Click({
    Start-Process powershell -ArgumentList "-NoExit -File `"$projectPath\VoiceControl.ps1`""
})

$btnIntercom.Add_Click({
    $ip = [Microsoft.VisualBasic.Interaction]::InputBox("IP:", "Intercom", "192.168.1.14")
    if ($ip) {
        Start-Process powershell -ArgumentList "-NoExit -File `"$projectPath\Intercom.ps1`" -ComputerName $ip"
    }
})

$btnSpeak.Add_Click({
    $ip = [Microsoft.VisualBasic.Interaction]::InputBox("IP:", "Voz", "192.168.1.10")
    if ($ip) {
        Start-Process powershell -ArgumentList "-NoExit -File `"$projectPath\Speak-Remote.ps1`" -ComputerName $ip"
    }
})

$btnWoL.Add_Click({
    $config = Get-Content "$projectPath\network-config.json" | ConvertFrom-Json
    Start-Process powershell -ArgumentList "-Command `"Import-Module '$projectPath\NetworkUtilsPublic.psm1'; Send-WakeOnLan -MACAddress $($config.Core0MAC)`""
    [System.Windows.Forms.MessageBox]::Show("Paquete WoL enviado a CORE0!", "WoL")
})

$form.Controls.AddRange(@($title,$btnScan,$btnFiles,$btnShell,$btnVoice,$btnIntercom,$btnSpeak,$btnWoL,$lblStatus,$txtLog))
$form.ShowDialog()