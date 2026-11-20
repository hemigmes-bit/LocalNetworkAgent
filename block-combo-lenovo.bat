@echo off
set "YTRANGES=64.233.160.0/19 66.102.0.0/20 66.249.64.0/19 72.14.192.0/18 74.125.0.0/16 172.217.0.0/16 172.253.0.0/16 209.85.128.0/17 216.58.192.0/19 216.239.32.0/19"
set "RBRANGES=128.116.0.0/17 103.140.28.0/23 141.193.3.0/24 204.9.184.0/24 205.201.62.0/24 204.13.168.0/21 209.206.40.0/21 23.173.192.0/24 64.125.149.0/24 208.185.116.0/25 208.185.166.232/29 208.185.166.240/29 208.185.173.0/24 216.200.230.0/24 107.180.192.0/19"

echo Bloqueando YouTube...
for %%R in (%YTRANGES%) do (
    netsh advfirewall firewall add rule name="Block-YouTube-%%R" dir=out action=block remoteip=%%R protocol=TCP description="Block YouTube"
)

echo Bloqueando Roblox...
for %%R in (%RBRANGES%) do (
    netsh advfirewall firewall add rule name="Block-Roblox-%%R" dir=out action=block remoteip=%%R protocol=TCP description="Block Roblox"
)

echo.
echo Proceso finalizado. Verifica reglas con: netsh advfirewall firewall show rule name=all
pause