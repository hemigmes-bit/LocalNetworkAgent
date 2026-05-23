@echo off
title OpenCode Mobile Server
echo Iniciando OpenCode Mobile Server...
echo URL: http://192.168.1.17:4097
echo Usuario: opencode
echo Password: opencode2026
echo.
set OPENCODE_SERVER_USERNAME=opencode
set OPENCODE_SERVER_PASSWORD=opencode2026
npx -y opencode-ai serve --hostname 0.0.0.0 --port 4097
pause