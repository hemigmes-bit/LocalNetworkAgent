$pubKey = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDpOHctt5PEZfWFn5JwgkqtkZ7MkbeT384ZMzEPuX9OBxA3K9fsb9FQQWksMO0nZ0OOCDV4MKtdWH3vp0z2+baVsnrljmmmHmunGVRYRv1TQG8BZi/IVBbMKYInV7mkWch+GbuvEqsjASoNDp+6mtHAw8c7A6ycVAOGj59V3GkoSrPrOL0Zslfj2Qd1YUdLawX3MLHgpvmRsGI02iSWW2jY087yzNNPiT8wJ223yeResLeJR/7RUtjC+fIfHSIVFZJoLOlP9pRLde2OG5ep3kCX4aQQaHah5s4jHfbKFzKlWmCGPZUp1W5F1F5Xi6e2HQnQcIg57gU6yq/y4rhAKCiu+5PzW3oIYlnFZ51jr14yELNLlXvjZ2OBQbbSI8ksDg3gXVqOeYAPeVFfnqc4TBbnVJpVKZKQVOfIS9aBJZ+SBif4VmbAEyPW08ccT/8IDC0mQK+r8H4+sG36hbt+VWAwfS2S3C0iSpbPJrMs8CAjh8D2KnNqBTjeAo/2ffC5dqk= usuario@VICTORYMAR'
$adminKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $adminKeys)) { Set-Content -Path $adminKeys -Value $pubKey -Force }
else {
    $content = Get-Content $adminKeys
    if ($content -notcontains $pubKey) { Add-Content -Path $adminKeys -Value $pubKey -Force }
}
icacls $adminKeys /inheritance:r
icacls $adminKeys /grant "SYSTEM:(F)"
icacls $adminKeys /grant "Administrators:(F)"
Write-Host "Clave a?adida a administrators_authorized_keys"
