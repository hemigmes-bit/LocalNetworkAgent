$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File C:\Users\Usuario\LocalNetworkAgent\block-roblox-victorymar.ps1'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(30)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'BlockRobloxVictorymar' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Start-ScheduledTask -TaskName 'BlockRobloxVictorymar'
Write-Host "Scheduled task created and started"