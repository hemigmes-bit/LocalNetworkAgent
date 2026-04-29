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
    return "AWhjR1vKIQorbqSekM6Hs307nx4cOJBp" # Default fallback
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
