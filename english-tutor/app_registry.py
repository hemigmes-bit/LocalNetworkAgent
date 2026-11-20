"""app_registry.py - Resolucion de apps instaladas en VICTORYMAR.
Patron tomado de Greninja/JarvisAi/VARNA: en lugar de aliases fijos,
escanea el sistema real: Start Menu, registro App Paths, UWP apps,
y rutas comunes. Con score de uso para apps frecuentes.
"""
import os
import json
import subprocess
import winreg
from datetime import datetime

REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_registry.json")
USAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_usage.json")

COMMON_PATHS = {
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    "vscode": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")],
    "notepad": [r"C:\Windows\System32\notepad.exe"],
    "calc": [r"C:\Windows\System32\calc.exe"],
    "paint": [r"C:\Windows\System32\mspaint.exe"],
    "terminal": [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe")],
    "explorer": [r"C:\Windows\explorer.exe"],
}


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def scan_start_menu():
    """Escanea accesos directos del Start Menu."""
    apps = {}
    bases = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    import ctypes.wintypes
    import struct

    for base in bases:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(".lnk"):
                    continue
                full = os.path.join(root, fn)
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    sc = shell.CreateShortCut(full)
                    target = sc.Targetpath
                except Exception:
                    try:
                        target = _resolve_lnk_manual(full)
                    except Exception:
                        continue
                if target and os.path.exists(target) and target.lower().endswith((".exe", ".bat", ".cmd")):
                    name = fn[:-4].lower()
                    apps[name] = target
    return apps


def _resolve_lnk_manual(path):
    """Resuelve .lnk sin pywin32 (via PowerShell)."""
    try:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + path.replace("'", "''") + "');"
              "$s.TargetPath")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=10)
        t = (out.stdout or "").strip()
        return t if t else None
    except Exception:
        return None


def scan_uwp():
    """Lista apps UWP via PowerShell Get-StartApps."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        apps = {}
        for item in data:
            nm = (item.get("Name") or "").lower()
            aid = item.get("AppID") or ""
            if nm and aid:
                apps[nm] = aid
        return apps
    except Exception:
        return {}


def scan_app_paths():
    """Escanea App Paths del registro."""
    apps = {}
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            k = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
            for i in range(winreg.QueryInfoKey(k)[0]):
                ename = winreg.EnumKey(k, i)
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + ename) as ek:
                        path, _ = winreg.QueryValueEx(ek, "")
                    if os.path.exists(path):
                        apps[ename.lower()] = path
                except OSError:
                    continue
        except OSError:
            continue
    return apps


def build_registry(force=False):
    """Construye el registro completo de apps instaladas."""
    if os.path.exists(REGISTRY_FILE) and not force:
        age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(REGISTRY_FILE))).days
        if age < 7:
            return _load_json(REGISTRY_FILE, {})

    apps = {}
    for name, paths in COMMON_PATHS.items():
        for p in paths:
            if os.path.exists(p):
                apps[name] = p
                break
    apps.update(scan_start_menu())
    apps.update(scan_app_paths())
    uwp = scan_uwp()
    for k, v in uwp.items():
        apps[k] = v
    apps.update(_load_json(REGISTRY_FILE, {}))
    _save_json(REGISTRY_FILE, apps)
    return apps


def fuzzy_resolve(query, apps=None, strict=True):
    """Resuelve una app por nombre. strict=True: solo coincidencias fuertes
    (exacta, prefijo o subconjunto de palabras) para evitar falsos positivos."""
    if apps is None:
        apps = build_registry()
    q = query.strip().lower().rstrip(".exe")
    if not q:
        return None, apps
    # Exacto
    if q in apps:
        return apps[q], apps
    if q + ".exe" in apps:
        return apps[q + ".exe"], apps
    # Prefijo (estricto) o contiene (permisivo)
    for name, path in apps.items():
        base = name.replace(".exe", "").replace(".lnk", "")
        if base == q:
            return path, apps
        if strict:
            if base.startswith(q) or q.startswith(base):
                return path, apps
        else:
            if q in base or base in q:
                return path, apps
    # Palabras
    qwords = set(q.split())
    for name, path in apps.items():
        base = name.replace(".exe", "").replace(".lnk", "")
        words = set(base.replace("-", " ").replace("_", " ").split())
        if qwords and qwords.issubset(words):
            return path, apps
    return None, apps


def record_usage(app_name):
    """Incrementa el score de uso de una app."""
    data = _load_json(USAGE_FILE, {})
    key = app_name.strip().lower()
    data[key] = data.get(key, 0) + 1
    _save_json(USAGE_FILE, data)


def get_frequent(n=10):
    """Apps mas usadas."""
    data = _load_json(USAGE_FILE, {})
    return sorted(data.items(), key=lambda x: -x[1])[:n]


def list_apps(query=""):
    """Lista apps registradas (filtro opcional)."""
    apps = build_registry()
    if query:
        q = query.lower()
        return {k: v for k, v in apps.items() if q in k}
    return apps


if __name__ == "__main__":
    print("Escaneando apps instaladas en VICTORYMAR...")
    apps = build_registry(force=True)
    print(f"Total: {len(apps)} apps")
    for k in sorted(apps)[:40]:
        print(f"  {k} -> {apps[k]}")
