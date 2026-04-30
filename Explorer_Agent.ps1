param([string]$ComputerName = "")

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic

$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$configPath = Join-Path $projectPath "network-config.json"
$credPath = Join-Path $projectPath "core0-cred.xml"

$global:currentComputer = $ComputerName
$global:currentPath = if($ComputerName) { "__DRIVES__" } else { "__NETWORK__" }
$global:clipboardFile = $null

if (Test-Path $credPath) { $cred = Import-CliXml $credPath }
else { $cred = Get-Credential -UserName "Administrador" -Message "Introduce credenciales de red" }

$form = New-Object Windows.Forms.Form
$form.Text = "Explorador de Red"
$form.Size = New-Object Drawing.Size(1100, 800)
$form.BackColor = [Drawing.Color]::FromArgb(30, 30, 30)
$form.ForeColor = [Drawing.Color]::White
$form.StartPosition = "CenterScreen"

$header = New-Object Windows.Forms.Panel
$header.Dock = "Top"
$header.Height = 60
$header.BackColor = [Drawing.Color]::FromArgb(45, 45, 48)

$lblPath = New-Object Windows.Forms.Label
$lblPath.Text = " Ubicacion: Red Local"
$lblPath.Dock = "Fill"
$lblPath.TextAlign = "MiddleLeft"
$lblPath.Font = New-Object Drawing.Font("Segoe UI", 11)
$header.Controls.Add($lblPath)

$listView = New-Object Windows.Forms.ListView
$listView.Dock = "Fill"
$listView.View = "Details"
$listView.FullRowSelect = $true
$listView.BackColor = [Drawing.Color]::FromArgb(30, 30, 30)
$listView.ForeColor = [Drawing.Color]::White
$listView.LabelEdit = $false
$listView.Columns.Add("Nombre", 400) | Out-Null
$listView.Columns.Add("Tipo", 200) | Out-Null
$listView.Columns.Add("Estado", 150) | Out-Null
$listView.Columns.Add("Modificado", 180) | Out-Null

$side = New-Object Windows.Forms.Panel
$side.Dock = "Right"
$side.Width = 200
$side.BackColor = [Drawing.Color]::FromArgb(45, 45, 48)

function Add-Button {
    param([string]$txt, [int]$top, [int[]]$rgb, [scriptblock]$click)
    $b = New-Object Windows.Forms.Button
    $b.Text = $txt
    $b.Top = $top
    $b.Left = 10
    $b.Width = 180
    $b.Height = 45
    $b.FlatStyle = "Flat"
    $b.BackColor = [Drawing.Color]::FromArgb($rgb[0], $rgb[1], $rgb[2])
    $b.Add_Click($click)
    $side.Controls.Add($b)
}

function Show-Folder {
    $listView.Items.Clear()
    try {
        if ($global:currentPath -eq "__NETWORK__") {
            $lblPath.Text = " Ubicacion: Red Local"
            $config = Get-Content $configPath -Raw | ConvertFrom-Json
            foreach ($pc in $config.Computers) {
                $item = New-Object Windows.Forms.ListViewItem($pc.Name)
                $item.SubItems.Add("Equipo Remoto") | Out-Null
                $item.SubItems.Add($pc.IP) | Out-Null
                $item.Tag = @{ Type="PC"; IP=$pc.IP; Name=$pc.Name }
                $item.ForeColor = [Drawing.Color]::Cyan
                $listView.Items.Add($item)
            }
        }
        elseif ($global:currentPath -eq "__DRIVES__") {
            $lblPath.Text = " Ubicacion: $global:currentComputer > Unidades"
            $drives = Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock {
                Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } | Select-Object DeviceID, FreeSpace
            }
            foreach ($d in $drives) {
                $item = New-Object Windows.Forms.ListViewItem($d.DeviceID)
                $item.SubItems.Add("Disco Local") | Out-Null
                $item.SubItems.Add("$([math]::Round($d.FreeSpace/1GB,2)) GB Libres") | Out-Null
                $item.Tag = @{ Type="Drive"; Path=($d.DeviceID + "\") }
                $listView.Items.Add($item)
            }
        }
        else {
            if ([string]::IsNullOrEmpty($global:currentPath)) {
                [Windows.Forms.MessageBox]::Show("Error: Ruta vacia")
                return
            }
            $lblPath.Text = " Ubicacion: $global:currentComputer > $global:currentPath"
            $files = Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock {
                param($p)
                Get-ChildItem -Path $p -ErrorAction SilentlyContinue | Select-Object Name, PSIsContainer, Length, LastWriteTime
            } -ArgumentList $global:currentPath
            foreach ($f in $files) {
                $item = New-Object Windows.Forms.ListViewItem($f.Name)
                if ($f.PSIsContainer) {
                    $item.SubItems.Add("Carpeta") | Out-Null
                    $item.ForeColor = [Drawing.Color]::Yellow
                    $newPath = $global:currentPath + "\" + $f.Name
                    $item.Tag = @{ Type="Dir"; Path=$newPath }
                }
                else {
                    $item.SubItems.Add("$([math]::Round($f.Length/1KB,1)) KB") | Out-Null
                    $newPath = $global:currentPath + "\" + $f.Name
                    $item.Tag = @{ Type="File"; Path=$newPath }
                }
                $item.SubItems.Add("") | Out-Null
                $item.SubItems.Add($f.LastWriteTime.ToString("dd/MM/yyyy HH:mm")) | Out-Null
                $listView.Items.Add($item)
            }
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        if ($errMsg -match "Path") {
            $errMsg = "Error de ruta: verifique que la carpeta exista"
        }
        [Windows.Forms.MessageBox]::Show("Error: $errMsg")
        $global:currentPath = "__DRIVES__"
        Show-Folder
    }
}

# Navigation - use double click only
$listView.Add_DoubleClick({
    if ($listView.SelectedItems.Count -gt 0) {
        $item = $listView.SelectedItems[0]
        if ($item.Tag) {
            $data = $item.Tag
            if ($data.Type -eq "PC") {
                $global:currentComputer = $data.IP
                $global:currentPath = "__DRIVES__"
                Show-Folder
            }
            elseif (($data.Type -eq "Drive" -or $data.Type -eq "Dir") -and $data.Path) {
                $global:currentPath = $data.Path
                Show-Folder
            }
        }
    }
})

$listView.Add_MouseClick({
    Start-Sleep -Milliseconds 300
    if ($listView.SelectedItems.Count -gt 0) {
        $item = $listView.SelectedItems[0]
        if ($item.Tag) {
            $data = $item.Tag
            if ($data.Type -eq "PC") {
                $global:currentComputer = $data.IP
                $global:currentPath = "__DRIVES__"
                Show-Folder
            }
            elseif (($data.Type -eq "Drive" -or $data.Type -eq "Dir") -and $data.Path) {
                $global:currentPath = $data.Path
                Show-Folder
            }
        }
    }
})

Add-Button "ATRAS" 10 @(128,128,128) {
    if ($global:currentPath -eq "__NETWORK__") { return }
    if ($global:currentPath -eq "__DRIVES__") { $global:currentPath = "__NETWORK__"; Show-Folder; return }
    if ($global:currentPath -match "^[A-Za-z]:\\$") { $global:currentPath = "__DRIVES__"; Show-Folder; return }
    $global:currentPath = Split-Path $global:currentPath -Parent
    Show-Folder
}

Add-Button "COPIAR" 70 @(0,0,139) {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        if ($data.Type -eq "File") {
            $global:clipboardFile = @{ PC=$global:currentComputer; Path=$data.Path; Name=(Split-Path $data.Path -Leaf) }
            [Windows.Forms.MessageBox]::Show("Copiado: $($global:clipboardFile.Name)")
        }
    }
}

Add-Button "PEGAR" 125 @(0,100,0) {
    if ($null -eq $global:clipboardFile) { return }
    if ($global:currentPath -eq "__NETWORK__" -or $global:currentPath -eq "__DRIVES__") { return }
    try {
        $temp = Join-Path $env:TEMP $global:clipboardFile.Name
        $s1 = New-PSSession -ComputerName $global:clipboardFile.PC -Credential $cred
        Copy-Item -FromSession $s1 -Path $global:clipboardFile.Path -Destination $temp -Force
        Remove-PSSession $s1
        $s2 = New-PSSession -ComputerName $global:currentComputer -Credential $cred
        Copy-Item -ToSession $s2 -Path $temp -Destination $global:currentPath -Force
        Remove-PSSession $s2
        Remove-Item $temp -Force
        Show-Folder
        [Windows.Forms.MessageBox]::Show("Archivo pegado")
    }
    catch {
        [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)")
    }
}

Add-Button "NUEVA CARPETA" 180 @(60,60,60) {
    if ($global:currentPath -eq "__NETWORK__" -or $global:currentPath -eq "__DRIVES__") { return }
    $name = [Microsoft.VisualBasic.Interaction]::InputBox("Nombre:", "Crear Carpeta", "Nueva Carpeta")
    if ($name) {
        try {
            Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock {
                param($p, $n) New-Item -Path (Join-Path $p $n) -ItemType Directory -Force
            } -ArgumentList $global:currentPath, $name
            Show-Folder
        }
        catch {
            [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)")
        }
    }
}

Add-Button "ACTUALIZAR" 600 @(0,0,0) { Show-Folder }

$form.Controls.AddRange(@($listView, $header, $side))
$form.Add_Shown({ Show-Folder })
[Windows.Forms.Application]::Run($form)