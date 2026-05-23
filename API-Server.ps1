# =============================================================================
# API Server v2.4.1 - REST + WebSocket + SCHEDULER
# =============================================================================

param([int]$Port = 8082)

function Write-NetworkLog {
    param (
        [string]$message,
        [string]$level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$level] $message"
    Write-Host $logEntry
    try {
        Add-Content "$PSScriptRoot\network-agent.log" -Value $logEntry -ErrorAction SilentlyContinue
    } catch {}
}

# Import the network utilities module
if (Test-Path "$PSScriptRoot\NetworkUtilsPublic.psm1") {
    Import-Module "$PSScriptRoot\NetworkUtilsPublic.psm1" -Force
}

$ScriptVersion = "2.4.1"
$ApiTokenPath = "$PSScriptRoot\api-token.json"
$Global:ApiRunning = $true

function Get-ApiToken {
    if (Test-Path $ApiTokenPath) {
        $data = Get-Content $ApiTokenPath -Raw | ConvertFrom-Json
        return $data.Token
    }
    return "AWhjR1vKIQorbqSekM6Hs307nx4cOJBp"
}

function Read-RequestBody {
    param([System.Net.HttpListenerRequest]$Request)
    if ($Request.HasEntityBody) {
        $reader = New-Object System.IO.StreamReader($Request.InputStream)
        $body = $reader.ReadToEnd()
        $reader.Close()
        try { return $body | ConvertFrom-Json } catch { return $null }
    }
    return $null
}

function Handle-ApiRequest {
    param (
        [System.Net.HttpListenerRequest]$Request,
        [System.Net.HttpListenerResponse]$Response
    )

    try {
        $url = $Request.Url
        $path = $url.AbsolutePath.TrimEnd('/')
        $method = $request.HttpMethod

        Write-NetworkLog "$method $path" "DEBUG"

        # Get token from header
        $token = $request.Headers["Authorization"]
        if ($token -and $token.StartsWith("Bearer ")) {
            $token = $token.Substring(7)
        }

        # Validate token for non-public endpoints
        $validToken = Get-ApiToken
        if ($path -ne "/api/status" -and $path -ne "") {
            if (-not $token -or $token -ne $validToken) {
                $Response.StatusCode = 401
                $Response.Close()
                return
            }
        }

        $responseData = $null

        # Route handling
        switch -Regex ($path) {
            # Status endpoint
            { $_ -eq "/api/status" -or $_ -eq "" } {
                $responseData = @{ status = "ok"; version = $ScriptVersion; timestamp = Get-Date -Format o } | ConvertTo-Json
                $Response.StatusCode = 200
            }

            # Computers endpoint
            { $_ -eq "/api/computers" } {
                if (Get-Command Get-NetworkConfig -ErrorAction SilentlyContinue) {
                    $config = Get-NetworkConfig
                    $responseData = @{ computers = $config.Computers } | ConvertTo-Json
                    $Response.StatusCode = 200
                } else {
                    $responseData = @{ error = "NetworkUtils module not fully loaded" } | ConvertTo-Json
                    $Response.StatusCode = 500
                }
            }

            # WOL endpoint
            { $_ -eq "/api/wol" -and $method -eq "POST" } {
                $configPath = "$PSScriptRoot\network-config.json"
                if (Test-Path $configPath) {
                    $cfg = Get-Content $configPath -Raw | ConvertFrom-Json
                    $mac = $cfg.Core0MAC
                    if ($mac -and (Get-Command Send-WakeOnLan -ErrorAction SilentlyContinue)) {
                        Send-WakeOnLan -MACAddress $mac
                        $responseData = @{ success = $true; mac = $mac; message = "WoL packet sent" } | ConvertTo-Json
                        $Response.StatusCode = 200
                    } else {
                        $responseData = @{ error = "Core0MAC not configured or NetworkUtils module missing" } | ConvertTo-Json
                        $Response.StatusCode = 500
                    }
                } else {
                    $responseData = @{ error = "network-config.json not found" } | ConvertTo-Json
                    $Response.StatusCode = 500
                }
            }

            # Ping endpoint
            { $_ -eq "/api/ping" -and $method -eq "POST" } {
                $body = Read-RequestBody -Request $Request
                $ip = $body.ip
                if (-not $ip) { $ip = $body.IP }
                if ($ip) {
                    $alive = Test-Connection -ComputerName $ip -Count 1 -Quiet -ErrorAction SilentlyContinue
                    $responseData = @{ ip = $ip; alive = ($alive -eq $true) } | ConvertTo-Json
                    $Response.StatusCode = 200
                } else {
                    $responseData = @{ error = "Missing 'ip' in request body" } | ConvertTo-Json
                    $Response.StatusCode = 400
                }
            }

            # Scan endpoint
            { $_ -eq "/api/scan" -and $method -eq "POST" } {
                $cfg = Get-Content "$PSScriptRoot\network-config.json" -Raw | ConvertFrom-Json
                $subnet = $cfg.SubnetPrefix
                $results = @()
                $jobMap = @{}
                1..20 | ForEach-Object { 
                    $ip = "$subnet.$_"
                    $jobMap[$ip] = Test-Connection -ComputerName $ip -Count 1 -AsJob -ErrorAction SilentlyContinue
                }
                $jobMap.Values | Wait-Job -Timeout 3 | Out-Null
                foreach ($ip in $jobMap.Keys) {
                    $r = $jobMap[$ip] | Receive-Job -ErrorAction SilentlyContinue
                    if ($r -and $r.StatusCode -eq 0) { $results += @{ IP = $ip } }
                    $jobMap[$ip] | Remove-Job -Force -ErrorAction SilentlyContinue
                }
                $responseData = @{ subnet = $subnet; online = $results.Count; devices = $results } | ConvertTo-Json
                $Response.StatusCode = 200
            }

            # Speak endpoint
            { $_ -eq "/api/speak" -and $method -eq "POST" } {
                $body = Read-RequestBody -Request $Request
                $text = $body.text
                $ip = $body.ip
                if ($text -and $ip) {
                    $script = "$PSScriptRoot\Speak-Remote.ps1"
                    if (Test-Path $script) {
                        Start-Process powershell.exe -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -ComputerName $ip -Message `"$text`"" -WindowStyle Hidden
                        $responseData = @{ success = $true; ip = $ip; text = $text } | ConvertTo-Json
                        $Response.StatusCode = 200
                    } else {
                        $responseData = @{ error = "Speak-Remote.ps1 not found" } | ConvertTo-Json
                        $Response.StatusCode = 500
                    }
                } else {
                    $responseData = @{ error = "Missing 'text' or 'ip' in request body" } | ConvertTo-Json
                    $Response.StatusCode = 400
                }
            }

            # Shell endpoint
            { $_ -eq "/api/shell" -and $method -eq "POST" } {
                $body = Read-RequestBody -Request $Request
                $command = $body.command
                $ip = $body.ip
                if ($command -and $ip) {
                    try {
                        $credFile = "$PSScriptRoot\core0-cred.xml"
                        $out = if ($ip -eq "192.168.1.14" -or $ip -eq "localhost") {
                            Invoke-Expression $command 2>&1 | Out-String
                        } elseif (Test-Path $credFile) {
                            $cred = Import-CliXml $credFile
                            Invoke-Command -ComputerName $ip -Credential $cred -ScriptBlock { param($c) Invoke-Expression $c 2>&1 } -ArgumentList $command | Out-String
                        } else {
                            Invoke-Command -ComputerName $ip -ScriptBlock { param($c) Invoke-Expression $c 2>&1 } -ArgumentList $command | Out-String
                        }
                        $responseData = @{ success = $true; ip = $ip; output = $out.Trim() } | ConvertTo-Json
                        $Response.StatusCode = 200
                    } catch {
                        $responseData = @{ success = $false; ip = $ip; error = $_.Exception.Message } | ConvertTo-Json
                        $Response.StatusCode = 500
                    }
                } else {
                    $responseData = @{ error = "Missing 'command' or 'ip' in request body" } | ConvertTo-Json
                    $Response.StatusCode = 400
                }
            }

            default {
                $Response.StatusCode = 404
            }
        }

        if ($null -ne $responseData) {
            $Response.ContentType = "application/json"
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($responseData)
            $Response.ContentLength64 = $buffer.Length
            $Response.OutputStream.Write($buffer, 0, $buffer.Length)
        }

    } catch {
        Write-NetworkLog "Error processing request: $_" "ERROR"
        $Response.StatusCode = 500
    } finally {
        try { $Response.Close() } catch {}
    }
}

function Stop-LocalPort {
    param([int]$port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            Write-NetworkLog "Stopping process $($conn.OwningProcess) using port $port" "WARN"
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Start-ApiServer {
    Stop-LocalPort $Port
    
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://+:$Port/")
    
    try {
        $listener.Start()
        Write-NetworkLog "API Server v$ScriptVersion started on port $Port" "INFO"

        while ($Global:ApiRunning -and $listener.IsListening) {
            try {
                $context = $listener.GetContext()
                Handle-ApiRequest -Request $context.Request -Response $context.Response
            } catch {
                if ($Global:ApiRunning) {
                    Write-NetworkLog "Listener error: $_" "ERROR"
                }
            }
        }
    } catch {
        Write-NetworkLog "Failed to start listener: $_" "ERROR"
    } finally {
        if ($listener) {
            $listener.Stop()
            $listener.Close()
        }
    }
}

# Execution
Start-ApiServer
