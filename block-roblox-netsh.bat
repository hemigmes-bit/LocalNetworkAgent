@echo off
netsh advfirewall firewall add rule name="Block-Roblox-128-116-0-0-17" dir=out action=block remoteip=128.116.0.0/17 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-103-140-28-0-23" dir=out action=block remoteip=103.140.28.0/23 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-141-193-3-0-24" dir=out action=block remoteip=141.193.3.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-204-9-184-0-24" dir=out action=block remoteip=204.9.184.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-205-201-62-0-24" dir=out action=block remoteip=205.201.62.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-204-13-168-0-21" dir=out action=block remoteip=204.13.168.0/21 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-209-206-40-0-21" dir=out action=block remoteip=209.206.40.0/21 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-23-173-192-0-24" dir=out action=block remoteip=23.173.192.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-64-125-149-0-24" dir=out action=block remoteip=64.125.149.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-208-185-116-0-25" dir=out action=block remoteip=208.185.116.0/25 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-208-185-166-232-29" dir=out action=block remoteip=208.185.166.232/29 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-208-185-166-240-29" dir=out action=block remoteip=208.185.166.240/29 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-208-185-173-0-24" dir=out action=block remoteip=208.185.173.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-216-200-230-0-24" dir=out action=block remoteip=216.200.230.0/24 protocol=TCP description="Block Roblox traffic"
netsh advfirewall firewall add rule name="Block-Roblox-107-180-192-0-19" dir=out action=block remoteip=107.180.192.0/19 protocol=TCP description="Block Roblox traffic"
echo Done.
pause