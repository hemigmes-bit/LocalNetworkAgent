param([string]$ComputerName = "")

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic

# --- CARGA DE CONFIGURACIÓN Y CREDENCIALES ---
$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$configPath = Join-Path $projectPath "network-config.json"
$credPath = Join-Path $projectPath "core0-cred.xml"

$global:currentComputer = $ComputerName
$global:currentPath = if($ComputerName){ "__DRIVES__" } else { "__NETWORK__" }
$global:clipboardFile = $null # Para Copiar/Pegar entre equipos

if (Test-Path $credPath) { $cred = Import-CliXml $credPath }
else { $cred = Get-Credential -UserName "Administrador" -Message "Introduce credenciales de red" }

# UI PRINCIPAL
$form = New-Object Windows.Forms.Form
$form.Text = "Explorador de Red Inteligente - Local Network Agent"
$form.Size = New-Object Drawing.Size(1100, 800)
$form.BackColor = [Drawing.Color]::FromArgb(30, 30, 30)
$form.ForeColor = [Drawing.Color]::White
$form.StartPosition = "CenterScreen"

# CABECERA
$header = New-Object Windows.Forms.Panel
$header.Dock = "Top"; $header.Height = 60; $header.BackColor = [Drawing.Color]::FromArgb(45, 45, 48)
$lblPath = New-Object Windows.Forms.Label
$lblPath.Text = " Ubicación: Red Local"; $lblPath.Dock = "Fill"; $lblPath.TextAlign = "MiddleLeft"; $lblPath.Font = New-Object Drawing.Font("Segoe UI", 11)
$header.Controls.Add($lblPath)

# LISTADO (ListView para iconos)
$listView = New-Object Windows.Forms.ListView
$listView.Dock = "Fill"; $listView.View = "Details"; $listView.FullRowSelect = $true; $listView.BackColor = [Drawing.Color]::FromArgb(30, 30, 30); $listView.ForeColor = [Drawing.Color]::White
$listView.Columns.Add("Nombre", 400) | Out-Null
$listView.Columns.Add("Tipo / Tamaño", 200) | Out-Null
$listView.Columns.Add("Estado", 150) | Out-Null
$listView.Columns.Add("Modificado", 180) | Out-Null
$listView.Font = New-Object Drawing.Font("Segoe UI", 10)

# PANEL LATERAL DE ACCIONES
$side = New-Object Windows.Forms.Panel
$side.Dock = "Right"; $side.Width = 200; $side.BackColor = [Drawing.Color]::FromArgb(45, 45, 48)

function Add-Btn {
    param($txt, $top, $color, $click)
    $b = New-Object Windows.Forms.Button
    $b.Text = $txt; $b.Top = $top; $b.Left = 10; $b.Width = 180; $b.Height = 45; $b.FlatStyle = "Flat"
    $b.BackColor = $color; $b.Add_Click($click)
    $side.Controls.Add($b)
}

# --- LÓGICA DE NAVEGACIÓN ---
function Refresh-Explorer {
    $listView.Items.Clear()
    try {
        if ($global:currentPath -eq "__NETWORK__") {
            $lblPath.Text = " Ubicación: Red Local (Equipos detectados)"
            $config = Get-Content $configPath | ConvertFrom-Json
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
            $lblPath.Text = " Ubicación: $($global:currentComputer) > Unidades"
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
            $lblPath.Text = " Ubicación: $($global:currentComputer) > $global:currentPath"
            $files = Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock {
                param($p) Get-ChildItem -Path $p | Select-Object Name, PSIsContainer, Length, LastWriteTime
            } -ArgumentList $global:currentPath
            foreach ($f in $files) {
                $item = New-Object Windows.Forms.ListViewItem($f.Name)
                $type = if($f.PSIsContainer){ "Carpeta" } else { "$([math]::Round($f.Length/1KB,1)) KB" }
                $item.SubItems.Add($type) | Out-Null
                $item.SubItems.Add("") | Out-Null # Espacio para Estado
                $item.SubItems.Add($f.LastWriteTime.ToString("dd/MM/yyyy HH:mm")) | Out-Null
                $item.Tag = @{ Type=(if($f.PSIsContainer){"Dir"}else{"File"}); Path=(Join-Path $global:currentPath $f.Name) }
                if($f.PSIsContainer){ $item.ForeColor = [Drawing.Color]::Yellow }
                $listView.Items.Add($item)
            }
        }
    } catch {
        [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)")
        $global:currentPath = "__NETWORK__"; Refresh-Explorer
    }
}

$listView.Add_DoubleClick({
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        if ($data.Type -eq "PC") {
            $global:currentComputer = $data.IP
            $global:currentPath = "__DRIVES__"
            Refresh-Explorer
        }
        elseif ($data.Type -eq "Drive" -or $data.Type -eq "Dir") {
            $global:currentPath = $data.Path
            Refresh-Explorer
        }
    }
})

# --- BOTONES DE ACCIÓN ---
Add-Btn "ATRÁS" 10 [Drawing.Color]::Gray {
    if ($global:currentPath -eq "__NETWORK__") { return }
    if ($global:currentPath -eq "__DRIVES__") { $global:currentPath = "__NETWORK__"; Refresh-Explorer; return }
    if ($global:currentPath -match '^[A-Za-z]:\\$') { $global:currentPath = "__DRIVES__"; Refresh-Explorer; return }
    $global:currentPath = Split-Path $global:currentPath -Parent
    Refresh-Explorer
}

Add-Btn "COPIAR" 70 [Drawing.Color]::DarkBlue {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        if ($data.Type -eq "File") {
            $global:clipboardFile = @{ PC=$global:currentComputer; Path=$data.Path; Name=(Split-Path $data.Path -Leaf) }
            [Windows.Forms.MessageBox]::Show("Copiado al portapapeles: $($global:clipboardFile.Name)")
        }
    }
}

Add-Btn "PEGAR AQUÍ" 125 [Drawing.Color]::DarkGreen {
    if ($null -eq $global:clipboardFile) { return }
    if ($global:currentPath -eq "__NETWORK__" -or $global:currentPath -eq "__DRIVES__") { return }
    
    try {
        $temp = Join-Path $env:TEMP $global:clipboardFile.Name
        # Origen -> Local
        $s1 = New-PSSession -ComputerName $global:clipboardFile.PC -Credential $cred
        Copy-Item -FromSession $s1 -Path $global:clipboardFile.Path -Destination $temp -Force
        Remove-PSSession $s1
        
        # Local -> Destino
        $s2 = New-PSSession -ComputerName $global:currentComputer -Credential $cred
        Copy-Item -ToSession $s2 -Path $temp -Destination $global:currentPath -Force
        Remove-PSSession $s2
        
        Remove-Item $temp -Force
        Refresh-Explorer
        [Windows.Forms.MessageBox]::Show("Archivo pegado con éxito.")
    } catch { [Windows.Forms.MessageBox]::Show("Error al pegar: $($_.Exception.Message)") }
}

Add-Btn "NUEVA CARPETA" 180 [Drawing.Color]::FromArgb(60, 60, 60) {
    if ($global:currentPath -eq "__NETWORK__" -or $global:currentPath -eq "__DRIVES__") { return }
    $name = [Microsoft.VisualBasic.Interaction]::InputBox("Nombre de la nueva carpeta:", "Crear Carpeta", "Nueva Carpeta")
    if ($name) {
        try {
            Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock { param($p, $n) New-Item -Path (Join-Path $p $n) -ItemType Directory -Force } -ArgumentList $global:currentPath, $name
            Refresh-Explorer
        } catch { [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)") }
    }
}

Add-Btn "RENOMBRAR" 235 [Drawing.Color]::FromArgb(60, 60, 60) {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        $newName = [Microsoft.VisualBasic.Interaction]::InputBox("Nuevo nombre:", "Renombrar", (Split-Path $data.Path -Leaf))
        if ($newName) {
            try {
                Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock { param($p, $n) Rename-Item -Path $p -NewName $n -Force } -ArgumentList $data.Path, $newName
                Refresh-Explorer
            } catch { [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)") }
        }
    }
}

Add-Btn "VISTA PREVIA" 345 [Drawing.Color]::FromArgb(0, 120, 215) {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        if ($data.Type -eq "File") {
            try {
                $text = Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock { param($p) Get-Content $p -TotalCount 100 -ErrorAction SilentlyContinue } -ArgumentList $data.Path
                $viewer = New-Object Windows.Forms.Form
                $viewer.Text = "Vista Previa - " + (Split-Path $data.Path -Leaf)
                $viewer.Size = New-Object Drawing.Size(800, 600)
                $txtBox = New-Object Windows.Forms.TextBox
                $txtBox.Multiline = $true; $txtBox.Dock = "Fill"; $txtBox.ScrollBars = "Both"; $txtBox.Font = New-Object Drawing.Font("Consolas", 10)
                $txtBox.Text = $text -join "`r`n"
                $viewer.Controls.Add($txtBox)
                $viewer.ShowDialog()
            } catch { [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)") }
        }
    }
}

Add-Btn "PROPIEDADES" 400 [Drawing.Color]::FromArgb(60, 60, 60) {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        $form.Cursor = [Windows.Forms.Cursors]::WaitCursor
        try {
            $info = Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock {
                param($p, $t)
                $item = Get-Item $p
                $size = if($t -eq "Dir") { (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum } else { $item.Length }
                return @{ Path=$item.FullName; Size=$size; Created=$item.CreationTime; Modified=$item.LastWriteTime }
            } -ArgumentList $data.Path, $data.Type
            $msg = "Ruta: $($info.Path)`n`nTamaño: $([math]::Round($info.Size/1MB,2)) MB`nCreado: $($info.Created)`nModificado: $($info.Modified)"
            [Windows.Forms.MessageBox]::Show($msg, "Propiedades")
        } catch { [Windows.Forms.MessageBox]::Show("Error: $($_.Exception.Message)") }
        $form.Cursor = [Windows.Forms.Cursors]::Default
    }
}

Add-Btn "ELIMINAR" 455 [Drawing.Color]::DarkRed {
    if ($listView.SelectedItems.Count -gt 0) {
        $data = $listView.SelectedItems[0].Tag
        Invoke-Command -ComputerName $global:currentComputer -Credential $cred -ScriptBlock { param($p) Remove-Item $p -Recurse -Force } -ArgumentList $data.Path
        Refresh-Explorer
    }
}

Add-Btn "ACTUALIZAR" 600 [Drawing.Color]::Black { Refresh-Explorer }

$form.Controls.AddRange(@($listView, $header, $side))
$form.Add_Shown({ Refresh-Explorer })
[Windows.Forms.Application]::Run($form)


