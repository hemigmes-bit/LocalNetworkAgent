"""Emma Personal Assistant v4.0 - Control TOTAL de VICTORYMAR (maquina local).
Emma puede controlar TODAS las aplicaciones de VICTORYMAR:
- Lanzar cualquier app instalada (resuelta por nombre o ruta)
- Gestionar ventanas (traer al frente, minimizar, maximizar, cerrar)
- Listar procesos y apps en ejecucion
- Control de volumen/sistema (local)
- Confirmaciones para acciones criticas, auditoria completa
- COOPERACION: Emma puede pedir ayuda a opencode via mailbox
"""
import os
import re
import sys
import subprocess
import logging
import shutil
import time
import ctypes
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_registry as appreg
import memory as emma_memory
import network as home_net

AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_audit.log")
logging.basicConfig(filename=AUDIT_LOG, level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_DIRS = [
    PROJECT_DIR,
    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    os.getcwd(),
]

# Apps comunes con rutas conocidas (se resuelven al vuelo)
APP_ALIASES = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "vscode": r"C:\Users\Usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "code": r"C:\Users\Usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\Usuario\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "explorador": r"C:\Windows\explorer.exe",
    "notepad": r"C:\Windows\System32\notepad.exe",
    "bloc de notas": r"C:\Windows\System32\notepad.exe",
    "calc": r"C:\Windows\System32\calc.exe",
    "calculadora": r"C:\Windows\System32\calc.exe",
    "paint": r"C:\Windows\System32\mspaint.exe",
    "configuracion": r"C:\Windows\System32\ms-settings.exe",
    "panel de control": r"C:\Windows\System32\control.exe",
    "terminal": r"C:\Windows\System32\wt.exe",
    "spotify": None,  # se resuelve via App Paths
    "telegram": None,
    "whatsapp": None,
    "vlc": None,
    "word": None,
    "excel": None,
    "powerpoint": None,
}


def audit(action, target, success=True, details=""):
    status = "OK" if success else "FAIL"
    entry = f"{action} | {status} | {target} | {details}"
    logging.info(entry)
    print("[AUDIT] " + entry)


_CONFIRM_PROVIDER = None


def set_confirm_provider(fn):
    """Registra un confirmador alternativo (p.ej. por voz desde la GUI)."""
    global _CONFIRM_PROVIDER
    _CONFIRM_PROVIDER = fn


def confirm_action(prompt, title="Emma - Confirmar"):
    provider = _CONFIRM_PROVIDER
    if provider is not None:
        try:
            return bool(provider(prompt))
        except Exception:
            pass
    try:
        return ctypes.windll.user32.MessageBoxW(0, prompt, title, 4) == 6
    except Exception:
        try:
            resp = input(prompt + " [y/N]: ").strip().lower()
            return resp in ("y", "yes", "s", "si")
        except Exception:
            return False


def _resolve_app_path(name):
    """Resuelve una app por alias, App Paths del registro o busqueda en rutas comunes."""
    key = name.strip().lower()
    if key in APP_ALIASES and APP_ALIASES[key]:
        p = APP_ALIASES[key]
        if os.path.exists(p):
            return p
    # Buscar en App Paths del registro
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
            try:
                k = winreg.OpenKey(hive, base)
                for i in range(winreg.QueryInfoKey(k)[0]):
                    ename = winreg.EnumKey(k, i)
                    if name.lower() in ename.lower():
                        with winreg.OpenKey(hive, base + "\\" + ename) as ek:
                            path, _ = winreg.QueryValueEx(ek, "")
                            if os.path.exists(path):
                                return path
            except OSError:
                continue
    except Exception:
        pass
    # Si es una ruta directa
    if os.path.exists(name):
        return name
    # Si tiene .exe en nombre
    for ext in (".exe",):
        candidate = name if name.endswith(ext) else name + ext
        for base in (r"C:\Windows\System32", r"C:\Windows", PROJECT_DIR):
            full = os.path.join(base, candidate)
            if os.path.exists(full):
                return full
    return None


def list_processes(filter_text=""):
    """Lista procesos en ejecucion (local)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Process | Where-Object {{ $_.MainWindowTitle }} | Select-Object -First 30 ProcessName, MainWindowTitle | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=20)
        return out.stdout or "Sin ventanas activas"
    except Exception as e:
        return "Error: " + str(e)


def _resolve_target(target):
    """Resuelve el nombre real de la app tomando solo las primeras palabras
    que coinciden con una app instalada. Evita 'Brave web my browser ok...'."""
    apps = appreg.build_registry()
    words = [w for w in target.split() if w]
    cleaned = [w.strip(".,;:!?\u00bf\u00a1\"'()[]").lower() for w in words]
    cleaned = [w for w in cleaned if w]
    # 1) clave exacta, prefiriendo el prefijo mas largo de palabras
    for n in range(min(len(cleaned), 6), 0, -1):
        cand = " ".join(cleaned[:n])
        for key in (cand, cand + ".exe"):
            if key in apps:
                return apps[key], cand
    # 2) subconjunto de palabras
    for n in range(min(len(cleaned), 6), 0, -1):
        cand = " ".join(cleaned[:n])
        qwords = set(cand.split())
        for name, path in apps.items():
            base = name.replace(".exe", "").replace(".lnk", "")
            if qwords and qwords.issubset(set(base.replace("-", " ").replace("_", " ").split())):
                return path, cand
    # 3) prefijo de la primera palabra (ej: 'whats' -> whatsapp)
    first = cleaned[0] if cleaned else ""
    if first:
        for name, path in apps.items():
            base = name.replace(".exe", "").replace(".lnk", "")
            if base.startswith(first) or first.startswith(base):
                return path, first
    return None, target


def launch_app(name, args=None, auto=False):
    """Lanza cualquier app instalada en VICTORYMAR.
    auto=True (el usuario dijo 'hazlo ya') salta la confirmacion."""
    path, display = _resolve_target(name)
    if not path:
        audit("launch_app", name, False, "Not found")
        return False, f"No encuentro '{name}'. Prueba con otro nombre o dame la ruta."
    if auto or confirm_action("¿Lanzar " + display + "?"):
        try:
            _smart_launch(path, args)
            appreg.record_usage(display)
            emma_memory.log_event("launch_app", display)
            audit("launch_app", f"{display} -> {path}", True)
            return True, f"Lanzado: {display}"
        except Exception as e:
            audit("launch_app", path, False, str(e))
            return False, str(e)
    audit("launch_app", path, False, "User cancelled")
    return False, "Cancelado por el usuario"


def _smart_launch(path, args=None):
    """Lanza considerando tipo de destino."""
    p = path.strip()
    extra = args or []
    if p.startswith("steam://"):
        subprocess.Popen(["cmd", "/c", "start", "", p], shell=False)
    elif "!" in p and not os.path.exists(p):
        # UWP AppID -> explorer shell:AppsFolder
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + p])
    elif p.lower().endswith(".lnk"):
        os.startfile(p)
    elif p.lower().endswith((".exe", ".bat", ".cmd", ".msc")):
        subprocess.Popen([p] + extra, cwd=os.path.dirname(os.path.abspath(__file__)))
    else:
        os.startfile(p)


def close_app(name, auto=False):
    """Cierra una app en ejecucion por nombre de proceso."""
    proc = name if name.endswith(".exe") else name + ".exe"
    if auto or confirm_action("¿Cerrar " + name + "?"):
        try:
            r = subprocess.run(["taskkill", "/F", "/IM", proc],
                               capture_output=True, text=True, timeout=15)
            ok = r.returncode == 0
            audit("close_app", name, ok, r.stdout.strip() or r.stderr.strip())
            return ok, ("Cerrado: " + name) if ok else ("No se pudo cerrar: " + r.stderr.strip())
        except Exception as e:
            audit("close_app", name, False, str(e))
            return False, str(e)
    return False, "Cancelado"


def open_folder(path, auto=False):
    """Abre una carpeta en el Explorador (soporta nombres conocidos en ES/EN)."""
    known = {
        "documentos": "Documents", "documents": "Documents",
        "escritorio": "Desktop", "desktop": "Desktop",
        "descargas": "Downloads", "downloads": "Downloads",
        "imagenes": "Pictures", "imágenes": "Pictures", "pictures": "Pictures",
        "musica": "Music", "música": "Music", "music": "Music",
        "videos": "Videos", "vídeos": "Videos",
    }
    p = path.strip().strip(" .,;:!?¿¡\"'")
    if p.lower() in known:
        p = os.path.join(os.environ.get("USERPROFILE", ""), known[p.lower()])
    if not os.path.isdir(p):
        cand = os.path.join(PROJECT_DIR, p)
        if os.path.isdir(cand):
            p = cand
        else:
            return False, "Carpeta no existe: " + path
    if auto or confirm_action("¿Abrir la carpeta " + os.path.basename(os.path.normpath(p)) + "?"):
        try:
            subprocess.Popen(["explorer.exe", p])
            audit("open_folder", p, True)
            return True, "Carpeta abierta: " + p
        except Exception as e:
            audit("open_folder", p, False, str(e))
            return False, str(e)
    return False, "Cancelado"


def create_file(path, content=""):
    if not any(os.path.abspath(path).startswith(d) for d in ALLOWED_DIRS):
        audit("create_file", path, False, "Outside allowed directories")
        return False, "Directorio no permitido: " + os.path.abspath(path)
    if confirm_action("¿Creo el archivo " + os.path.basename(path) + "?"):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(os.path.abspath(path), "w", encoding="utf-8") as f:
                f.write(content)
            audit("create_file", os.path.abspath(path), True)
            return True, "Archivo creado: " + os.path.abspath(path)
        except Exception as e:
            audit("create_file", os.path.abspath(path), False, str(e))
            return False, str(e)
    return False, "Cancelado"


def run_cmd(cmdline):
    """Ejecuta un comando local en VICTORYMAR (con confirmacion)."""
    if confirm_action("¿Ejecutar comando en VICTORYMAR?\n" + cmdline):
        try:
            r = subprocess.run(cmdline, shell=True, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR)
            audit("run_cmd", cmdline[:80], r.returncode == 0)
            out = (r.stdout or "") + (r.stderr or "")
            return r.returncode == 0, out.strip()[:1500] or "OK (sin salida)"
        except Exception as e:
            audit("run_cmd", cmdline[:80], False, str(e))
            return False, str(e)
    return False, "Cancelado"


def system_info():
    """Info del sistema local."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$os = Get-CimInstance Win32_OperatingSystem; "
             "$cs = Get-CimInstance Win32_ComputerSystem; "
             "$d = Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\"; "
             "Write-Output ('Hostname: ' + $env:COMPUTERNAME); "
             "Write-Output ('OS: ' + $os.Caption); "
             "Write-Output ('RAM: ' + [math]::Round($cs.TotalPhysicalMemory/1GB,1) + ' GB'); "
             "Write-Output ('Uptime: ' + ((Get-Date) - $os.LastBootUpTime).ToString()); "
             "foreach($x in $d){ Write-Output ('Disk ' + $x.DeviceID + ': ' + [math]::Round($x.FreeSpace/1GB,1) + ' GB libre de ' + [math]::Round($x.Size/1GB,1) + ' GB') }"],
            capture_output=True, text=True, timeout=30)
        return out.stdout or "Error obteniendo info"
    except Exception as e:
        return "Error: " + str(e)


def handle_command(cmd):
    """Procesa comandos de lenguaje natural con permisos TOTALES en VICTORYMAR."""
    c = cmd.strip().lower()
    orig = cmd.strip()

    # --- Ayuda / info ---
    if c in ("/ayuda", "/help", "?"):
        return True, _help()
    if c == "/whitelist":
        return True, _whitelist_text()
    if c in ("/info", "/sysinfo"):
        return True, system_info()
    if c in ("/salir", "/exit", "/q"):
        return False, "salir"
    if c == "/apps":
        return True, list_processes()

    # --- Atajos: correo / bandeja ---
    if any(p in c for p in ("check my inbox", "check my email", "check my mail",
                            "revisa mi correo", "revisar mi correo", "mi bandeja",
                            "revisa mi bandeja", "abre mi correo", "mis correos")):
        return launch_app("outlook")

    # --- Lanzar apps (ES + EN) ---
    for kw in ("abre ", "abrir ", "lanza ", "lanzar ", "ejecuta ", "ejecutar ",
               "inicia ", "iniciar ", "open ", "launch ", "run ", "start "):
        if c.startswith(kw):
            rest = orig[len(kw):].strip()
            rest = _strip_clauses(rest)
            return launch_app(rest)
    if c in ("abre", "lanza", "ejecuta", "open", "launch", "run"):
        return False, "¿Qué app? Ej: abre chrome / open outlook"

    # --- Cerrar apps (ES + EN) ---
    for kw in ("cierra ", "cerrar ", "mata ", "termina ", "close ", "kill "):
        if c.startswith(kw):
            rest = _strip_clauses(orig[len(kw):].strip())
            return close_app(rest)

    # --- Carpetas ---
    for kw in ("abre carpeta ", "abrir carpeta ", "explora ", "carpeta "):
        if c.startswith(kw):
            rest = orig[len(kw):].strip()
            ok, msg = open_folder(rest)
            return ok, msg

    # --- Apagar/reiniciar (local, doble confirmacion) ---
    if c.startswith(("apaga", "apagar", "apaga el pc", "shutdown")):
        delay = _parse_delay(c)
        if confirm_action(f"¿APAGAR VICTORYMAR en {delay}s? (irreversible)"):
            ok, msg = run_cmd(f"shutdown /s /t {delay} /f")
            return ok, "Apagado programado en " + str(delay) + "s. " + msg
        return False, "Cancelado"
    if c.startswith(("reinicia", "reiniciar", "restart")):
        delay = _parse_delay(c)
        if confirm_action(f"¿REINICIAR VICTORYMAR en {delay}s? (irreversible)"):
            ok, msg = run_cmd(f"shutdown /r /t {delay} /f")
            return ok, "Reinicio programado en " + str(delay) + "s. " + msg
        return False, "Cancelado"

    # --- Crear archivo ---
    for kw in ("crea ", "crear ", "nuevo archivo "):
        if c.startswith(kw):
            rest = orig[len(kw):].strip()
            if " con " in rest:
                parts = rest.split(" con ", 1)
                return create_file(parts[0].strip(), parts[1].strip())
            return create_file(rest)

    # --- Ejecutar comando bruto ---
    if c.startswith("/cmd "):
        return run_cmd(orig[5:].strip())

    return False, "No entiendo: '" + orig + "'. Prueba /ayuda"


def _strip_clauses(text):
    """Quita clausulas extra: 'outlook and check my inbox' -> 'outlook'."""
    low = text.lower()
    for sep in (" and ", " y ", " to check", " para ", " para que", ", ",
                " luego ", " despues ", " después "):
        i = low.find(sep)
        if i > 0:
            text = text[:i].strip()
            low = text.lower()
    return text.strip().rstrip("?.!,;")


_OPEN_VERBS = (r"(?:abre|abres|abras|abr[áa]s|abreme|[áa]breme|abrirme|abrir|abrir[áa]s|"
               r"abran|open|opens|launch|launches|run|runs|start|starts|"
               r"ejecuta|ejecutar|lanza|lanzar|inicia|iniciar)")
_CLOSE_VERBS = r"(?:cierra|cierres|cerrar|close|closes|kill|kills|mata|matar|termina|terminar)"
_EMAIL_PHRASES = ("check my inbox", "check my email", "check my mail",
                  "revisa mi correo", "revisar mi correo", "mi bandeja",
                  "revisa mi bandeja", "abre mi correo", "mis correos")

_AUTO_PHRASES = ("just do it", "do it now", "hazlo ya", "hazlo ahora",
                 "sin preguntar", "no me preguntes", "obedece",
                 "ahora mismo", "sin confirmar", "no confirmes")


def _process_running(name):
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout.lower()
        key = name.lower().strip()
        if not key.endswith(".exe"):
            key += ".exe"
        return key in out
    except Exception:
        return False


def _clean_target(after):
    t = _strip_clauses(after)
    t = re.sub(r"^(?:me|nos|mi|mis|el|la|los|las|un|una|the|my|our|your)\s+", "", t, flags=re.I)
    t = re.sub(r"\s+(?:please|por favor|for me|para mi|ahora|now)$", "", t, flags=re.I)
    return t.strip(" .,;:!?¿¡\"'()[]")


def try_handle(text):
    """Intenta ejecutar una orden de sistema en cualquier fraseo (ES/EN).
    Solo actua si el destino existe de verdad (app registrada o proceso vivo),
    para no robar frases normales de practica de ingles.
    Devuelve (handled, ok, msg)."""
    orig = text.strip()
    low = orig.lower()

    # Atajos de correo en cualquier posicion
    for p in _EMAIL_PHRASES:
        if p in low:
            ok, msg = launch_app("outlook")
            return True, ok, msg

    # Dispositivo de red de confianza: apagar/reiniciar por nombre (NO VICTORYMAR)
    m = re.match(r"^(?:apaga|apagar|reinicia|reiniciar)\s+(.+)", low)
    if m:
        dev = home_net.resolve_device(m.group(1))
        if dev is not None and not dev.get("Local"):
            ok, msg = home_net.shutdown(dev.get("Name"), confirm=confirm_action)
            return True, ok, msg

    # Apagar / reiniciar (solo al inicio de la frase)
    if re.match(r"^(?:apaga|apagar|shutdown)\b", low):
        return (True,) + handle_command(orig)
    if re.match(r"^(?:reinicia|reiniciar|restart)\b", low):
        return (True,) + handle_command(orig)

    # Abrir carpeta
    auto = any(p in low for p in _AUTO_PHRASES)
    m = re.search(r"\b(?:abre|abrir|open|launch)\s+(?:la\s+|el\s+|the\s+)?(?:carpeta|folder)\s+(.+)$", low)
    if m:
        target = orig[m.start(1):].strip().strip(" .,;:!?¿¡\"'")
        ok, msg = open_folder(target, auto=auto)
        return True, ok, msg

    # Abrir app: verbo en cualquier posicion + destino que exista en el registro
    m = re.search(_OPEN_VERBS, low)
    if m:
        target = _clean_target(orig[m.end():])
        if target:
            path, display = _resolve_target(target)
            if path:
                ok, msg = launch_app(display, auto=auto)
                return True, ok, msg

    # Cerrar app: solo si el destino es una app conocida o un proceso vivo
    m = re.search(_CLOSE_VERBS, low)
    if m:
        target = _clean_target(orig[m.end():])
        if target:
            path, display = _resolve_target(target)
            if path or _process_running(target):
                ok, msg = close_app(display, auto=auto)
                return True, ok, msg

    return False, None, None


def _parse_delay(cmd):
    """Extrae delay en segundos: 'en 5 minutos', 'en 300', 'en 2 min'."""
    try:
        if " en " in cmd:
            parte = cmd.split(" en ")[1].strip()
            num = ""
            for ch in parte:
                if ch.isdigit():
                    num += ch
                else:
                    break
            n = int(num) if num else 0
            if "minuto" in parte or "min" in parte:
                n *= 60
            return n
    except Exception:
        pass
    return 0


def _whitelist_text():
    return (
        "Control TOTAL de VICTORYMAR (local):\n"
        "  - TODAS las apps instaladas (abre chrome, abre vscode, abre telegram...)\n"
        "  - Cerrar procesos (cierra chrome)\n"
        "  - Carpetas (abre carpeta Documentos)\n"
        "  - Archivos (crea nota.txt con texto)\n"
        "  - Comandos (/cmd dir)\n"
        "  - Apagado/reinicio con doble confirmacion\n"
        "  - COOPERACION con opencode via mailbox (/ayuda opencode)\n"
        "Todo requiere confirmacion y queda auditado"
    )


def _help():
    return (
        "Emma Asistente v4.0 - Control total VICTORYMAR:\n"
        "  abre/ejecuta [app]: lanza cualquier app (chrome, vscode, telegram...)\n"
        "  cierra [app]: cierra proceso en ejecucion\n"
        "  abre carpeta [ruta]: abre en el Explorador\n"
        "  crea [archivo] con [texto]: crea archivo en carpetas permitidas\n"
        "  apaga [en N min] / reinicia [en N min]: con doble confirmacion\n"
        "  /cmd [comando]: ejecuta comando local con confirmacion\n"
        "  /apps: lista ventanas abiertas\n"
        "  /sysinfo: estado de VICTORYMAR\n"
        "  /red: estado de la red de dispositivos de confianza\n"
        "  despierta [dispositivo]: enciende por Wake-on-LAN (ej: despierta la tele)\n"
        "  apaga [dispositivo]: apaga un dispositivo remoto (nunca VICTORYMAR)\n"
        "  /plan [new]: plan de ingles de 4 semanas\n"
        "  /coop: canal de cooperacion con opencode\n"
        "  /ayuda: este mensaje\n"
        "Todo queda auditado en assistant_audit.log"
    )


if __name__ == "__main__":
    print("=== Emma Personal Assistant v4.0 ===")
    print(_help())
    while True:
        try:
            cmd = input("Emma> ").strip()
            if not cmd:
                continue
            ok, msg = handle_command(cmd)
            if ok is False and "salir" in str(msg).lower():
                print("Adiós!")
                break
            print(msg)
        except KeyboardInterrupt:
            print("\nAdiós!")
            break
