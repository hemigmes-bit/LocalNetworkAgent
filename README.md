# Local Network Agent

Agente PowerShell para controlar tu red local de ordenadores Windows.

## Características

- **Monitorización**: Escanea la red y muestra equipos activos con IP, hostname y MAC
- **Control Remoto**:
  - Wake-on-LAN para encender equipos
  - Apagar y reiniciar remotamente
  - Sesión remota interactiva
- **Ejecución de Comandos**:
  - Ejecutar comandos en un equipo o en múltiples (paralelo)
  - Ejecutar scripts PowerShell en varios equipos a la vez
- **Gestión de Archivos**:
  - Copiar archivos a/desde equipos remotos
  - Listar directorios remotos
- **Inventario**:
  - Hardware (CPU, RAM, discos, GPU, red)
  - Software instalado

## Requisitos

1. **PowerShell Remoting** habilitado en todos los equipos (se configura automáticamente al ejecutar)
2. **Permisos de Administrador** para funcionalidad completa
3. Los equipos deben estar en la misma red local

## Instalación

### 1. Habilitar PowerShell Remoting (en todos los equipos)

Ejecuta en cada equipo de la red (como Administrador):

```powershell
Enable-PSRemoting -Force
```

### 2. Configurar firewall (si es necesario)

```powershell
New-NetFirewallRule -Name "Allow WinRM" -DisplayName "Windows Remote Management" -Enabled True -Profile Domain,Private -Protocol TCP -LocalPort 5985
```

## Uso

### Ejecutar el agente

```powershell
# Desde PowerShell (como Administrador recomendado)
cd C:\Users\Usuario\LocalNetworkAgent
.\LocalNetworkAgent.ps1
```

### Ejecución con perfil de ejecución desbloqueado

```powershell
powershell -ExecutionPolicy Bypass -File .\LocalNetworkAgent.ps1
```

## Configuración

El archivo `network-config.json` almacena:
- Subred a escanear (por defecto: 192.168.1)
- Lista de equipos guardados
- Puerto WinRM (por defecto: 5985)

## Comandos Rápidos (sin menú)

```powershell
# Escanear red
Get-NetworkComputers -SubnetPrefix "192.168.1"

# Enviar Wake-on-LAN
Send-WakeOnLan -MACAddress "00:11:22:33:44:55"

# Ejecutar comando remoto
Invoke-RemoteCommand -ComputerName "192.168.1.100" -Command "Get-Process"

# Copiar archivo a equipo remoto
Copy-ToRemoteComputer -ComputerName "192.168.1.100" -SourcePath "C:\archivo.txt" -DestPath "C:\temp\"

# Ver uso de recursos
Get-RemoteResourceUsage -ComputerName "192.168.1.100"
```

## Solución de Problemas

### Error "WinRM cannot process the request"
- Verifica que PowerShell Remoting esté habilitado en el equipo remoto
- Ejecuta: `Test-WSMan -ComputerName <IP>` para verificar conectividad

### Error de acceso denegado
- Ejecuta como Administrador
- Verifica que las credenciales tengan permisos en el equipo remoto

### Wake-on-LAN no funciona
- La tarjeta de red debe soportar WoL y estar habilitada en BIOS/UEFI
- El equipo debe estar conectado por cable (generalmente)

## API REST + WebSocket + MCP

El agente incluye un servidor API para controlar la red desde cualquier dispositivo (móvil, tablet, otro PC) con integración MCP.

### Endpoints MCP

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/mcp` | Lista de MCP servers instalados |
| `GET` | `/api/mcp/{server}/status` | Estado de un MCP server específico |
| `POST` | `/api/mcp/network-tools/scan` | Escanear red con herramientas MCP |
| `POST` | `/api/mcp/wol-server/wake` | Enviar Wake-on-LAN via MCP |
| `GET` | `/api/mcp/file-system/list` | Listar archivos via MCP |
| `POST` | `/api/mcp/vscode-server/open` | Abrir VS Code via MCP |
| `POST` | `/api/mcp/git-server/commit` | Hacer commit via MCP |
| `POST` | `/api/mcp/terminal-server/execute` | Ejecutar comando via MCP |

### Iniciar MCP Servers

```powershell
# Iniciar todos los MCP servers
.\Start-MCP-Servers.ps1

# Iniciar con configuración personalizada
.\Start-MCP-Servers.ps1 -Config "mcp-config.json"
```

### MCP Servers Instalados

- **network-tools**: Herramientas de escaneo y gestión de red
- **wol-server**: Wake-on-LAN para encendido remoto
- **ping-server**: Monitoreo de conectividad
- **file-system**: Acceso a archivos locales y remotos
- **smb-server**: Integración con recursos compartidos Windows
- **ftp-server**: Gestión de archivos vía FTP
- **vscode-server**: Integración con VS Code
- **git-server**: Control de versiones
- **terminal-server**: Acceso a terminal remoto

### Iniciar el servidor API

```powershell
# Inicio básico (puerto 8080)
.\API-Server.ps1

# Con configuración personalizada
.\API-Server.ps1 -Port 8080 -WebSocketPort 8081 -EnableWebSocket:$true
```

### Interfaz Web PWA

El servidor incluye una interfaz web móvil (PWA) accesible desde cualquier navegador:

1. Inicia el servidor API
2. Abre desde tu móvil: `http://<IP-del-servidor>:8080`
3. Introduce tu token de API (se guarda automáticamente)
4. **Instalar como app**: En Chrome/Android, usa "Añadir a pantalla de inicio"

**Características de la PWA:**
- Escaneo de red con un botón
- Control de equipos (encender, apagar, reiniciar)
- Ejecución de comandos remotos
- Upload de archivos
- Funciona offline (cache de assets)
- Diseño responsive para móvil

### Endpoints disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/status` | Estado del servidor |
| `GET` | `/api/computers` | Lista de equipos escaneados |
| `POST` | `/api/scan` | Escanear red |
| `GET` | `/api/computer/:ip/info` | Información de un equipo |
| `GET` | `/api/computer/:ip/resources` | Uso de recursos en tiempo real |
| `POST` | `/api/wol` | Enviar Wake-on-LAN |
| `POST` | `/api/computer/:ip/power-on` | **Encender + confirmar** (WoL + verificar) |
| `POST` | `/api/computer/:ip/shutdown` | Apagar equipo remoto |
| `POST` | `/api/computer/:ip/restart` | Reiniciar equipo remoto |
| `POST` | `/api/computer/:ip/command` | Ejecutar comando |
| `GET` | `/api/computer/:ip/hardware` | Inventario de hardware |
| `GET` | `/api/computer/:ip/software` | Software instalado |
| `GET` | `/api/computer/:ip/files` | Listar archivos remotos |
| `POST` | `/api/upload` | **Subir archivo** al servidor local |
| `POST` | `/api/computer/:ip/upload` | **Subir archivo** a equipo remoto |
| `GET` | `/api/logs` | Ver logs recientes |

### Autenticación

La API requiere autenticación por token para todos los endpoints excepto `/api/status`.

**Obtener tu token:**
- Al iniciar el servidor API por primera vez, se genera automáticamente un token
- El token se guarda en `api-token.json` en el mismo directorio
- El token se muestra en la consola al iniciar el servidor

**Usar el token en las peticiones:**
```bash
curl -H "Authorization: Bearer TU_TOKEN" http://192.168.1.100:8080/api/computers
```

### Ejemplos desde Android (curl/HTTP)

```bash
# Ver estado del servidor (público, sin autenticación)
curl http://192.168.1.100:8080/api/status

# Escanear red (requiere autenticación)
curl -X POST http://192.168.1.100:8080/api/scan \
  -H "Authorization: Bearer TU_TOKEN"

# Encender equipo con confirmación (espera hasta 120s)
curl -X POST http://192.168.1.100:8080/api/computer/192.168.1.50/power-on \
  -H "Authorization: Bearer TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"MACAddress":"00:11:22:33:44:55","timeout":120,"checkInterval":10}'

# Apagar equipo
curl -X POST http://192.168.1.100:8080/api/computer/192.168.1.50/shutdown \
  -H "Authorization: Bearer TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force":false}'

# Ejecutar comando
curl -X POST http://192.168.1.100:8080/api/computer/192.168.1.50/command \
  -H "Authorization: Bearer TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"Get-Process"}'

# Ver recursos en tiempo real
curl -H "Authorization: Bearer TU_TOKEN" \
  http://192.168.1.100:8080/api/computer/192.168.1.50/resources

# Subir archivo al servidor local
curl -X POST http://192.168.1.100:8080/api/upload \
  -H "Authorization: Bearer TU_TOKEN" \
  -F "file=@/ruta/a/archivo.pdf" \
  -F "path=/archivos"

# Subir archivo a equipo remoto
curl -X POST http://192.168.1.100:8080/api/computer/192.168.1.50/upload \
  -H "Authorization: Bearer TU_TOKEN" \
  -F "file=@/ruta/a/archivo.pdf" \
  -F "path=C:\temp"
```

### WebSocket

Conéctate a `ws://192.168.1.100:8081/` para recibir notificaciones en tiempo real.

```javascript
// Ejemplo desde app Android (JavaScript/WebSocket)
const ws = new WebSocket('ws://192.168.1.100:8081/');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};

// Enviar comando
ws.send(JSON.stringify({ action: 'scan' }));
```

## Estructura de Archivos

```
LocalNetworkAgent/
├── LocalNetworkAgent.ps1    # Script principal (menú interactivo)
├── API-Server.ps1           # Servidor REST + WebSocket + PWA
├── VoiceControl.ps1         # Control por voz (Windows Speech)
├── network-config.json      # Configuración (se crea al ejecutar)
├── api-token.json           # Token de autenticación (se crea al iniciar)
├── network-agent.log        # Logs de ejecución
├── public/                  # Archivos de la PWA
│   ├── index.html           # Interfaz web móvil
│   ├── manifest.json        # Manifiesto PWA
│   └── sw.js                # Service Worker
├── mcp-servers/            # MCP Servers instalados
│   ├── network-tools/      # Herramientas de red
│   ├── wol-server/         # Wake-on-LAN
│   ├── ping-server/        # Monitoreo de conectividad
│   ├── file-system/        # Gestión de archivos
│   ├── smb-server/         # Recursos compartidos Windows
│   ├── ftp-server/         # Gestión FTP
│   ├── vscode-server/      # Integración VS Code
│   ├── git-server/         # Control de versiones
│   └── terminal-server/    # Terminal remoto
├── mcp-config.json         # Configuración MCP
├── Start-MCP-Servers.ps1   # Inicializador MCP
├── TODO.md                 # Tareas pendientes y completadas
└── README.md              # Este archivo
```

## Seguridad

- Las credenciales se manejan de forma segura con PSCredential
- Los logs no almacenan información sensible
- Se recomienda usar HTTPS (puerto 5986) en entornos productivos

## Control por Voz (Windows Speech Recognition)

El agente incluye control por voz usando el reconocimiento de voz de Windows.

### Requisitos

- Windows Speech Recognition instalado (incluido en Windows 10/11)
- Micrófono configurado y funcionando
- API Server ejecutándose (`API-Server.ps1`)

### Iniciar Control por Voz

```powershell
# Desde PowerShell (como Administrador recomendado)
.\VoiceControl.ps1

# Con API en otro puerto
.\VoiceControl.ps1 -ApiBaseUrl "http://localhost:8080"
```

### Comandos de Voz Disponibles

| Categoría | Comandos | Descripción |
|-----------|----------|-------------|
| **Escaneo** | "Escanear red", "Buscar equipos" | Escanea la red en busca de equipos |
| **Estado** | "Estado del servidor", "Estado" | Ver estado del API Server |
| **Energía** | "Apagar equipo [IP]" | Apagar equipo remoto |
| | "Reiniciar equipo [IP]" | Reiniciar equipo remoto |
| | "Encender equipo [IP]" | Wake-on-LAN + verificar |
| **Información** | "Lista de equipos" | Mostrar todos los equipos |
| | "Información de [IP]" | Info detallada del equipo |
| | "Recursos de [IP]" | CPU/RAM en tiempo real |
| | "Hardware de [IP]" | Inventario de hardware |
| **Utilidades** | "Logs recientes" | Ver últimos logs |
| | "Cuantos equipos" | Contar equipos activos |
| **Ayuda** | "Ayuda", "Que puedo decir" | Mostrar ayuda de comandos |

### Ejemplos de Uso

```
Tú: "Escanear red"
Voice: "Escaneando la red en busca de equipos"
[espera...]
Voice: "Escaneo completado. Se encontraron 5 equipos en la red."

Tú: "Información de 192.168.1.50"
Voice: "Obteniendo información de 192.168.1.50"
[Muestra en pantalla: Hostname, SO, CPU, RAM]
Voice: "DESKTOP-PC. Sistema operativo Windows 11 Pro. 16 gigabytes de RAM"

Tú: "Encender equipo 192.168.1.100"
Voice: "Encendiendo equipo 192.168.1.100"
[envía WoL y verifica]
Voice: "Equipo 192.168.1.100 encendido y verificado"
```

### Solución de Problemas

**"No se pudo iniciar el reconocimiento de voz"**
- Verifica que Windows Speech Recognition esté instalado
- Abre Configuración > Hora e idioma > Voz y asegura que el reconocimiento esté activado

**"Comando no reconocido"**
- Habla claramente y cerca del micrófono
- Usa los comandos exactos de la tabla arriba
- Di "Ayuda" para recordar los comandos disponibles
