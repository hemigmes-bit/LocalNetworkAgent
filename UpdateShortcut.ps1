$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1`" 2>`$null"
$s.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$s.Description = "LocalNetworkAgent"
$s.Save()
Write-Host "OK"