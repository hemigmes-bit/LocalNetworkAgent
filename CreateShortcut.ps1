$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$Shortcut.TargetPath = "C:\Users\Usuario\LocalNetworkAgent\Iniciar.bat"
$Shortcut.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$Shortcut.WindowStyle = 7
$Shortcut.Save()