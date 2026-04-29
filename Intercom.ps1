param([string]$ComputerName = "192.168.1.14")

Write-Host "Iniciando intercomunicador con $ComputerName..." -ForegroundColor Cyan

try {
    $cred = Get-Credential -UserName "Administrador" -Message "Credenciales para abrir ventana en $ComputerName"
    
    # El truco para abrir una ventana en la sesion del usuario es usar una tarea programada
    # que se ejecute bajo el grupo "Users" de forma interactiva.
    Invoke-Command -ComputerName $ComputerName -Credential $cred -ScriptBlock {
        $taskName = "RemoteIntercom"
        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/K echo === INTERCOMUNICADOR ACTIVADO === && echo Escribe aqui para hablar con el administrador. && echo ================================="
        
        # Registrar y ejecutar inmediatamente
        Register-ScheduledTask -TaskName $taskName -Action $action -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName
        
        Start-Sleep -Seconds 5
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    Write-Host "Ventana abierta en el escritorio remoto de $ComputerName." -ForegroundColor Green
    Write-Host "Cerrando en 3 segundos..."
    Start-Sleep -Seconds 3
} catch {
    [Windows.Forms.MessageBox]::Show("Error al lanzar intercom: " + $_.Exception.Message)
}
