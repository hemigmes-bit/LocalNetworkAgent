param([string]$IP, [string]$ADB)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- ADB setup ---
try {
    & $ADB connect "$IP`:5555" 2>&1 | Out-Null
    $adbConnected = $true
} catch {
    $adbConnected = $false
    Write-Warning "ADB connect failed: $_"
}

$global:currentPath = "/sdcard"
$global:history = [System.Collections.ArrayList]::new()
$global:historyIndex = -1
$global:dirCache = @{}
$script:listUpdateLock = [System.Object]::new()

# --- ADB helpers ---
function Get-ADBOutput {
    param([string]$cmd, [int]$timeoutMs = 10000)
    $proc = Start-Process -FilePath $ADB -ArgumentList "-s", "$IP`:5555", "shell", $cmd -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Warning "ADB exit code: $($proc.ExitCode) for: $cmd"
    }
    return $proc.StandardOutput.ReadToEnd().Trim()
}

function Get-FileTypeIcon {
    param([string]$name, [bool]$isDir)
    if ($isDir) { return "[DIR]" }
    $ext = [System.IO.Path]::GetExtension($name).ToLower()
    if ($ext -in ".jpg",".jpeg",".png",".gif",".bmp",".webp") { return "[IMG]" }
    if ($ext -in ".mp4",".avi",".mkv",".mov",".webm") { return "[VID]" }
    if ($ext -in ".mp3",".wav",".flac",".aac",".ogg") { return "[AUD]" }
    if ($ext -in ".zip",".rar",".tar",".gz",".7z") { return "[ZIP]" }
    if ($ext -in ".pdf",".doc",".docx",".xls",".xlsx",".txt") { return "[DOC]" }
    if ($ext -in ".apk") { return "[APK]" }
    return "[FIL]"
}

function Parse-LsOutput {
    param([string]$raw, [bool]$dirsOnly = $false)
    if (-not $raw) { return @() }
    $entries = [System.Collections.ArrayList]::new()
    $lines = $raw -split "`n" | Where-Object { $_ -match "^-|^d|^l" -and $_ -notmatch "^\s*$" -and $_ -notmatch "^total" }
    foreach ($line in $lines) {
        $parts = $line.Trim() -split "\s+"
        if ($parts.Count -lt 8) { continue }
        $perms = $parts[0]
        $isDir = $perms.StartsWith("d")
        $isLink = $perms.StartsWith("l")
        if ($dirsOnly -and -not $isDir -and -not $isLink) { continue }
        $size = $parts[4]
        $dateParts = $parts[5..7] -join " "
        $name = $parts[8..$parts.Count] -join " "
        if ($name -match "^\.\.?$" -or $name -eq "lost+found") { continue }
        $isNavigable = $isDir -or $isLink
        $entry = @{
            Name       = $name
            IsDir      = $isNavigable
            IsLink     = $isLink
            Size       = $size
            Date       = $dateParts
            Permissions = $perms
        }
        $entries.Add($entry) | Out-Null
    }
    return $entries
}

function Get-Listing {
    param([string]$path, [bool]$dirsOnly = $false, [bool]$forceRefresh = $false)
    $path = $path.TrimEnd('/')
    if (-not $forceRefresh -and $global:dirCache.ContainsKey($path)) {
        return $global:dirCache[$path]
    }
    $raw = Get-ADBOutput "ls -la ${path}/"
    $entries = Parse-LsOutput $raw $dirsOnly
    $global:dirCache[$path] = $entries
    return $entries
}

# --- Form ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "ADB Explorer - $IP"
$form.Size = New-Object System.Drawing.Size(1100, 700)
$form.MinimumSize = New-Object System.Drawing.Size(800, 500)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 45)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)

# ========== TOOLBAR ==========
$toolbar = New-Object System.Windows.Forms.Panel
$toolbar.Dock = "Top"
$toolbar.Height = 48
$toolbar.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 60)
$toolbar.Padding = New-Object System.Windows.Forms.Padding(4)
$form.Controls.Add($toolbar)

function Add-ToolBtn {
    param([string]$text, [int]$x, [scriptblock]$click, [string]$bg = "#505070", [int]$w = 60)
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.Location = New-Object System.Drawing.Point($x, 6)
    $b.Size = New-Object System.Drawing.Size($w, 34)
    $b.FlatStyle = "Flat"
    $b.FlatAppearance.BorderSize = 0
    $b.ForeColor = [System.Drawing.Color]::White
    $b.BackColor = [System.Drawing.Color]::FromArgb([System.Int32]("0x$($bg.Substring(1))"))
    $b.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $b.Cursor = [System.Windows.Forms.Cursors]::Hand
    $b.Add_Click($click)
    $toolbar.Controls.Add($b)
    return $b
}

# Navigation buttons
$btnBack = Add-ToolBtn "<" 4  { NavigateHistory -1 } "#3a3a5a" 30
$btnFwd  = Add-ToolBtn ">" 40 { NavigateHistory 1 } "#3a3a5a" 30
$btnUp   = Add-ToolBtn "^" 76  { NavigateUp } "#5a3a3a" 30
$btnRef  = Add-ToolBtn "R" 112 { NavigateTo $global:currentPath -ForceRefresh } "#3a5a3a" 30

# Address bar
$addrBox = New-Object System.Windows.Forms.TextBox
$addrBox.Location = New-Object System.Drawing.Point(148, 8)
$addrBox.Size = New-Object System.Drawing.Size(480, 30)
$addrBox.BackColor = [System.Drawing.Color]::FromArgb(20, 20, 35)
$addrBox.ForeColor = [System.Drawing.Color]::Lime
$addrBox.BorderStyle = "FixedSingle"
$addrBox.Font = New-Object System.Drawing.Font("Cascadia Code", 10)
$addrBox.Add_KeyDown({ if ($_.KeyCode -eq "Enter") { ValidateAndNavigate $addrBox.Text } })
$toolbar.Controls.Add($addrBox)

# Quick buttons
Add-ToolBtn "SDCARD" 640  { ValidateAndNavigate "/sdcard" } "#3a5a3a" 65
Add-ToolBtn "DCIM"   710  { ValidateAndNavigate "/sdcard/DCIM" } "#3a5a3a" 55
Add-ToolBtn "Dwnld"  770  { ValidateAndNavigate "/sdcard/Download" } "#3a5a3a" 60
Add-ToolBtn "Root"   840  { ValidateAndNavigate "/" } "#5a3a3a" 50

# ========== SPLIT CONTAINER ==========
$split = New-Object System.Windows.Forms.SplitContainer
$split.Dock = "Fill"
$split.SplitterDistance = 260
$split.SplitterWidth = 4
$split.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 80)
$split.Panel1MinSize = 150
$split.Panel2MinSize = 100
$form.Controls.Add($split)

# ========== LEFT: TREE VIEW ==========
$tree = New-Object System.Windows.Forms.TreeView
$tree.Dock = "Fill"
$tree.BackColor = [System.Drawing.Color]::FromArgb(15, 15, 30)
$tree.ForeColor = [System.Drawing.Color]::White
$tree.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$tree.BorderStyle = "None"
$tree.ShowLines = $true
$tree.ShowRootLines = $true
$tree.LineColor = [System.Drawing.Color]::FromArgb(60, 60, 80)
$tree.HideSelection = $false
$tree.Indent = 16

$tree.Add_AfterSelect({
    if ($_.Node.Tag -and $_.Node.Tag -ne $global:currentPath) {
        ValidateAndNavigate $_.Node.Tag
    }
})

$tree.Add_BeforeExpand({
    $_.Node.Nodes.Clear()
    Load-TreeChildren $_.Node $_.Node.Tag
})

$split.Panel1.Controls.Add($tree)

# ========== RIGHT: LIST VIEW ==========
$list = New-Object System.Windows.Forms.ListView
$list.Dock = "Fill"
$list.BackColor = [System.Drawing.Color]::FromArgb(15, 15, 30)
$list.ForeColor = [System.Drawing.Color]::White
$list.View = "Details"
$list.FullRowSelect = $true
$list.GridLines = $true
$list.BorderStyle = "None"
$list.Font = New-Object System.Drawing.Font("Segoe UI", 9)
  $list.AllowColumnReorder = $true
  $list.Sorting = "None"

$colName = $list.Columns.Add("Nombre", 350) | Out-Null
$colType = $list.Columns.Add("Tipo", 90) | Out-Null
$colSize = $list.Columns.Add("Tama" + [char]0x6F + "o", 100) | Out-Null
$colDate = $list.Columns.Add("Fecha", 170) | Out-Null

$script:sortColumn = -1
$script:sortOrder = "Ascending"

$list.Add_ColumnClick({
    if ($script:sortColumn -eq $_.Column) {
        $script:sortOrder = if ($script:sortOrder -eq "Ascending") { "Descending" } else { "Ascending" }
    } else {
        $script:sortColumn = $_.Column
        $script:sortOrder = "Ascending"
    }
    $list.Sorting = $script:sortOrder
    $list.ListViewItemSorter = New-Object System.Windows.Forms.ListViewItemComparer($_.Column, $script:sortOrder)
})

$list.Add_DoubleClick({
    if ($list.SelectedItems.Count -eq 0) { return }
    $tag = $list.SelectedItems[0].Tag
    if ($tag -and $tag.IsDir) {
        ValidateAndNavigate $tag.FullPath
    }
})

$list.Add_ItemSelectionChanged({
    # Solo actuar en selección, no en deselección
    if ($_.IsSelected -and $list.SelectedItems.Count -gt 0) {
        $tag = $list.SelectedItems[0].Tag
        if ($tag) {
            if ($tag.IsDir) {
                $stItem.Text = "[DIR] $($tag.Name)  -  Doble clic para entrar"
            } else {
                $stItem.Text = "[FIL] $($tag.Name)"
            }
        }
    }
})

# ListView context menu
$ctxMenu = New-Object System.Windows.Forms.ContextMenuStrip
$ctxMenu.Items.Add("Abrir", $null, { }).Name = "ctxOpen"
$ctxMenu.Items.Add("Propiedades", $null, { }).Name = "ctxProps"
$list.ContextMenuStrip = $ctxMenu

$split.Panel2.Controls.Add($list)

# ========== STATUS BAR ==========
$statusBar = New-Object System.Windows.Forms.StatusStrip
$statusBar.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 40)
$statusBar.ForeColor = [System.Drawing.Color]::Gray
$statusBar.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$statusBar.SizingGrip = $false

$stPath = New-Object System.Windows.Forms.ToolStripStatusLabel
$stPath.Text = "  Preparado  "
$stPath.Spring = $true
$stPath.TextAlign = "MiddleLeft"

$stItem = New-Object System.Windows.Forms.ToolStripStatusLabel
$stItem.Text = ""
$stItem.TextAlign = "MiddleLeft"
$stItem.AutoSize = $true

$stCount = New-Object System.Windows.Forms.ToolStripStatusLabel
$stCount.Text = ""
$stCount.TextAlign = "MiddleRight"
$stCount.AutoSize = $true

$statusBar.Items.Add($stPath) | Out-Null
$statusBar.Items.Add($stItem) | Out-Null
$statusBar.Items.Add($stCount) | Out-Null
$form.Controls.Add($statusBar)

# ========== NAVIGATION ENGINE ==========
function ValidateAndNavigate {
    param([string]$path, [switch]$ForceRefresh)
    $path = $path.Trim()
    if (-not $path) { return }
    $path = $path.TrimEnd('/')
    if ([string]::IsNullOrEmpty($path)) { $path = "/" }
    if (-not $path.StartsWith("/")) { $path = "/$path" }
    NavigateTo $path -ForceRefresh $ForceRefresh
}

function NavigateTo {
    param([string]$path, [switch]$ForceRefresh)
    $path = $path.TrimEnd('/')
    if ([string]::IsNullOrEmpty($path)) { $path = "/" }

    $stPath.Text = "  Cargando...  "
    $stCount.Text = ""
    $list.Items.Clear()
    $list.ListViewItemSorter = $null
    [System.Windows.Forms.Application]::DoEvents()

try {
    $entries = Get-Listing $path -ForceRefresh $ForceRefresh
} catch {
    $stPath.Text = "  Error: $($_.Exception.Message)  "
    return
}

    $dirs = [System.Collections.ArrayList]::new()
    $files = [System.Collections.ArrayList]::new()

    foreach ($entry in $entries) {
        $isNavigable = $entry.IsDir
        $icon = Get-FileTypeIcon $entry.Name $isNavigable
        $typeStr = if ($entry.IsDir) { "Carpeta" } elseif ($entry.IsLink) { "Enlace" } else { "Archivo" }

        if (-not $entry.IsDir -and -not $entry.IsLink) {
            $size = [long]$entry.Size
            if ($size -ge 1MB) { $sizeStr = "{0:N1} MB" -f ($size / 1MB) }
            elseif ($size -ge 1KB) { $sizeStr = "{0:N1} KB" -f ($size / 1KB) }
            else { $sizeStr = "$size B" }
        } else { $sizeStr = "-" }

        $cleanPath = $path.TrimEnd('/')
        $it = New-Object System.Windows.Forms.ListViewItem("$icon $entry.Name")
        $it.SubItems.Add($typeStr) | Out-Null
        $it.SubItems.Add($sizeStr) | Out-Null
        $it.SubItems.Add($entry.Date) | Out-Null
        $it.Tag = @{ Name = $entry.Name; IsDir = $isNavigable; FullPath = "$cleanPath/$entry.Name" }
        $it.ForeColor = if ($isNavigable) { [System.Drawing.Color]::Cyan } else { [System.Drawing.Color]::White }

        if ($isNavigable) { $dirs.Add($it) | Out-Null } else { $files.Add($it) | Out-Null }
    }

    # Carpeta primero, luego archivos
    foreach ($d in $dirs) { $list.Items.Add($d) | Out-Null }
    foreach ($f in $files) { $list.Items.Add($f) | Out-Null }

    # Actualizar ruta
    $global:currentPath = $path
    $addrBox.Text = $path

    # Historial (evitar duplicados consecutivos)
    if ($global:history.Count -eq 0 -or $global:history[$global:history.Count-1] -ne $path) {
        if ($global:historyIndex -lt $global:history.Count-1) {
            $global:history = [System.Collections.ArrayList]::new($global:history[0..$global:historyIndex])
        }
        $global:history.Add($path) | Out-Null
        $global:historyIndex = $global:history.Count - 1
    }
    Update-NavButtons

    # Actualizar TreeView
    Sync-TreeSelection $path

    $folderStr = if ($dirs.Count -eq 1) { "1 carpeta" } else { "$($dirs.Count) carpetas" }
    $fileStr = if ($files.Count -eq 1) { "1 archivo" } else { "$($files.Count) archivos" }
    $stPath.Text = "  $path  "
    $stCount.Text = "  $folderStr, $fileStr  "
}

function Update-NavButtons {
    $btnBack.Enabled = $global:historyIndex -gt 0
    $btnFwd.Enabled = $global:historyIndex -lt ($global:history.Count - 1)
}

function NavigateHistory {
    param([int]$delta)
    $newIndex = $global:historyIndex + $delta
    if ($newIndex -ge 0 -and $newIndex -lt $global:history.Count) {
        $global:historyIndex = $newIndex
        NavigateTo $global:history[$global:historyIndex]
    }
}

function NavigateUp {
    $parent = Get-UnixParent $global:currentPath
    if ($parent -and $parent -ne $global:currentPath) {
        NavigateTo $parent
    }
}

function Get-UnixParent {
    param([string]$path)
    $path = $path.TrimEnd('/')
    if ($path -eq "/" -or $path -eq "") { return "/" }
    $lastSlash = $path.LastIndexOf('/')
    if ($lastSlash -le 0) { return "/" }
    return $path.Substring(0, $lastSlash)
}

function Sync-TreeSelection {
    param([string]$path)
    $parts = $path.Trim('/').Split('/')
    $node = $tree.Nodes[0]
    if (-not $node) { return }

    for ($i = 0; $i -lt $parts.Count -and $node -ne $null; $i++) {
        $child = $node.Nodes | Where-Object { $_.Text -eq $parts[$i] -and $_.Tag -eq (($parts[0..$i] -join '/') -replace '^', '/') }
        if ($child) {
            $node = $child[0]
        } else {
            break
        }
    }
    if ($node) {
        $tree.SelectedNode = $node
    }
}

# ========== TREE POPULATION ==========
function Build-Tree {
    $tree.Nodes.Clear()
    $root = New-Object System.Windows.Forms.TreeNode
    $root.Text = "/ (root)"
    $root.Tag = "/"
    $root.ForeColor = [System.Drawing.Color]::White
    $root.NodeFont = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $dummy = New-Object System.Windows.Forms.TreeNode
    $dummy.Text = "..."
    $root.Nodes.Add($dummy) | Out-Null
    $tree.Nodes.Add($root) | Out-Null
}

function Load-TreeChildren {
    param([System.Windows.Forms.TreeNode]$parentNode, [string]$dirPath)
    $entries = Get-Listing $dirPath -dirsOnly
    if (-not $entries) { return }
    foreach ($entry in $entries) {
        $fullPath = "$dirPath/$entry.Name" -replace "//", "/"
        $child = New-Object System.Windows.Forms.TreeNode
        $child.Text = $entry.Name
        $child.Tag = $fullPath
        $child.ForeColor = [System.Drawing.Color]::Cyan

        $dummy = New-Object System.Windows.Forms.TreeNode
        $dummy.Text = "..."
        $child.Nodes.Add($dummy) | Out-Null

$parentNode.Nodes.Add($child) | Out-Null
        }
}

# ========== INIT ==========
Build-Tree
NavigateTo $global:currentPath

$form.Add_Shown({ $list.Focus() })
$form.ShowDialog() | Out-Null