Remove-NetFirewallRule -DisplayName "Block-YouTube-TV-172_217_0_0_16" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Block-YouTube-TV-142_250_0_0_15" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Block-YouTube-TV-209_85_0_0_17" -ErrorAction SilentlyContinue
Write-Host "Reglas eliminadas"