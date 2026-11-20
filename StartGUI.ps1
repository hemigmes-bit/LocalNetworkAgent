# Start GUI - mata procesos antiguos e inicia
$env:POSHTERM_REHYDRATE_PROCESS = "0" 1>$null 2>$null

# Matar procesos antiguos
Get-Process powershell* -EA SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -EA SilentlyContinue

# Iniciar GUI
Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1`"" -WindowStyle Hidden