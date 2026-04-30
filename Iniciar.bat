@echo off
cmd /c start "" /b powershell -WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -File "%~dp0LocalNetworkAgent-GUI.ps1"