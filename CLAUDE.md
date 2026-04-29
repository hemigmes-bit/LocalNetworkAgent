# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local Network Agent - PowerShell-based network management suite for Windows environments with REST API, WebSocket, PWA interface, voice control, and MCP server integration.

## Quick Commands

```powershell
# Run main interactive menu
.\LocalNetworkAgent.ps1

# Launch GUI dashboard
dotnet run --project LocalNetworkAgent\LocalNetworkAgent.csproj

# Start API server (port 8082)
.\API-Server.ps1

# Start voice control
.\VoiceControl.ps1

# Start all MCP servers
.\Start-MCP-Servers.ps1

# Build .NET launcher
dotnet publish LocalNetworkAgent\LocalNetworkAgent.csproj -c Release -r win-x64 --self-contained
```

## Architecture

```
LocalNetworkAgent/
├── LocalNetworkAgent.ps1      # Main PowerShell menu (v2.6.0)
├── API-Server.ps1             # REST API + WebSocket server (port 8082)
├── VoiceControl.ps1           # Windows Speech Recognition integration
├── Launcher.cs                # .NET WinForms dashboard
├── NetworkUtilsPublic.psm1    # Core PowerShell module (all remote functions)
├── network-config.json        # Runtime config (subnet, computers, MAC addresses)
├── mcp-config.json            # MCP servers configuration
├── public/                    # PWA web interface
│   ├── index.html             # Mobile-responsive UI
│   ├── manifest.json          # PWA manifest
│   └── sw.js                  # Service worker (offline support)
├── mcp-servers/               # MCP server implementations
│   ├── network-tools/, wol-server/, ping-server/, file-system/, etc.
└── publish_release/           # Pre-built binaries
```

## Key Components

- **NetworkUtilsPublic.psm1**: Central module containing all network utilities:
  - `Get-NetworkComputers`: Parallel network scanning (60 threads)
  - `Invoke-RemoteCommand`: Remote PowerShell execution
  - `Send-WakeOnLan`: WoL packet sender
  - `Copy-BetweenRemotes`: File transfer between remote machines
  - `Get-StoredCredential`: Credential management (core0-cred.xml)

- **API Server**: Express-like PowerShell HTTP server with:
  - Token-based authentication (api-token.json)
  - REST endpoints for all network operations
  - WebSocket for real-time notifications
  - PWA static file serving

- **MCP Servers**: 9 Node.js-based MCP servers for external tool integration (network-tools, wol-server, file-system, etc.)

## Configuration

- **Subnet**: Configured in `network-config.json` (default: 192.168.1.x)
- **WinRM Port**: 5985 (HTTP), 5986 (HTTPS)
- **API Port**: 8082
- **Credentials**: Stored in `core0-cred.xml` (PSCredential XML export)
- **Core0 MAC**: Stored in config for WoL (B2-C5-13-46-C3-09)

## Development Notes

- Requires PowerShell Remoting enabled on target machines (`Enable-PSRemoting -Force`)
- .NET component targets net10.0-windows (win-x64)
- MCP servers run via Node.js from `mcp-servers/*/index.js`
- Logs written to console; rotation handled internally
