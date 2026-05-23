# LocalNetworkAgent
## Ejecutar
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1"
```
O hacer doble clic en `Iniciar.bat`
## Proyecto
- **GUI**: `LocalNetworkAgent-GUI.ps1`
- **Entry point**: `Iniciar.bat` → llama a `LocalNetworkAgent-GUI.ps1`
- **Explorador**: `Explorer_Agent.ps1`
- **Módulos**: `NetworkUtilsPublic.psm1`
- **Config**: `network-config.json`
- **C#**: `LocalNetworkAgent/`
- **Scripts**: `*.ps1`
## Estado
Última reparación: 02/05/2026 - GUI funcionando
# OpenCode Agent Instructions
## REGLA SUPREMA — NUNCA pedir al usuario lo que puedo hacer yo
- Cerrar procesos → `taskkill /F /IM powershell.exe`
- Lanzar GUI → `Start-Process powershell.exe -File ...`
- Probar scripts → ejecutarlos yo mismo
- Modificar código → editarlo yo mismo
- **Si el usuario pregunta "¿por qué me pides esto?" → he fallado**
## Regla principal
- **TOMAR ACCIÓN DIRECTA — NUNCA pedir al usuario tareas que puedo ejecutar yo**: 
  - Cerrar procesos: `taskkill /F /IM powershell.exe`, `Stop-Process`
  - Lanzar scripts: `Start-Process powershell.exe -File ...`
  - Modificar archivos: `Edit`, `Write`
  - Ejecutar comandos: `bash`
  - HACERLO SIN PREGUNTAR ni pedir permiso
- **CERRAR PROCESOS PROBLEMÁTICOS**: Si hay procesos que bloquean la ejecución (PowerShell, wscript, etc.), cerrarlos ANTES de iniciar nuevos — NUNCA pedir al usuario que lo haga.
- **VERIFICAR ANTES DE LANZAR**: Comprobar procesos activos antes de lanzar GUI u otros scripts — NUNCA pedir al usuario que lo haga.
## REGLA CRÍTICA: Imágenes del usuario
- **SIEMPRE usar `clipboard-vision_analyze_clipboard`** cuando el usuario envíe una imagen, screenshot o diga "mira esto"
- **NUNCA responder "no puedo ver imágenes"** — usar la herramienta del portapapeles primero
- Herramientas disponibles:
  - `clipboard_vision_analyze_clipboard` — análisis general de imagen
  - `clipboard_vision_diagnose_error_from_clipboard` — diagnosticar errores
  - `clipboard_vision_extract_text_from_clipboard` — extraer texto (OCR)
  - `clipboard_vision_code_from_clipboard` — extraer código
  - `clipboard_vision_describe_ui_from_clipboard` — describir interfaz
- Si la imagen viene como archivo, usar las versiones con `_path`: `_analyze_image`, `_extract_text`, etc.
## Archivos protegidos (NUNCA borrar)
- `LocalNetworkAgent-GUI.ps1` — GUI principal
- `Iniciar.bat` — Entry point, referencia a la GUI
- `Iniciar.vbs` — Alternativa silent launch
- `Explorer_Agent.ps1` — Navegador de archivos remoto
- `NetworkUtilsPublic.psm1` — Módulo de utilidades de red
- `network-config.json` — Configuración de dispositivos y red
- `core0-cred.xml` — Credenciales remotas (SECRETO, no commit)
- `victorymar-cred.xml` — Credenciales (SECRETO, no commit)
- `api-token.json` — Token API (SECRETO, no commit)
- `AGENTS.md` — Este archivo de instrucciones
## REGLA CRÍTICA: Antes de borrar cualquier archivo
1. **Verificar referencias cruzadas**: Si borro X.ps1, buscar quién lo llama (`Select-String "X.ps1" *.*`)
2. **NUNCA borrar `Iniciar.bat`**, `LocalNetworkAgent-GUI.ps1`, `network-config.json`, `*.xml`
3. **Si `Iniciar.bat` referencia un archivo, ese archivo es ESENCIAL**
4. **Archivos con espacios en el nombre**: marcarlos como corruptos pero verificar antes de borrar que no sean el único entry point
## REGLA: Verificar IPs reales antes de asumir
1. **NUNCA confiar ciegamente en `network-config.json`**: las IPs pueden haber cambiado (DHCP)
2. **Al diagnosticar "mismos archivos en todos los dispositivos"**: verificar que cada IP apunte a un hostname DIFERENTE
3. **Comando rápido**: `Invoke-Command -Session (New-PSSession IP) { hostname }` revela la máquina real
4. **Si dos IPs devuelven el mismo hostname**: la config está MAL, actualizarla con los valores reales
## Protocolo pre-diagnóstico OBLIGATORIO
Antes de tocar cualquier código cuando el usuario reporta un fallo, ejecutar SIEMPRE:
1. `Test-Connection -ComputerName <cada IP de la config> -Count 1 -Quiet`
2. `Invoke-Command -ComputerName <IP> { hostname }` (con y sin credenciales)
3. Comparar hostnames obtenidos con los nombres en `network-config.json`
4. Si hay discrepancias → actualizar `network-config.json` ANTES de modificar código
## Errores comunes a evitar
1. **NO pedir** al usuario que cierre procesos - hacerlo yo mismo con `Stop-Process -Id X -Force`
2. **Usar espacios en blanco** en rutas causa errores de sintaxis - usar rutas sin espacios o con comillas
3. **NO verificar** procesos activos antes de lanzar - siempre verificar primero
4. **NO mostrar** output truncado al usuario - resumir resultados
5. **NO borrar archivos sin verificar referencias** — usar `Select-String` para buscar dependencias
6. **NO romper el entry point** — `Iniciar.bat` debe apuntar al archivo correcto
7. **NO decir "no puedo ver imágenes"** — usar `clipboard-vision_analyze_clipboard` primero
8. **NO confiar en `network-config.json`** sin verificar IPs reales con `Invoke-Command { hostname }`
## Entorno de desarrollo
- OS: Windows 11 x64
- Shell: PowerShell 7.4+
- Package manager: NuGet / npm / Chocolatey
## Reglas generales
- Usar siempre rutas Windows con backslash o `Path.Combine()`
- En PowerShell, variables de entorno con `$env:NOMBRE`
- Line endings CRLF en scripts `.ps1`
- Nunca usar comandos Unix (`ls`, `grep`, `cat`) — usar equivalentes PowerShell
## Comandos de shell
- Para listar archivos: `Get-ChildItem` o `dir`
- Para buscar texto: `Select-String` en lugar de `grep`
- **PARA MATAR PROCESOS**: `taskkill /F /PID X` o `Stop-Process -Id X -Force`
## Stack específico
- Framework: WinForms (PowerShell GUI)
## Verificación post-cambio
- Después de modificar/cambiar archivos, ejecutar `Iniciar.bat` para verificar que la GUI arranca
- Si `Iniciar.bat` falla, reparar INMEDIATAMENTE
## LECCIONES APRENDIDAS — NO VOLVER A COMETER
### Detección de dispositivos (ERRROR recurrente: CORE0 offline)
1. **NUNCA saltarse el ping sweep**: antes de leer la tabla ARP, hacer ping a TODAS las IPs de la subred (1-30, timeout 80ms). Sin esto la ARP está desactualizada y las MACs no se resuelven.
2. **Siempre verificar IPs reales**: no confiar en `network-config.json`. Al arrancar el scan, leer ARP → buscar MACs conocidas → actualizar config automáticamente.
3. **Cadena de fallback completa**: MAC en ARP → IP configurada → ping → TCP 5985/5555. NUNCA saltarse un paso.
4. **No usar runspace/async para el scan**: usar código síncrono con `[Application]::DoEvents()`. El runspace pierde scope de variables y es imposible de depurar.
5. **No usar `Test-Connection`**: usar `[System.Net.NetworkInformation.Ping]::new().Send(ip, timeout_ms)` con timeout explícito.
6. **DoEvents entre cada operación**: mantener la UI responsiva insertando `[System.Windows.Forms.Application]::DoEvents()` después de cada ping y cada TCP check.
7. **Auto-update del config**: si un dispositivo aparece en IP distinta a la configurada, actualizar `network-config.json` automáticamente Y recargar la config global.

### Lanzamiento de procesos
- **GUI siempre con `-WindowStyle Hidden`** para no mostrar consola
- SHELL es la única excepción (debe mostrar ventana interactiva)
- API, WOL, VOICE, CHAT, MONITOR siempre con `-WindowStyle Hidden`

### Livebox / Router
- Livebox 6 solo usa SMBv1 (deshabilitado en Windows por seguridad)
- Orange desactivó el USB sharing server-side
- Puerto 445 (SMB) cerrado, solo 443 (HTTPS) abierto
- Para ARCHIVOS en livebox: abrir `https://192.168.1.1` en el navegador
- NO intentar SMB, FTP o WebDAV — no funcionan en Livebox 6

## Proceso de razonamiento
- Piensa paso a paso antes de responder
- Si la tarea es compleja, divídela en subtareas
- Confirma cada subtarea completada antes de pasar a la siguiente

## Verificación
- Después de cada cambio importante, verifica que el código compila
- Si modificas un archivo existente, lee el archivo completo primero
- No hagas suposiciones sobre el contenido de archivos que no has leído
## Herramientas web
- Cuando necesites documentación de APIs, SDKs o librerías, usa siempre `exa` antes de responder
- Usa `context7` para documentación de .NET, WinForms, PowerShell y NuGet
- No respondas sobre APIs basándote solo en conocimiento interno si puede estar desactualizado

## Modo de trabajo con DeepSeek V4 Pro
- Para tareas que tocan más de 2 archivos, usa modo Plan primero
- Usa etiquetas <think> para razonamiento explícito en tareas complejas
- Una tarea a la vez — completa y verifica antes de pasar a la siguiente

## Seguridad
- NUNCA incluir en commits: `core0-cred.xml`, `victorymar-cred.xml`, `api-token.json`
- NUNCA mostrar contenido de archivos `*-cred.xml` o `api-token.json` en el chat
- Verificar siempre que `.gitignore` cubre los archivos secretos antes de cualquier commit