$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c C:\Users\Usuario\LocalNetworkAgent\block-roblox-netsh2.bat'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'BlockRobloxDirect' -Action $action -Trigger $trigger -Principal $principal -Force
Start-ScheduledTask -TaskName 'BlockRobloxDirect'
Write-Host "Task created"