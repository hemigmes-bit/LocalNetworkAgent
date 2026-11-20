$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "cmd.exe"
$psi.Arguments = '/c C:\Users\Usuario\LocalNetworkAgent\block-roblox-netsh.bat'
$psi.Verb = "RunAs"
$psi.UseShellExecute = $true
$p = [System.Diagnostics.Process]::Start($psi)
$p.WaitForExit(30000)
Write-Host "Exit code: " $p.ExitCode