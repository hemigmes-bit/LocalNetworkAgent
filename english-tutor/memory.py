"""memory.py - Memoria persistente de Emma (JSONL append-only).
Patron tomado de yoyo-evolve: archivos append-only como fuente de verdad,
sintesis periodica que comprime lo antiguo en contexto activo.
"""
import os
import json
import time
from datetime import datetime

MEM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
LEARNINGS = os.path.join(MEM_DIR, "learnings.jsonl")
EVENTS = os.path.join(MEM_DIR, "events.jsonl")
ACTIVE = os.path.join(MEM_DIR, "active_memory.md")


def ensure():
    os.makedirs(MEM_DIR, exist_ok=True)
    for f in (LEARNINGS, EVENTS):
        if not os.path.exists(f):
            open(f, "a", encoding="utf-8").close()


def _append(path, entry):
    ensure()
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def learn(category, content, importance=1):
    """Emma aprende algo: categoria + contenido + importancia 1-5."""
    _append(LEARNINGS, {"type": "learning", "category": category,
                        "content": content, "importance": importance})


def log_event(event_type, details=""):
    """Evento relevante (errores, cambios, acciones)."""
    _append(EVENTS, {"type": "event", "event": event_type, "details": details})


def recent_learnings(n=20, category=None):
    """Ultimos aprendizajes."""
    ensure()
    out = []
    if os.path.exists(LEARNINGS):
        with open(LEARNINGS, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if category and e.get("category") != category:
                        continue
                    out.append(e)
                except Exception:
                    continue
    return out[-n:]


def recent_events(n=20):
    ensure()
    out = []
    if os.path.exists(EVENTS):
        with open(EVENTS, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out[-n:]


def synthesize():
    """Genera memoria activa (contexto comprimido) para inyectar en prompts."""
    ensure()
    ls = recent_learnings(50)
    ev = recent_events(50)
    lines = ["# Memoria activa de Emma (auto-generada)",
             f"# Sintesis: {datetime.now().isoformat(timespec='minutes')}", ""]
    if ls:
        lines.append("## Aprendizajes recientes")
        for e in ls[-15:]:
            lines.append(f"- [{e['ts']}] ({e['category']}) {e['content']}")
    if ev:
        lines.append("\n## Eventos recientes")
        for e in ev[-15:]:
            lines.append(f"- [{e['ts']}] {e['event']}: {e['details'][:120]}")
    content = "\n".join(lines)
    with open(ACTIVE, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def get_active():
    ensure()
    if not os.path.exists(ACTIVE):
        return synthesize()
    with open(ACTIVE, encoding="utf-8") as f:
        return f.read()


def stats():
    ensure()
    lc = sum(1 for _ in open(LEARNINGS, encoding="utf-8")) if os.path.exists(LEARNINGS) else 0
    ec = sum(1 for _ in open(EVENTS, encoding="utf-8")) if os.path.exists(EVENTS) else 0
    return {"learnings": lc, "events": ec, "dir": MEM_DIR}


if __name__ == "__main__":
    ensure()
    learn("test", "Sistema de memoria funcionando", 3)
    log_event("startup", "Memory module init")
    print(json.dumps(stats(), indent=2))
    print(synthesize())
