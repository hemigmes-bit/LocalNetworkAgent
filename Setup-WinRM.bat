@echo off
echo Iniciando WinRM en este equipo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%CWD%\Enable-WinRM.ps1' -Verb RunAs -Wait"
echo WinRM configurado
pause