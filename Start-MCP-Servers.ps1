# =============================================================================
# MCP Servers Initializer
# =============================================================================

param([string]$Config = "mcp-config.json")

function Write-MCPLog {
    param (
        [string]$message,
        [string]$level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$level] $message"
}

function Initialize-MCP {
    try {
        Write-MCPLog "Starting MCP Servers initialization..." "INFO"

        # Check if MCP CLI is installed
        if (-not (Get-Command mcp -ErrorAction SilentlyContinue)) {
            Write-MCPLog "MCP CLI not found. Installing..." "WARN"
            npm install -g mcp
        }

        # Check if MCP config exists
        if (-not (Test-Path $Config)) {
            Write-MCPLog "Creating MCP configuration file..." "INFO"
            $mcpConfig = @{
                mcpServers = @{
                    "network-tools" = @{ command = "node"; args = "mcp-servers/network-tools/index.js" }
                    "wol-server" = @{ command = "node"; args = "mcp-servers/wol-server/index.js" }
                    "ping-server" = @{ command = "node"; args = "mcp-servers/ping-server/index.js" }
                    "file-system" = @{ command = "node"; args = "mcp-servers/file-system/index.js" }
                    "smb-server" = @{ command = "node"; args = "mcp-servers/smb-server/index.js" }
                    "ftp-server" = @{ command = "node"; args = "mcp-servers/ftp-server/index.js" }
                    "vscode-server" = @{ command = "node"; args = "mcp-servers/vscode-server/index.js" }
                    "git-server" = @{ command = "node"; args = "mcp-servers/git-server/index.js" }
                    "terminal-server" = @{ command = "node"; args = "mcp-servers/terminal-server/index.js" }
                }
            }
            $mcpConfig | ConvertTo-Json -Depth 3 | Out-File $Config -Encoding UTF8
        }

# Start MCP servers
        Write-MCPLog "Starting MCP servers..." "INFO"
        $mcpConfig = Get-Content $Config | ConvertFrom-Json
        foreach ($serverName in $mcpConfig.mcpServers.PSObject.Properties.Name) {
            $serverConfig = $mcpConfig.mcpServers.$serverName
Write-MCPLog "Starting $serverName..." "INFO"
            Start-Process -FilePath $serverConfig.command -ArgumentList $serverConfig.args
        }

        Write-MCPLog "MCP Servers initialization completed successfully!" "SUCCESS"
    } catch {
        Write-MCPLog "Error initializing MCP Servers: $_" "ERROR"
    }
}

# Start MCP servers
Initialize-MCP