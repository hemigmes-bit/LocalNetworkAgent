# LocalNetworkAgent
## Ejecutar
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.PS1"
```
O hacer doble clic en `Iniciar.bat`
## Proyecto
- **GUI**: `LocalNetworkAgent-GUI.PS1`
- **C#**: `LocalNetworkAgent/`
- **Scripts**: `*.ps1`
## Estado
Última reparación: 24/04/2026 - GUI funcionando
# OpenCode Agent Instructions
## Regla principal
- **TOMAR ACCIÓN DIRECTA**: No pedir al usuario que haga tareas que puedo hacer yo mismo. Ejecutar sin preguntar para operaciones de sistema, lanzamiento de procesos, y modificaciones de archivos.
- **CERRAR PROCESOS PROBLEMÁTICOS**: Si hay procesos que bloquean la ejecución (PowerShell, wscript, etc.), cerrarlos ANTES de iniciar nuevos.
- **VERIFICAR ANTES DE LANZAR**: Comprobar procesos activos antes de lanzar GUI u otros scripts.
## Errores comunes a evitar
1. **NO pedir** al usuario que cierre procesos - hacerlo yo mismo con `Stop-Process -Id X -Force`
2. **Usar espacios en blanco** en rutas causa errores de sintaxis - usar rutas sin espacios o con comillas
3. **NO verificar** procesos activos antes de lanzar - siempre verificar primero
4. **NO mostrar** output truncado al usuario - resumir resultados
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