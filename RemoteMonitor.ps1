param([string]$ComputerName="192.168.1.17",[int]$Port=9876,[int]$Interval=2000)

Add-Type -AssemblyName System.Windows.Forms

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"

# Arrancar CaptureServer en el PC remoto
try {
    $ip = $ComputerName
    Invoke-Command -ComputerName $ip -ScriptBlock {
        param($port, $interval)
        $taskName = "CaptureServer_$port"
        schtasks /Delete /TN $taskName /F 2>$null
        schtasks /Create /TN $taskName /SC ONCE /ST 00:00 /TR "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Users\Usuario\LocalNetworkAgent\CaptureServer.ps1 -Port $port -Interval $interval" /RU INTERACTIVE /F 2>$null
        schtasks /Run /TN $taskName 2>$null
        Start-Sleep -Seconds 3
    } -ArgumentList $Port, $Interval -ErrorAction SilentlyContinue
} catch {}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Monitor: $ComputerName"
$form.Size = New-Object System.Drawing.Size(1024, 700)
$form.StartPosition = "CenterScreen"

$pic = New-Object System.Windows.Forms.PictureBox
$pic.Dock = "Fill"
$pic.SizeMode = "Zoom"
$pic.BackColor = [System.Drawing.Color]::Black
$form.Controls.Add($pic)

$lbl = New-Object System.Windows.Forms.Label
$lbl.Dock = "Top"
$lbl.Text = "Conectando a $ComputerName..."
$lbl.Height = 25
$lbl.BackColor = [System.Drawing.Color]::FromArgb(0, 50, 0)
$lbl.ForeColor = [System.Drawing.Color]::Lime
$lbl.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$form.Controls.Add($lbl)

$url = "http://${ComputerName}:$Port/screen.jpg"

function getImage {
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "Mozilla/5.0")
        $bytes = $wc.DownloadData($url)
        $wc.Dispose()
        if ($bytes.Length -gt 100) {
            $ms = New-Object System.IO.MemoryStream(, $bytes)
            $img = [System.Drawing.Image]::FromStream($ms)
            $ms.Dispose()
            return $img
        } else { return $null }
    } catch { return $null }
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = $Interval

$timer.Add_Tick({
    try {
        $img = getImage
        if ($img) {
            if ($pic.Image) { $pic.Image.Dispose() }
            $pic.Image = $img
            $lbl.Text = "Monitor: $ComputerName - $(Get-Date -Format 'HH:mm:ss')"
        } else {
            $lbl.Text = "Esperando captura de $ComputerName..."
        }
    } catch {
        $lbl.Text = "Error: " + $_.Exception.Message.Substring(0, 40)
    }
})

$timer.Start()
$form.Add_FormClosing({
    $timer.Stop()
    # Detener CaptureServer remoto
    try {
        Invoke-Command -ComputerName $ComputerName -ScriptBlock {
            param($port)
            schtasks /End /TN "CaptureServer_$port" 2>$null
            schtasks /Delete /TN "CaptureServer_$port" /F 2>$null
        } -ArgumentList $Port -ErrorAction SilentlyContinue
    } catch {}
})
$form.ShowDialog()
