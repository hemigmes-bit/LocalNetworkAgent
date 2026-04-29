# LocalNetworkAgent

## Ejecutar

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1"
```

O hacer doble clic en `Iniciar.bat`

## Proyecto

- **GUI**: `LocalNetworkAgent-GUI.ps1`
- **C#**: `LocalNetworkAgent/`
- **Scripts**: `*.ps1`

## Estado

Última reparación: 24/04/2026 - GUI funcionando

# OpenCode Agent Instructions

## Entorno de desarrollo
- OS: Windows 11 x64
- Shell: PowerShell 7.4+
- Compilador: MSVC 2022 (o el que uses)
- Package manager: NuGet / npm / Chocolatey

## Reglas generales
- Usar siempre rutas Windows con backslash o `Path.Combine()`
- En PowerShell, variables de entorno con `$env:NOMBRE`
- Line endings CRLF en scripts `.ps1`
- Preferir `winget` o `choco` para instalar herramientas del sistema
- Nunca usar comandos Unix (`ls`, `grep`, `cat`) — usar equivalentes PowerShell

## Convenciones de código
- C#: seguir convenciones de Microsoft (.NET naming guidelines)
- Usar `async/await` siempre que la API lo soporte
- XML doc comments en métodos públicos (`/// <summary>`)

## Comandos de shell
- Para listar archivos: `Get-ChildItem` o `dir`
- Para buscar texto: `Select-String` en lugar de `grep`
- Para variables: `$env:PATH` en lugar de `$PATH`
- Para ejecutar como admin: indicarlo explícitamente en el prompt

## Stack específico (edita esto)
- Framework: .NET 9 / WinUI 3  (o WPF, WinForms, etc.)
- Base de datos: SQL Server / SQLite
- Testing: xUnit / MSTest

## Herramientas web
- Cuando necesites información actualizada, documentación de APIs, o ejemplos recientes, usa siempre `exa` para buscar en la web antes de responder.
- Usa `exa` para buscar documentación de Microsoft Learn, NuGet packages, WinUI 3, .NET, y cualquier SDK de Windows.
- Usa `exa` para verificar versiones actuales de paquetes y librerías antes de recomendarlas.
- No respondas sobre APIs o SDKs basándote solo en tu conocimiento interno si hay riesgo de que esté desactualizado.
