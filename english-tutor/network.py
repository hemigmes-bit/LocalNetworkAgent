"""network.py - Gestion de dispositivos de confianza en la red local.
Lee ../network-config.json del proyecto LocalNetworkAgent.
- estado (ping + puertos)
- encender con Wake-on-LAN
- apagar remoto por WinRM (SOLO dispositivos no locales)

Seguridad: VICTORYMAR (Local=true) NUNCA se apaga/reinicia desde aqui.
"""
import json
import logging
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_CANDIDATES = [BASE.parent / "network-config.json", BASE / "network-config.json"]
CRED_CANDIDATES = [BASE.parent / "core0-cred.xml", BASE / "core0-cred.xml"]
AUDIT_LOG = BASE / "assistant_audit.log"

logging.basicConfig(filename=str(AUDIT_LOG), level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")


def _audit(action, target, ok, details=""):
    try:
        logging.info("network | " + ("OK" if ok else "FAIL") + " | " + action +
                     " | " + str(target) + " | " + str(details))
    except Exception:
        pass
    print("[AUDIT] network | " + ("OK" if ok else "FAIL") + " | " + action + " | " + str(target))


def load_devices():
    for p in CONFIG_CANDIDATES:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("Computers", []), data
            except Exception:
                pass
    return [], {}


def _ports(dev):
    raw = str(dev.get("OpenPorts") or "")
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def _ping(ip, timeout_ms=900):
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", str(timeout_ms), ip],
                           capture_output=True, timeout=(timeout_ms / 1000.0) + 4)
        return r.returncode == 0
    except Exception:
        return False


def _tcp(ip, port, timeout=0.8):
    try:
        with socket.create_connection((ip, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def _resolve(device):
    devices, cfg = load_devices()
    q = (device or "").strip().lower()
    if not q:
        return None, cfg
    for w in ("tele", "television", "televisor", "la tele", "la television"):
        if w in q:
            q = q.replace(w, "tv")
    for d in devices:
        if q == str(d.get("IP")) or q in str(d.get("Name", "")).lower():
            return d, cfg
    for d in devices:
        words = str(d.get("Name", "")).lower().replace("/", " ").split()
        if any(w and len(w) > 2 and w in q for w in words):
            return d, cfg
    return None, cfg


def resolve_device(name):
    """Devuelve el dict del dispositivo o None."""
    d, _cfg = _resolve(name)
    return d


def status(device=None):
    devices, _cfg = load_devices()
    if not devices:
        return False, "No encuentro network-config.json"
    targets = devices
    if device:
        d, _ = _resolve(device)
        if not d:
            return False, "No conozco el dispositivo '" + device + "'"
        targets = [d]

    def check(d):
        if d.get("Local"):
            return d.get("Name"), "esta maquina", True, []
        ip = d.get("IP")
        if not ip:
            return d.get("Name"), "sin IP", False, []
        alive = _ping(ip)
        open_ports = []
        ports = _ports(d)
        if alive and ports:
            with ThreadPoolExecutor(max_workers=len(ports)) as ex:
                results = list(ex.map(lambda p: (p, _tcp(ip, p)), ports))
            open_ports = [p for p, ok in results if ok]
        return d.get("Name"), ip, alive, open_ports

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(check, targets))

    lines = []
    for name, ip, alive, open_ports in results:
        st = "ONLINE" if alive else "offline"
        extra = (" | puertos: " + ",".join(map(str, open_ports))) if open_ports else ""
        lines.append("- " + str(name) + " (" + str(ip) + "): " + st + extra)
    return True, "Estado de la red:\n" + "\n".join(lines)


def _broadcast_addr(cfg):
    prefix = str(cfg.get("SubnetPrefix") or "").strip()
    if prefix.count(".") == 2:
        return prefix + ".255"
    return "255.255.255.255"


def wake(device):
    d, cfg = _resolve(device)
    if not d:
        return False, "No conozco el dispositivo '" + str(device) + "'"
    mac = d.get("MAC")
    if not mac:
        return False, str(d.get("Name")) + " no tiene MAC registrada"
    try:
        macb = bytes.fromhex(str(mac).replace(":", "").replace("-", ""))
        packet = b"\xff" * 6 + macb * 16
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for addr in ("255.255.255.255", _broadcast_addr(cfg)):
            try:
                s.sendto(packet, (addr, 9))
            except Exception:
                pass
        s.close()
        _audit("wake", d.get("Name"), True, mac)
        return True, "Magic packet enviado a " + str(d.get("Name")) + " (" + str(mac) + ")"
    except Exception as e:
        _audit("wake", d.get("Name"), False, str(e))
        return False, str(e)


def shutdown(device, confirm=None):
    """Apaga un dispositivo remoto de confianza (NUNCA VICTORYMAR)."""
    d, _cfg = _resolve(device)
    if not d:
        return False, "No conozco el dispositivo '" + str(device) + "'"
    if d.get("Local"):
        return False, "VICTORYMAR es esta maquina: no se apaga desde aqui"
    ip = d.get("IP")
    if not ip:
        return False, "El dispositivo no tiene IP registrada"
    if 5985 not in _ports(d):
        return False, str(d.get("Name")) + " no tiene WinRM (5985) configurado"
    cred = None
    for p in CRED_CANDIDATES:
        if p.exists():
            cred = p
            break
    if cred is None:
        return False, "Falta core0-cred.xml para WinRM"
    if confirm is not None and not confirm("¿Apagar " + str(d.get("Name")) + " (" + str(ip) + ")?"):
        return False, "Cancelado"
    ps = ("Invoke-Command -ComputerName " + str(ip) +
          " -Credential (Import-Clixml '" + str(cred) + "')" +
          " -ScriptBlock { shutdown.exe /s /t 0 /f }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=90)
        ok = r.returncode == 0
        _audit("shutdown", d.get("Name"), ok, (r.stderr or "").strip()[:120])
        return ok, ("Apagado remoto enviado a " + str(d.get("Name"))) if ok else ("Fallo: " + (r.stderr or "").strip()[:200])
    except Exception as e:
        _audit("shutdown", d.get("Name"), False, str(e))
        return False, str(e)


def device_names():
    devices, _ = load_devices()
    return [d.get("Name") for d in devices if d.get("Name")]


if __name__ == "__main__":
    print("Dispositivos:", device_names())
    ok, msg = status()
    print(msg)
