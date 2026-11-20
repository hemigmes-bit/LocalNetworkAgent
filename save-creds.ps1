$projectPath = "C:\Users\Usuario\LocalNetworkAgent"
$outFile = Join-Path $projectPath "victorymar-cred.xml"

$username = $env:USERNAME
$password = Read-Host -AsSecureString "Password for $username"

$cred = New-Object System.Management.Automation.PSCredential($username, $password)
$cred | Export-CliXml $outFile
Write-Host "Saved to $outFile"