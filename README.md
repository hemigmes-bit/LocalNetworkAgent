# Local Network Agent v2.4.1

Gestor de red local Windows — escaneo, archivos remotos, shell, monitor, API REST.

## Inicio rápido

```powershell
# Doble clic en:
Iniciar.bat

# O desde PowerShell:
powershell -ExecutionPolicy Bypass -File "C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1"
```

## Funcionalidades

| Botón | Función |
|---|---|
| **ARCHIVOS** | Explorador de archivos remotos (copiar/pegar entre PCs) |
| **SHELL** | Consola PowerShell remota (Enter-PSSession) |
| **WOL** | Encender CORE0 por Wake-on-LAN |
| **VOZ** | Mensaje de voz al PC remoto |
| **CHAT** | Chat en tiempo real |
| **MONITOR** | Ver pantalla remota en vivo |

## API REST (puerto 8082)

Auto-arranca con la GUI. Token en `api-token.json`.

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/status` | Estado del servidor |
| GET | `/api/computers` | Dispositivos configurados |
| POST | `/api/ping` | Ping a IP `{"ip":"..."}` |
| POST | `/api/scan` | Escanear red (.1-.20) |
| POST | `/api/wol` | Wake-on-LAN a CORE0 |
| POST | `/api/speak` | Voz remota `{"text":"...","ip":"..."}` |
| POST | `/api/shell` | Comando remoto `{"command":"...","ip":"..."}` |

Autenticación: `Authorization: Bearer <token>`

## Configuración

`network-config.json`:
```json
{
    "SubnetPrefix": "192.168.1",
    "Computers": [
        {"Name": "livebox.home", "IP": "192.168.1.1", "OpenPorts": "80,443"},
        {"Name": "CORE0", "IP": "192.168.1.14", "OpenPorts": "5985"},
        {"Name": "VICTORYMAR.home", "IP": "192.168.1.18", "OpenPorts": "5985"}
    ],
    "Core0MAC": "5C:85:7E:41:80:2B"
}
```

## Archivos protegidos (no borrar)

- `LocalNetworkAgent-GUI.ps1` — GUI principal
- `Explorer_Agent.ps1` — Explorador de archivos remotos
- `NetworkUtilsPublic.psm1` — Módulo de utilidades de red
- `API-Server.ps1` — API REST (token en `api-token.json`)
- `network-config.json` — Configuración de dispositivos
- `Iniciar.bat` / `Iniciar.vbs` — Entry points
- `core0-cred.xml` / `victorymar-cred.xml` — Credenciales (no compartir)
- `AGENTS.md` — Instrucciones del asistente

## Restaurar desde backup

### 1. Descomprimir

```powershell
Expand-Archive -Path "$env:USERPROFILE\Desktop\LocalNetworkAgent_backup_*.zip" -DestinationPath "C:\Users\Usuario\LocalNetworkAgent" -Force
```

### 2. Restaurar dependencias npm

```powershell
cd C:\Users\Usuario\LocalNetworkAgent
npm install
```

### 3. Crear acceso directo

```powershell
$sh = New-Object -COM WScript.Shell
$lnk = $sh.CreateShortcut("$env:USERPROFILE\Desktop\LocalNetworkAgent.lnk")
$lnk.TargetPath = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1"'
$lnk.WorkingDirectory = "C:\Users\Usuario\LocalNetworkAgent"
$lnk.Save()
```

### 4. Verificar

```powershell
# Probar que arranca
C:\Users\Usuario\LocalNetworkAgent\Iniciar.bat
```

### 5. Configurar WinRM en equipos remotos (si es necesario)

```powershell
Enable-PSRemoting -Force
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "192.168.1.14" -Force
```

## Requisitos

- Windows 10/11 x64
- PowerShell 5.1+
- PowerShell Remoting (WinRM) habilitado en equipos remotos
- Credenciales guardadas en `core0-cred.xml` para acceso a CORE0
