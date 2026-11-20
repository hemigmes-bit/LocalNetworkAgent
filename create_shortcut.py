import os
import winshell
from win32com.client import Dispatch

desktop = winshell.desktop()
path = os.path.join(desktop, 'Emma Bilingue.lnk')
target = r'C:\Users\Usuario\AppData\Local\Programs\Python\Python312\python.exe'
wdir = r'C:\Users\Usuario\LocalNetworkAgent'
args = r'"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python\voice_loop.py"'

shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(path)
shortcut.Targetpath = target
shortcut.Arguments = args
shortcut.WorkingDirectory = wdir
shortcut.Description = 'Emma Bilingue - Voice Loop'
shortcut.save()
print('Shortcut created at:', path)