$user = $env:USERNAME
$sshDir = "$env:USERPROFILE\.ssh"
$authFile = "$sshDir\authorized_keys"

# Deshabilitar herencia y limpiar permisos
icacls $sshDir /inheritance:r
icacls $sshDir /grant "SYSTEM:(F)"
icacls $sshDir /grant "${user}:(F)"

if (Test-Path $authFile) {
    icacls $authFile /inheritance:r
    icacls $authFile /grant "SYSTEM:(F)"
    icacls $authFile /grant "${user}:(R)"
}
Write-Host "Permisos SSH corregidos para $user"
