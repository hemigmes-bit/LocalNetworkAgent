param(
    [string]$ComputerName = "",
    [string]$Mode = "Browse",
    [string]$SourceFileName = "",
    [int]$ParentPID = 0
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Invoke-Command:ErrorAction'] = 'SilentlyContinue'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$configPath = Join-Path $projectPath "network-config.json"
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$localName = $env:COMPUTERNAME
$remoteName = ""
$remoteIP = $ComputerName
$global:isLocal = ($ComputerName -eq "192.168.1.14" -or $ComputerName -eq "localhost" -or $ComputerName -eq "")
$global:sessions = @{}
$global:psSession = $null
$global:clipboardFile = $null

function Get-Credential-ForIP {
    param([string]$ip)
    $core0Cred = Join-Path $projectPath "core0-cred.xml"
    if ($ip -eq "192.168.1.14" -or $ip -eq "localhost") { return $null }
    if (Test-Path $core0Cred) {
        try { return Import-CliXml $core0Cred } catch { }
    }
    return $null
}

$cred = Get-Credential-ForIP -ip $ComputerName

function Get-RemoteName {
    if ($global:isLocal) { return $localName }
    foreach ($pc in $config.Computers) {
        if ($pc.IP -eq $remoteIP) { return $pc.Name }
    }
    try {
        if ($cred) {
            $name = Invoke-Command -ComputerName $remoteIP -Credential $cred -ErrorAction Stop { $env:COMPUTERNAME }
            if ($name) { return $name }
        } else {
            $name = Invoke-Command -ComputerName $remoteIP -ErrorAction Stop { $env:COMPUTERNAME }
            if ($name) { return $name }
        }
    } catch {}
    return $remoteIP
}

$remoteName = Get-RemoteName

# ========== HELPER: Enable Double Buffering ==========
function Enable-DoubleBuffering {
    param([System.Windows.Forms.Control]$ctrl)
    $doubleBufferProp = [System.Windows.Forms.Control].GetProperty("DoubleBuffered", [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Instance)
    if ($doubleBufferProp) { $doubleBufferProp.SetValue($ctrl, $true, $null) }
}

# ========== MAIN FORM ==========
$form = New-Object Windows.Forms.Form
$form.Text = "Transferencia de archivos a $remoteName"
$form.Size = New-Object Drawing.Size(1200, 750)
$form.MinimumSize = New-Object Drawing.Size(900, 550)
$form.BackColor = [Drawing.Color]::FromArgb(245, 245, 245)
$form.StartPosition = "CenterScreen"

# ========== TOOLBAR ==========
$toolPanel = New-Object Windows.Forms.Panel
$toolPanel.Dock = "Top"
$toolPanel.Height = 40
$toolPanel.BackColor = [Drawing.Color]::FromArgb(245, 245, 245)

$btnBack = New-Object Windows.Forms.Button
$btnBack.Location = New-Object Drawing.Point(0, 5)
$btnBack.Size = New-Object Drawing.Size(30, 30)
$btnBack.Text = "<-"
$btnBack.FlatStyle = "Flat"
$btnBack.FlatAppearance.BorderSize = 1
$btnBack.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnBack.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnBack.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)

$btnForward = New-Object Windows.Forms.Button
$btnForward.Location = New-Object Drawing.Point(35, 5)
$btnForward.Size = New-Object Drawing.Size(30, 30)
$btnForward.Text = "->"
$btnForward.FlatStyle = "Flat"
$btnForward.FlatAppearance.BorderSize = 1
$btnForward.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnForward.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnForward.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)

$btnUp = New-Object Windows.Forms.Button
$btnUp.Location = New-Object Drawing.Point(70, 5)
$btnUp.Size = New-Object Drawing.Size(30, 30)
$btnUp.Text = "^"
$btnUp.FlatStyle = "Flat"
$btnUp.FlatAppearance.BorderSize = 1
$btnUp.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnUp.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnUp.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)

$btnRefresh = New-Object Windows.Forms.Button
$btnRefresh.Location = New-Object Drawing.Point(105, 5)
$btnRefresh.Size = New-Object Drawing.Size(30, 30)
$btnRefresh.Text = "R"
$btnRefresh.FlatStyle = "Flat"
$btnRefresh.FlatAppearance.BorderSize = 1
$btnRefresh.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnRefresh.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnRefresh.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)

$btnSend = New-Object Windows.Forms.Button
$btnSend.Location = New-Object Drawing.Point(150, 5)
$btnSend.Size = New-Object Drawing.Size(80, 30)
$btnSend.Text = "Enviar ->"
$btnSend.FlatStyle = "Flat"
$btnSend.FlatAppearance.BorderSize = 1
$btnSend.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnSend.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnSend.Font = New-Object Drawing.Font("Segoe UI", 8)

$btnReceive = New-Object Windows.Forms.Button
$btnReceive.Location = New-Object Drawing.Point(235, 5)
$btnReceive.Size = New-Object Drawing.Size(90, 30)
$btnReceive.Text = "<- Recibir"
$btnReceive.FlatStyle = "Flat"
$btnReceive.FlatAppearance.BorderSize = 1
$btnReceive.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(180, 180, 180)
$btnReceive.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$btnReceive.Font = New-Object Drawing.Font("Segoe UI", 8)

$toolPanel.Controls.Add($btnBack)
$toolPanel.Controls.Add($btnForward)
$toolPanel.Controls.Add($btnUp)
$toolPanel.Controls.Add($btnRefresh)
$toolPanel.Controls.Add($btnSend)
$toolPanel.Controls.Add($btnReceive)

# ========== SPLIT PANELS ==========
$splitMain = New-Object Windows.Forms.SplitContainer
$splitMain.Dock = "Fill"
$splitMain.SplitterDistance = 550
$splitMain.BackColor = [Drawing.Color]::FromArgb(200, 200, 200)

# ========== LEFT PANEL - Local ==========
$localContainer = New-Object Windows.Forms.Panel
$localContainer.Dock = "Fill"
$localContainer.BackColor = [Drawing.Color]::White

# Local Header
$localHeader = New-Object Windows.Forms.Panel
$localHeader.Dock = "Top"
$localHeader.Height = 30
$localHeader.BackColor = [Drawing.Color]::FromArgb(240, 240, 240)

$localIcon = New-Object Windows.Forms.Label
$localIcon.Location = New-Object Drawing.Point(5, 5)
$localIcon.Size = New-Object Drawing.Size(20, 20)
$localIcon.Font = New-Object Drawing.Font("Segoe UI", 10)
$localIcon.Text = "@"

$localHeaderLabel = New-Object Windows.Forms.Label
$localHeaderLabel.Location = New-Object Drawing.Point(28, 6)
$localHeaderLabel.Size = New-Object Drawing.Size(300, 18)
$localHeaderLabel.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)
$localHeaderLabel.ForeColor = [Drawing.Color]::FromArgb(51, 51, 51)
$localHeaderLabel.Text = "$localName - Ordenador local"

$localHeader.Controls.Add($localIcon)
$localHeader.Controls.Add($localHeaderLabel)

# Local TreeView
$localTree = New-Object Windows.Forms.TreeView
$localTree.Dock = "Left"
$localTree.Width = 220
$localTree.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$localTree.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
$localTree.LineColor = [Drawing.Color]::FromArgb(150, 150, 150)
$localTree.ShowLines = $true
$localTree.ShowPlusMinus = $true
$localTree.HideSelection = $false
$localTree.BorderStyle = "FixedSingle"
$localTree.Font = New-Object Drawing.Font("Segoe UI", 8)

# Local ListView
$localList = New-Object Windows.Forms.ListView
$localList.Dock = "Fill"
$localList.View = "Details"
$localList.FullRowSelect = $true
$localList.GridLines = $true
$localList.HeaderStyle = "Nonclickable"
$localList.BorderStyle = "FixedSingle"
$localList.Font = New-Object Drawing.Font("Segoe UI", 8)
$localList.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
$localList.Columns.Add("Nombre", 200) | Out-Null
$localList.Columns.Add("Tamano", 80) | Out-Null
$localList.Columns.Add("Tipo", 90) | Out-Null
$localList.Columns.Add("Modificado", 110) | Out-Null

Enable-DoubleBuffering $localList

$localContainer.Controls.Add($localList)
$localContainer.Controls.Add($localTree)
$localContainer.Controls.Add($localHeader)

# ========== RIGHT PANEL - Remote ==========
$remoteContainer = New-Object Windows.Forms.Panel
$remoteContainer.Dock = "Fill"
$remoteContainer.BackColor = [Drawing.Color]::White

# Remote Header
$remoteHeader = New-Object Windows.Forms.Panel
$remoteHeader.Dock = "Top"
$remoteHeader.Height = 30
$remoteHeader.BackColor = [Drawing.Color]::FromArgb(240, 240, 240)

$remoteIcon = New-Object Windows.Forms.Label
$remoteIcon.Location = New-Object Drawing.Point(5, 5)
$remoteIcon.Size = New-Object Drawing.Size(20, 20)
$remoteIcon.Font = New-Object Drawing.Font("Segoe UI", 10)
$remoteIcon.Text = "#"

$remoteHeaderLabel = New-Object Windows.Forms.Label
$remoteHeaderLabel.Location = New-Object Drawing.Point(28, 6)
$remoteHeaderLabel.Size = New-Object Drawing.Size(300, 18)
$remoteHeaderLabel.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)
$remoteHeaderLabel.ForeColor = [Drawing.Color]::FromArgb(51, 51, 51)
$remoteHeaderLabel.Text = "$remoteName - Ordenador remoto"

$remoteHeader.Controls.Add($remoteIcon)
$remoteHeader.Controls.Add($remoteHeaderLabel)

# Remote TreeView
$remoteTree = New-Object Windows.Forms.TreeView
$remoteTree.Dock = "Left"
$remoteTree.Width = 220
$remoteTree.BackColor = [Drawing.Color]::FromArgb(250, 250, 250)
$remoteTree.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
$remoteTree.LineColor = [Drawing.Color]::FromArgb(150, 150, 150)
$remoteTree.ShowLines = $true
$remoteTree.ShowPlusMinus = $true
$remoteTree.HideSelection = $false
$remoteTree.BorderStyle = "FixedSingle"
$remoteTree.Font = New-Object Drawing.Font("Segoe UI", 8)

# Remote ListView
$remoteList = New-Object Windows.Forms.ListView
$remoteList.Dock = "Fill"
$remoteList.View = "Details"
$remoteList.FullRowSelect = $true
$remoteList.GridLines = $true
$remoteList.HeaderStyle = "Nonclickable"
$remoteList.BorderStyle = "FixedSingle"
$remoteList.Font = New-Object Drawing.Font("Segoe UI", 8)
$remoteList.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
$remoteList.Columns.Add("Nombre", 200) | Out-Null
$remoteList.Columns.Add("Tamano", 80) | Out-Null
$remoteList.Columns.Add("Tipo", 90) | Out-Null
$remoteList.Columns.Add("Modificado", 110) | Out-Null

Enable-DoubleBuffering $remoteList

$remoteContainer.Controls.Add($remoteList)
$remoteContainer.Controls.Add($remoteTree)
$remoteContainer.Controls.Add($remoteHeader)

$splitMain.Panel1.Controls.Add($localContainer)
$splitMain.Panel2.Controls.Add($remoteContainer)

# ========== STATUS BAR ==========
$statusBar = New-Object Windows.Forms.Panel
$statusBar.Dock = "Bottom"
$statusBar.Height = 24
$statusBar.BackColor = [Drawing.Color]::FromArgb(240, 240, 240)
$statusBar.BorderStyle = "FixedSingle"

$lblSelCount = New-Object Windows.Forms.Label
$lblSelCount.Location = New-Object Drawing.Point(5, 3)
$lblSelCount.Size = New-Object Drawing.Size(200, 18)
$lblSelCount.Font = New-Object Drawing.Font("Segoe UI", 8)
$lblSelCount.ForeColor = [Drawing.Color]::FromArgb(100, 100, 100)
$lblSelCount.Text = "0 objeto(s) seleccionado(s)"

$lblConnection = New-Object Windows.Forms.Label
$lblConnection.Location = New-Object Drawing.Point(300, 3)
$lblConnection.Size = New-Object Drawing.Size(600, 18)
$lblConnection.Font = New-Object Drawing.Font("Segoe UI", 8)
$lblConnection.ForeColor = [Drawing.Color]::FromArgb(0, 120, 0)
$lblConnection.TextAlign = "MiddleRight"
$lblConnection.Text = ""

$statusBar.Controls.Add($lblSelCount)
$statusBar.Controls.Add($lblConnection)

# ========== ASSEMBLE ==========
$form.Controls.Add($splitMain)
$form.Controls.Add($toolPanel)
$form.Controls.Add($statusBar)

# ========== HELPER: Double Buffering ==========
function Enable-DoubleBuffering {
    param([System.Windows.Forms.Control]$ctrl)
    $doubleBufferProp = [System.Windows.Forms.Control].GetProperty("DoubleBuffered", [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Instance)
    if ($doubleBufferProp) { $doubleBufferProp.SetValue($ctrl, $true, $null) }
}

# ========== FORMAT SIZE ==========
function Format-Size {
    param([long]$bytes)
    if ($bytes -gt 1GB) { return "$([math]::Round($bytes/1GB,1)) GB" }
    elseif ($bytes -gt 1MB) { return "$([math]::Round($bytes/1MB,1)) MB" }
    elseif ($bytes -gt 1KB) { return "$([math]::Round($bytes/1KB,1)) KB" }
    else { return "$bytes B" }
}

# ========== SESSION MANAGEMENT ==========
function Switch-Computer {
    param([string]$ip)
    if ($global:isLocal -or -not $ip) { return }
    if ($global:psSession -and $global:psSession.State -eq 'Opened') { return }
    if ($global:sessions.ContainsKey($ip) -and $global:sessions[$ip].State -eq 'Opened') {
        $global:psSession = $global:sessions[$ip]
        return
    }
    try {
        $global:psSession = New-PSSession -ComputerName $ip -ErrorAction Stop
        $global:sessions[$ip] = $global:psSession
        $lblConnection.Text = "Conexion establecida con $ip"
    } catch {
        $c = Get-Credential-ForIP -ip $ip
        if ($c) {
            try {
                $global:psSession = New-PSSession -ComputerName $ip -Credential $c -ErrorAction Stop
                $global:sessions[$ip] = $global:psSession
                $lblConnection.Text = "Conexion establecida con $ip"
            } catch {
                $lblConnection.Text = "Error conectando a $ip"
            }
        } else {
            $lblConnection.Text = "Error conectando a $ip"
        }
    }
}

# ========== PATH TRACKING ==========
$global:localPath = "C:\Users\$($env:USERNAME)"
$global:remotePath = "__ROOT__"
$global:localHistory = @()
$global:remoteHistory = @()

# ========== POPULATE LOCAL TREE ==========
function Populate-LocalTree {
    $localTree.Nodes.Clear()
    $drives = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 }
    foreach ($d in $drives) {
        $node = New-Object Windows.Forms.TreeNode($d.DeviceID)
        $node.Tag = @{ Type="Drive"; Path=$d.DeviceID + "\" }
        $node.Nodes.Add((New-Object Windows.Forms.TreeNode("..."))) | Out-Null
        $localTree.Nodes.Add($node) | Out-Null
    }
}

# ========== POPULATE REMOTE TREE ==========
function Populate-RemoteTree {
    $remoteTree.Nodes.Clear()
    if (-not $global:psSession -or $global:psSession.State -ne 'Opened') { return }
    try {
        $drives = Invoke-Command -Session $global:psSession -ScriptBlock {
            Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 }
        }
        foreach ($d in $drives) {
            $node = New-Object Windows.Forms.TreeNode($d.DeviceID)
            $node.Tag = @{ Type="Drive"; Path=$d.DeviceID + "\" }
            $node.Nodes.Add((New-Object Windows.Forms.TreeNode("..."))) | Out-Null
            $remoteTree.Nodes.Add($node) | Out-Null
        }
    } catch {}
}

# ========== LIST LOCAL PATH ==========
function Show-LocalPath {
    param([string]$path)
    $global:localPath = $path
    $localList.Items.Clear()

    try {
        $items = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | Sort-Object @{E={$_.PSIsContainer};D=$true}, Name
        foreach ($f in $items) {
            $item = New-Object Windows.Forms.ListViewItem($f.Name)
            $item.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
            if ($f.PSIsContainer) {
                $item.SubItems.Add("") | Out-Null
                $item.SubItems.Add("Carpeta") | Out-Null
                $item.Tag = @{ Type="Folder"; Path=($path + "\" + $f.Name) }
            } else {
                $ext = [System.IO.Path]::GetExtension($f.Name).TrimStart('.')
                if ($ext) { $ext = "$ext archivo" } else { $ext = "Archivo" }
                $item.SubItems.Add((Format-Size $f.Length)) | Out-Null
                $item.SubItems.Add($ext) | Out-Null
                $item.Tag = @{ Type="File"; Path=($path + "\" + $f.Name) }
            }
            $item.SubItems.Add($f.LastWriteTime.ToString("dd/MM/yyyy HH:mm")) | Out-Null
            $localList.Items.Add($item) | Out-Null
        }
    } catch {}
}

# ========== LIST REMOTE PATH ==========
function Show-RemotePath {
    param([string]$path)
    $global:remotePath = $path
    $remoteList.Items.Clear()

    if ($path -eq "__ROOT__") { return }

    try {
        $items = Invoke-Command -Session $global:psSession -ScriptBlock {
            param($p)
            Get-ChildItem -Path $p -ErrorAction SilentlyContinue | Sort-Object @{E={$_.PSIsContainer};D=$true}, Name
        } -ArgumentList $path
        foreach ($f in $items) {
            $item = New-Object Windows.Forms.ListViewItem($f.Name)
            $item.ForeColor = [Drawing.Color]::FromArgb(30, 30, 30)
            if ($f.PSIsContainer) {
                $item.SubItems.Add("") | Out-Null
                $item.SubItems.Add("Carpeta") | Out-Null
                $item.Tag = @{ Type="Folder"; Path=($path + "\" + $f.Name) }
            } else {
                $ext = [System.IO.Path]::GetExtension($f.Name).TrimStart('.')
                if ($ext) { $ext = "$ext archivo" } else { $ext = "Archivo" }
                $item.SubItems.Add((Format-Size $f.Length)) | Out-Null
                $item.SubItems.Add($ext) | Out-Null
                $item.Tag = @{ Type="File"; Path=($path + "\" + $f.Name) }
            }
            $item.SubItems.Add($f.LastWriteTime.ToString("dd/MM/yyyy HH:mm")) | Out-Null
            $remoteList.Items.Add($item) | Out-Null
        }
    } catch {}
}

# ========== TREE EXPANSION ==========
$localTree.Add_BeforeExpand({
    $node = $_.Node
    if ($node.Nodes.Count -eq 1 -and $node.Nodes[0].Text -eq "...") {
        $node.Nodes.Clear()
        $path = $node.Tag.Path
        try {
            $folders = Get-ChildItem -Path $path -Directory -ErrorAction SilentlyContinue
            foreach ($f in $folders) {
                $childNode = New-Object Windows.Forms.TreeNode($f.Name)
                $childNode.Tag = @{ Type="Folder"; Path=($path + $f.Name + "\") }
                $childNode.Nodes.Add((New-Object Windows.Forms.TreeNode("..."))) | Out-Null
                $node.Nodes.Add($childNode) | Out-Null
            }
        } catch {}
    }
})

$remoteTree.Add_BeforeExpand({
    $node = $_.Node
    if ($node.Nodes.Count -eq 1 -and $node.Nodes[0].Text -eq "...") {
        $node.Nodes.Clear()
        $path = $node.Tag.Path
        try {
            $folders = Invoke-Command -Session $global:psSession -ScriptBlock {
                param($p) Get-ChildItem -Path $p -Directory -ErrorAction SilentlyContinue
            } -ArgumentList $path
            foreach ($f in $folders) {
                $childNode = New-Object Windows.Forms.TreeNode($f.Name)
                $childNode.Tag = @{ Type="Folder"; Path=($path + $f.Name + "\") }
                $childNode.Nodes.Add((New-Object Windows.Forms.TreeNode("..."))) | Out-Null
                $node.Nodes.Add($childNode) | Out-Null
            }
        } catch {}
    }
})

# ========== TREE SELECTION ==========
$localTree.Add_AfterSelect({
    $tag = $_.Node.Tag
    if ($tag -and $tag.Type) {
        $global:localHistory += $global:localPath
        Show-LocalPath $tag.Path
    }
})

$remoteTree.Add_AfterSelect({
    $tag = $_.Node.Tag
    if ($tag -and $tag.Type) {
        $global:remoteHistory += $global:remotePath
        Show-RemotePath $tag.Path
    }
})

# ========== DOUBLE CLICK NAV ==========
$localList.Add_DoubleClick({
    if ($localList.SelectedItems.Count -eq 0) { return }
    $tag = $localList.SelectedItems[0].Tag
    if ($tag.Type -eq "Folder") {
        $global:localHistory += $global:localPath
        Show-LocalPath $tag.Path
    }
})

$remoteList.Add_DoubleClick({
    if ($remoteList.SelectedItems.Count -eq 0) { return }
    $tag = $remoteList.SelectedItems[0].Tag
    if ($tag.Type -eq "Folder") {
        $global:remoteHistory += $global:remotePath
        Show-RemotePath $tag.Path
    }
})

# ========== BUTTONS ==========
$btnBack.Add_Click({
    $global:localHistory = @()
    $global:remoteHistory = @()
    Show-LocalPath $global:localPath
    Show-RemotePath $global:remotePath
})

$btnUp.Add_Click({
    $parent = Split-Path $global:localPath -Parent
    if ($parent) {
        $global:localHistory += $global:localPath
        Show-LocalPath $parent
    }
})

$btnRefresh.Add_Click({
    Show-LocalPath $global:localPath
    if ($global:remotePath -ne "__ROOT__") {
        Show-RemotePath $global:remotePath
    }
})

$btnSend.Add_Click({
    if ($localList.SelectedItems.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un archivo en el panel local", "Aviso")
        return
    }
    $tag = $localList.SelectedItems[0].Tag
    if ($tag.Type -ne "File") {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un archivo (no carpeta)", "Aviso")
        return
    }
    if ($global:remotePath -eq "__ROOT__") {
        [System.Windows.Forms.MessageBox]::Show("Seleccione una carpeta de destino en el panel remoto", "Aviso")
        return
    }
    Transfer-File -SourcePath $tag.Path -SourcePC "local" -DestPath $global:remotePath -DestPC "remote" -Direction "Enviar"
})

$btnReceive.Add_Click({
    if ($remoteList.SelectedItems.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un archivo en el panel remoto", "Aviso")
        return
    }
    $tag = $remoteList.SelectedItems[0].Tag
    if ($tag.Type -ne "File") {
        [System.Windows.Forms.MessageBox]::Show("Seleccione un archivo (no carpeta)", "Aviso")
        return
    }
    Transfer-File -SourcePath $tag.Path -SourcePC "remote" -DestPath $global:localPath -DestPC "local" -Direction "Recibir"
})

# ========== SELECTION COUNT ==========
$localList.Add_SelectedIndexChanged({
    $c = $localList.SelectedItems.Count
    $lblSelCount.Text = "$c objeto(s) seleccionado(s)  |  Local: $global:localPath"
})

$remoteList.Add_SelectedIndexChanged({
    $c = $remoteList.SelectedItems.Count
    $lblSelCount.Text = "$c objeto(s) seleccionado(s)  |  Remoto: $global:remotePath"
})

# ========== TRANSFER ==========
function Transfer-File {
    param([string]$SourcePath, [string]$SourcePC, [string]$DestPath, [string]$DestPC, [string]$Direction)

    $fname = [System.IO.Path]::GetFileName($SourcePath)
    $fsize = 0

    try {
        if ($SourcePC -eq "local") {
            $fsize = (Get-Item $SourcePath -ErrorAction SilentlyContinue).Length
        } else {
            $fsize = Invoke-Command -Session $global:psSession -ScriptBlock {
                param($p) (Get-Item $p -ErrorAction SilentlyContinue).Length
            } -ArgumentList $SourcePath
        }
    } catch {}

    $sizeStr = Format-Size $fsize

    $fromLabel = if ($SourcePC -eq "local") { $localName } else { $remoteName }
    $toLabel = if ($DestPC -eq "local") { $localName } else { $remoteName }

    $temp = Join-Path $env:TEMP $fname

    # Simple progress dialog
    $pf = New-Object Windows.Forms.Form
    $pf.Text = "$Direction $fname"
    $pf.Size = New-Object Drawing.Size(420, 120)
    $pf.StartPosition = "CenterScreen"
    $pf.FormBorderStyle = "FixedDialog"
    $pf.MaximizeBox = $false; $pf.MinimizeBox = $false
    $pf.TopMost = $true
    $pf.BackColor = [Drawing.Color]::FromArgb(252, 252, 252)

    $lblTitle = New-Object Windows.Forms.Label
    $lblTitle.Location = New-Object Drawing.Point(10, 10)
    $lblTitle.Size = New-Object Drawing.Size(380, 18)
    $lblTitle.Font = New-Object Drawing.Font("Segoe UI", 9, [Drawing.FontStyle]::Bold)
    $lblTitle.Text = $fname

    $lblInfo = New-Object Windows.Forms.Label
    $lblInfo.Location = New-Object Drawing.Point(10, 30)
    $lblInfo.Size = New-Object Drawing.Size(380, 16)
    $lblInfo.Font = New-Object Drawing.Font("Segoe UI", 8)
    $lblInfo.ForeColor = [Drawing.Color]::Gray
    $lblInfo.Text = "$sizeStr  |  $fromLabel -> $toLabel"

    $bar = New-Object Windows.Forms.ProgressBar
    $bar.Location = New-Object Drawing.Point(10, 50)
    $bar.Size = New-Object Drawing.Size(380, 25)
    $bar.Style = "Marquee"

    $lblStatus = New-Object Windows.Forms.Label
    $lblStatus.Location = New-Object Drawing.Point(10, 80)
    $lblStatus.Size = New-Object Drawing.Size(380, 18)
    $lblStatus.Font = New-Object Drawing.Font("Segoe UI", 8)
    $lblStatus.ForeColor = [Drawing.Color]::FromArgb(0, 120, 215)
    $lblStatus.Text = "Transfiriendo..."

    $pf.Controls.Add($lblTitle)
    $pf.Controls.Add($lblInfo)
    $pf.Controls.Add($bar)
    $pf.Controls.Add($lblStatus)

    $pf.Show()
    [System.Windows.Forms.Application]::DoEvents()
    $start = Get-Date

    $ok = $false
    try {
        if ($SourcePC -ne "local") {
            Copy-Item -FromSession $global:psSession -Path $SourcePath -Destination $temp -Force -ErrorAction Stop
        } else {
            Copy-Item -Path $SourcePath -Destination $temp -Force -ErrorAction Stop
        }
        if ($DestPC -ne "local") {
            Copy-Item -ToSession $global:psSession -Path $temp -Destination $DestPath -Force -ErrorAction Stop
        } else {
            Copy-Item -Path $temp -Destination $DestPath -Force -ErrorAction Stop
        }
        $ok = $true
    } catch {
        $lblStatus.Text = "Error: $($_.Exception.Message)"
        $lblStatus.ForeColor = [Drawing.Color]::Red
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Seconds 2
    } finally {
        if (Test-Path $temp) { Remove-Item $temp -Force -ErrorAction SilentlyContinue }
    }

    if ($ok) {
        $elapsed = [math]::Max(0.1, ((Get-Date) - $start).TotalSeconds)
        $bar.Style = "Continuous"
        $bar.Value = 100
        $lblStatus.Text = "Completado en ${elapsed}s"
        $lblStatus.ForeColor = [Drawing.Color]::Green
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Seconds 1
        $lblConnection.Text = "$Direction completado: $fname"
    }

    $pf.Close(); $pf.Dispose()
    return $ok
}

# ========== INIT ==========
Show-LocalPath $global:localPath
Populate-LocalTree

if (-not $global:isLocal) {
    Switch-Computer -ip $remoteIP
    if ($global:psSession -and $global:psSession.State -eq 'Opened') {
        Show-RemotePath "__ROOT__"
        Populate-RemoteTree
    } else {
        $lblConnection.Text = "No se pudo conectar a $remoteName"
    }
} else {
    $lblConnection.Text = "Explorador local"
}

[Windows.Forms.Application]::Run($form)

if ($global:psSession) { Remove-PSSession $global:psSession -ErrorAction SilentlyContinue }
foreach ($s in $global:sessions.Values) { Remove-PSSession $s -ErrorAction SilentlyContinue }
