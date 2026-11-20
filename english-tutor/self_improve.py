"""self_improve.py - Emma puede leer, analizar y mejorar su propio codigo.
Siempre con backups automaticos y validacion de sintaxis antes de aplicar.

Flujo:
1. Emma (via LLM) propone un cambio en uno de sus archivos
2. self_improve aplica el cambio con backup en backups/
3. Valida sintaxis con py_compile
4. Si falla, restaura el backup automaticamente
5. Registra todo en improve.log

COOPERACION: cuando Emma necesita ayuda de opencode, escribe al mailbox
y espera la respuesta antes de aplicar cambios complejos.
"""
import os
import sys
import shutil
import json
import logging
import py_compile
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")
IMPROVE_LOG = os.path.join(PROJECT_DIR, "improve.log")

logging.basicConfig(filename=IMPROVE_LOG, level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")

# Archivos que Emma puede modificar (su propio nucleo)
EDITABLE_FILES = [
    "assistant.py",
    "tutor.py",
    "prompts.py",
    "config.json",
    "level_progression.py",
    "voice.py",
    "main.py",
    "emma_gui.py",
    "mailbox.py",
]

# Archivos INTOCABLES (nunca)
PROTECTED = [
    "db.py",           # base de datos - riesgo de corrupcion
    "providers.py",    # credenciales API
    "api-token.json",  # secretos
    "BIBLE.md",        # identidad inmutable de Emma
]


def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_file(rel_path):
    """Crea backup con timestamp."""
    ensure_backup_dir()
    src = os.path.join(PROJECT_DIR, rel_path)
    if not os.path.exists(src):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"{os.path.basename(rel_path)}.{ts}.bak")
    shutil.copy2(src, dst)
    return dst


def list_backups(rel_path=None):
    ensure_backup_dir()
    if rel_path:
        return sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(os.path.basename(rel_path))], reverse=True)[:10]
    return sorted(os.listdir(BACKUP_DIR), reverse=True)[:20]


def can_edit(rel_path):
    """Verifica si el archivo es editable."""
    base = os.path.basename(rel_path)
    if base in PROTECTED:
        return False, f"{base} esta protegido (no editable)"
    if base not in EDITABLE_FILES and not rel_path.endswith(".py"):
        return False, f"{base} no esta en la lista de editables"
    return True, "OK"


def read_source(rel_path):
    """Lee el codigo fuente de un archivo del proyecto."""
    p = os.path.join(PROJECT_DIR, rel_path)
    if not os.path.exists(p):
        return None, "No existe: " + rel_path
    try:
        with open(p, encoding="utf-8") as f:
            return f.read(), "OK"
    except Exception as e:
        return None, str(e)


def apply_change(rel_path, new_content, note="", validate=True):
    """Aplica un cambio con backup + validacion de sintaxis + rollback automatico."""
    ok, reason = can_edit(rel_path)
    if not ok:
        return False, reason

    src = os.path.join(PROJECT_DIR, rel_path)
    if not os.path.exists(src):
        return False, "No existe: " + rel_path

    # Backup
    bak = backup_file(rel_path)

    # Guardar nuevo contenido
    try:
        with open(src, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        if bak:
            shutil.copy2(bak, src)
        return False, "Error al escribir: " + str(e)

    # Validar sintaxis si es .py
    if validate and rel_path.endswith(".py"):
        try:
            py_compile.compile(src, doraise=True)
        except py_compile.PyCompileError as e:
            # ROLLBACK automatico
            if bak:
                shutil.copy2(bak, src)
            logging.warning(f"ROLLBACK {rel_path}: {e}")
            return False, "Error de sintaxis, se restauro backup: " + str(e)

    logging.info(f"CHANGE APPLIED {rel_path} | backup: {bak} | note: {note}")
    return True, f"Cambio aplicado a {rel_path} (backup: {os.path.basename(bak) if bak else 'N/A'})"


def project_structure():
    """Mapa de la arquitectura de Emma para que el LLM la entienda."""
    return {
        "emma_gui.py": "GUI principal (CustomTkinter) - interfaz, avatar, subtitulos",
        "tutor.py": "Motor del tutor - logica pedagogica, correcciones, nivel",
        "prompts.py": "Ingenieria de prompts del LLM",
        "voice.py": "Voz: STT (faster-whisper) + TTS (Kokoro/edge-tts)",
        "assistant.py": "Asistente personal: control de apps en VICTORYMAR",
        "mailbox.py": "Canal de cooperacion Emma<->opencode",
        "level_progression.py": "Sistema CEFR A1-C2",
        "db.py": "Base de datos SQLite (PROTEGIDO)",
        "providers.py": "Clientes LLM (PROTEGIDO)",
        "config.json": "Configuracion (niveles, voces, idioma)",
        "main.py": "Modo consola",
        "backups/": "Backups automaticos de cambios",
        "mailbox/": "Mensajes entre Emma y opencode",
    }


if __name__ == "__main__":
    print("Self-improve module de Emma")
    print(json.dumps(project_structure(), indent=2, ensure_ascii=False))
    print("\nBackups:", list_backups())
