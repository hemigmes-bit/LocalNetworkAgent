<# 
.SYNOPSIS
    Instalador de Emma Bilingüe - Voice Loop
.DESCRIPTION
    Instala dependencias Python, descarga modelos Kokoro, configura entorno
.NOTES
    Ejecutar como Administrador para instalar Python packages globalmente
#>

param(
    [switch]$GlobalInstall,
    [switch]$SkipModels,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Emma Bilingüe - Instalador" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
try {
    $pythonVersion = & $PythonPath --version 2>&1
    Write-Host "✓ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python no encontrado. Instala Python 3.12+ desde python.org" -ForegroundColor Red
    exit 1
}

# Verificar pip
try {
    & $PythonPath -m pip --version 2>&1 | Out-Null
    Write-Host "✓ pip disponible" -ForegroundColor Green
} catch {
    Write-Host "✗ pip no disponible" -ForegroundColor Red
    exit 1
}

# Instalar dependencias Python
Write-Host "`n[1/4] Instalando dependencias Python..." -ForegroundColor Yellow
$requirements = Join-Path $ProjectRoot "requirements.txt"
if (Test-Path $requirements) {
    $pipArgs = @("install", "-r", $requirements)
    if ($GlobalInstall) { $pipArgs += "--global" }
    & $PythonPath -m @pipArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Error instalando dependencias" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Dependencias instaladas" -ForegroundColor Green
} else {
    Write-Host "⚠ requirements.txt no encontrado" -ForegroundColor Yellow
}

# Descargar modelos Kokoro
if (-not $SkipModels) {
    Write-Host "`n[2/4] Descargando modelos Kokoro..." -ForegroundColor Yellow
    $models = @(
        @{Url="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"; Name="kokoro-v1.0.onnx"},
        @{Url="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"; Name="voices-v1.0.bin"}
    )
    
    foreach ($model in $models) {
        $dest = Join-Path $ProjectRoot $model.Name
        if (-not (Test-Path $dest)) {
            Write-Host "  Descargando $($model.Name) ($(( [math]::Round((Invoke-WebRequest -Uri $model.Url -Method Head -UseBasicParsing).Headers['Content-Length'] / 1MB) )) MB)..."
            try {
                Invoke-WebRequest -Uri $model.Url -OutFile $dest -UseBasicParsing
                Write-Host "  ✓ $($model.Name)" -ForegroundColor Green
            } catch {
                Write-Host "  ✗ Error descargando $($model.Name): $_" -ForegroundColor Red
            }
        } else {
            Write-Host "  ✓ $($model.Name) ya existe" -ForegroundColor Gray
        }
    }
}

# Verificar config.yaml
Write-Host "`n[3/4] Verificando configuración..." -ForegroundColor Yellow
$configPath = Join-Path $ProjectRoot "config.yaml"
if (-not (Test-Path $configPath)) {
    Write-Host "⚠ config.yaml no encontrado" -ForegroundColor Yellow
} else {
    Write-Host "✓ config.yaml encontrado" -ForegroundColor Green
}

# Verificar OPENROUTER_API_KEY
Write-Host "`n[4/4] Verificando API Key..." -ForegroundColor Yellow
$envKey = $env:OPENROUTER_API_KEY
if ([string]::IsNullOrEmpty($envKey)) {
    Write-Host "⚠ OPENROUTER_API_KEY no configurada en variables de entorno" -ForegroundColor Yellow
    Write-Host "  Configúrala con: `n  `$env:OPENROUTER_API_KEY = 'tu-clave-aqui'`n  O añádela a tu perfil de PowerShell/CMD" -ForegroundColor Yellow
} else {
    Write-Host "✓ OPENROUTER_API_KEY configurada" -ForegroundColor Green
}

# Crear acceso directo en Escritorio (opcional)
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Emma Bilingüe.lnk"
if (-not (Test-Path $shortcutPath)) {
    Write-Host "`n¿Crear acceso directo en Escritorio? (s/n): " -NoNewline
    $answer = Read-Host
    if ($answer -eq 's') {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = "powershell.exe"
        $shortcut.Arguments = "-NoExit -Command `\"cd '$ProjectRoot'; python python\src\main\python\voice_loop.py`\""
        $shortcut.WorkingDirectory = $ProjectRoot
        $shortcut.IconLocation = Join-Path $ProjectRoot "assets\emma.ico"
        $shortcut.Save()
        Write-Host "✓ Acceso directo creado" -ForegroundColor Green
    }
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   Instalación completada" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ejecutar Emma Bilingüe:" -ForegroundColor Cyan
Write-Host "  cd $ProjectRoot" -ForegroundColor White
Write-Host "  python python\src\main\python\voice_loop.py" -ForegroundColor White
Write-Host ""
Write-Host "Con auriculares conectados y OPENROUTER_API_KEY configurada." -ForegroundColor Yellow
Write-Host ""
Read-Host "Presiona Enter para salir"