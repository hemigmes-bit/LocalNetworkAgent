"""mailbox.py - Canal de cooperacion Emma <-> opencode.
Emma escribe peticiones en mailbox/outbox/opencode_<ts>.json
opencode responde en mailbox/inbox/opencode_<ts>.json
Emma lee las respuestas y las integra a su arquitectura.

Estructura del mensaje:
{
  "id": "uuid",
  "from": "emma" | "opencode",
  "type": "help_request" | "code_change" | "architecture_review" | "answer" | "status",
  "subject": "...",
  "body": "...",
  "files": ["relativo1.py", ...],
  "status": "open" | "done" | "rejected",
  "created": "ISO8601",
  "response_to": "uuid opcional"
}
"""
import os
import json
import uuid
from datetime import datetime

MAILBOX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mailbox")
OUTBOX = os.path.join(MAILBOX_DIR, "outbox")
INBOX = os.path.join(MAILBOX_DIR, "inbox")
HISTORY = os.path.join(MAILBOX_DIR, "history")


def ensure_dirs():
    for d in (MAILBOX_DIR, OUTBOX, INBOX, HISTORY):
        os.makedirs(d, exist_ok=True)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def write_outbox(subject, body, msg_type="help_request", files=None):
    """Emma escribe una peticion para opencode."""
    ensure_dirs()
    msg = {
        "id": str(uuid.uuid4())[:8],
        "from": "emma",
        "type": msg_type,
        "subject": subject,
        "body": body,
        "files": files or [],
        "status": "open",
        "created": _now(),
    }
    path = os.path.join(OUTBOX, f"emma_{msg['id']}_{_now().replace(':', '-')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    return msg


def read_inbox():
    """Lee respuestas de opencode pendientes de procesar."""
    ensure_dirs()
    msgs = []
    for fn in sorted(os.listdir(INBOX)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(INBOX, fn), encoding="utf-8") as f:
                msg = json.load(f)
            if msg.get("status") == "open":
                msgs.append(msg)
        except Exception:
            continue
    return msgs


def mark_processed(msg, result="done"):
    """Mueve mensaje de inbox a history con estado."""
    ensure_dirs()
    msg["status"] = result
    msg["processed"] = _now()
    hist_path = os.path.join(HISTORY, f"processed_{msg['id']}_{_now().replace(':', '-')}.json")
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    # Borrar original del inbox
    for fn in os.listdir(INBOX):
        p = os.path.join(INBOX, fn)
        try:
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
            if m.get("id") == msg["id"]:
                os.remove(p)
        except Exception:
            continue
    return True


def pending_outbox():
    """Lista peticiones de Emma aun sin respuesta."""
    ensure_dirs()
    msgs = []
    for fn in sorted(os.listdir(OUTBOX)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(OUTBOX, fn), encoding="utf-8") as f:
                msg = json.load(f)
            if msg.get("status") == "open":
                msgs.append(msg)
        except Exception:
            continue
    return msgs


def status():
    ensure_dirs()
    out = len(pending_outbox())
    inc = len(read_inbox())
    hist = len([f for f in os.listdir(HISTORY) if f.endswith(".json")]) if os.path.isdir(HISTORY) else 0
    return {
        "outbox_pending": out,
        "inbox_unread": inc,
        "history": hist,
        "dir": MAILBOX_DIR,
    }


if __name__ == "__main__":
    ensure_dirs()
    s = status()
    print("Mailbox Emma<->opencode:")
    print(json.dumps(s, indent=2, ensure_ascii=False))
    if s["inbox_unread"] > 0:
        print("\nMensajes de opencode pendientes:")
        for m in read_inbox():
            print(f"  [{m['id']}] {m['subject']}: {m['body'][:100]}")
