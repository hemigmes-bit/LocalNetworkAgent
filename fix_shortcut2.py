import os
import winshell
from win32com.client import Dispatch

desktop = winshell.desktop()
path = os.path.join(os.path.expanduser('~'), 'Desktop', 'Emma.lnk')

shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.Targetpath = r'C:\Program Files\Python312\python.exe'
shortcut.Arguments = r'"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python\voice_loop.py"'
shortcut.WorkingDirectory = r'C:\Users\Usuario\LocalNetworkAgent'
shortcut.Description = 'Emma - Voice Loop'
shortcut.save()
print('Shortcut fixed!')