@echo off
cd /d "%~dp0"
start /B powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "%~dp0LocalNetworkAgent-GUI.ps1"
