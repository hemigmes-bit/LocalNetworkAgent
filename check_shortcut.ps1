$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
Write-Host "Target: $($shortcut.TargetPath)"
Write-Host "Args: $($shortcut.Arguments)"
Write-Host "Working: $($shortcut.WorkingDirectory)"