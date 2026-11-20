$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File C:\Users\Usuario\LocalNetworkAgent\block-roblox-hosts-admin2.ps1'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'BlockRobloxHosts' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Start-ScheduledTask -TaskName 'BlockRobloxHosts'
Write-Host "Scheduled task created and started"