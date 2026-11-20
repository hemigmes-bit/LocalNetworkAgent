# Fix-RustDeskCustomServer.ps1 - Elimina custom-rendezvous-server del servicio RustDesk
$results = @()
$targets = @(
    "C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config\RustDesk2.toml",
    "C:\Windows\System32\config\systemprofile\AppData\Roaming\RustDesk\config\RustDesk2.toml",
    "$env:APPDATA\RustDesk\config\RustDesk2.toml"
)
$changed = $false
foreach ($t in $targets) {
    if (Test-Path $t) {
        try {
            $lines = Get-Content $t -ErrorAction Stop
            if ($lines | Select-String "^custom-rendezvous-server") {
                $lines = $lines | Where-Object { $_ -notmatch "^custom-rendezvous-server" }
                $lines | Set-Content $t -Encoding UTF8
                $results += "LIMPIADO: $t"
                $changed = $true
            } else {
                $results += "SIN CAMBIOS: $t"
            }
        } catch {
            $results += "ERROR en $t : $($_.Exception.Message)"
        }
    } else {
        $results += "NO EXISTE: $t"
    }
}

if ($changed) {
    Restart-Service -Name "RustDesk" -Force -ErrorAction SilentlyContinue
    $results += "Servicio RustDesk reiniciado"
}

$results | Set-Content "C:\Users\Usuario\LocalNetworkAgent\rustdesk-fix-result.txt" -Encoding UTF8
