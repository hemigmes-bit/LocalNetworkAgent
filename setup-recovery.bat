@echo off
echo === LocalNetworkAgent - Setup Recovery ===
echo.

cd /d "C:\Users\Usuario\LocalNetworkAgent"

echo 1. Adding directory to git safe directories...
git config --global --add safe.directory "C:/Users/Usuario/LocalNetworkAgent" 2>nul

echo 2. Checking git status...
git status

echo.
echo === Setup Complete ===
echo Working directory: C:\Users\Usuario\LocalNetworkAgent
echo.
echo Run 'claude' to start working with Claude Code
