@echo off
chcp 65001 >nul
title Emma Bilingüe - Voice Loop

echo ============================================
echo    Emma Bilingüe - Voice Loop
echo ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.12+ desde python.org
    pause
    exit /b 1
)

REM Verificar config.yaml
if not exist config.yaml (
    echo [ERROR] config.yaml no encontrado
    pause
    exit /b 1
)

REM Verificar OPENROUTER_API_KEY
if "%OPENROUTER_API_KEY%"=="" (
    echo [ADVERTENCIA] OPENROUTER_API_KEY no configurada en variables de entorno
    echo Configurarla con: set OPENROUTER_API_KEY=tu-clave-aqui
    echo.
)

REM Verificar modelos Kokoro
if not exist kokoro-v1.0.onnx (
    echo [ERROR] Modelo kokoro-v1.0.onnx no encontrado
    echo Ejecuta install.ps1 para descargarlo
    pause
    exit /b 1
)

if not exist voices-v1.0.bin (
    echo [ERROR] Modelo voices-v1.0.bin no encontrado
    echo Ejecuta install.ps1 para descargarlo
    pause
    exit /b 1
)

echo [OK] Todo listo. Iniciando Emma Bilingüe...
echo.
echo ============================================
echo    Emma Bilingüe - Voice Loop
echo ============================================
echo Model: google/gemma-4-12b
echo History: 10 turns
echo Half-duplex: ON, Post-TTS delay: 500ms
echo.
echo Speak and the system will transcribe -> LLM -> voice
echo Press Ctrl+C to stop after current turn
echo ============================================
echo.

python python\src\main\python\voice_loop.py

echo.
echo Voice Loop finalizado.
pause