& {
    netsh advfirewall firewall delete rule name="Block-YouTube-TV-172_217_0_0_16"
    netsh advfirewall firewall delete rule name="Block-YouTube-TV-142_250_0_0_15"
    netsh advfirewall firewall delete rule name="Block-YouTube-TV-209_85_0_0_17"
    Write-Host "Reglas de YouTube eliminadas"
}