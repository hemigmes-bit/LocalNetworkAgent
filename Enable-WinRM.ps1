Enable-PSRemoting -SkipNetworkProfileCheck -Force
Set-Service -Name WinRM -StartupType Automatic
New-NetFirewallRule -DisplayName "Windows Remote Management (HTTP-In)" -Name "WinRM-HTTP-In" -Profile Public,Private -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985
Write-Host "WinRM habilitado"