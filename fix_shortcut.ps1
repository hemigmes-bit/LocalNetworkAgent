$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$s.TargetPath = "C:\Users\Usuario\LocalNetworkAgent\Iniciar.bat"
$s.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$s.WindowStyle = 7
$s.Save()