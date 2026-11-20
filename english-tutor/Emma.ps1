Set-Location -LiteralPath $PSScriptRoot
try { $Host.UI.RawUI.WindowTitle = 'Emma - English Tutor' } catch { }
$py = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python.exe -ErrorAction SilentlyContinue }
if (-not $py) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('No se encontro Python. Instala Python 3.12 desde python.org', 'Emma - Error')
    exit 1
}
try {
    Start-Process -FilePath $py.Source -ArgumentList @('emma_gui.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host 'Emma no pudo arrancar. Pulsa Enter para cerrar'
}
