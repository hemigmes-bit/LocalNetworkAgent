$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$s.TargetPath = "C:\Windows\System32\wscript.exe"
$s.Arguments = """C:\Users\Usuario\LocalNetworkAgent\Iniciar.vbs"""
$s.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$s.WindowStyle = 7
$s.Save()
Write-Host "OK"