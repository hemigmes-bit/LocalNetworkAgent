Set WshShell = CreateObject("WScript.Shell")
Dim exePath
exePath = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
WshShell.Run exePath & " -WindowStyle Hidden -ExecutionPolicy Bypass -NoExit -File ""C:\Users\Usuario\LocalNetworkAgent\LocalNetworkAgent-GUI.ps1""", 0, False