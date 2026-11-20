$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1`""
$shortcut.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$shortcut.Description = "LocalNetworkAgent GUI"
$shortcut.Save()
Write-Host "Acceso directo creado en escritorio"