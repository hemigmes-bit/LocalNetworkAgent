Write-Host "Configurando WinRM..."
winrm quickconfig -Force
Write-Host "Verificando..."
netstat -an | findstr 5985
Write-Host "Listo"