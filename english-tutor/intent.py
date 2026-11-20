"""intent.py - Clasificador de intencion con LLM.
Cuando el router rapido por regex no reconoce la orden, el LLM decide si
es un comando de sistema y extrae accion + destino.
Solo se invoca cuando hay pistas de orden, para no secuestrar la practica de ingles.
"""
from providers import chat, parse_json

ACTIONS = {"launch", "close", "network_status", "wake", "shutdown_device", "study_plan", "ack"}

_CUES = (
    "abre", "abrir", "abreme", "open", "lanza", "lanzar", "launch", "ejecuta", "ejecutar",
    "inicia", "iniciar", "cierra", "cerrar", "close", "mata ", "kill ",
    "apaga", "apagar", "reinicia", "reiniciar", "restart", "shutdown",
    "enciende", "encender", "prende", "prender", "despierta", "despertar", "wake",
    "fire up", "turn on", "turn off", "ponme", "pon la", "reproduce", "switch to",
    "estado", "status", "red", "network", "dispositivo", "device", "dispositivos",
    "tv", "television", "plan", "estudiar", "estudio", "study",
    "orden", "obedece", "hazme caso", "escuchame", "esc\u00fachame",
    "show status", "show me the status", "muestra el estado", "dime el estado",
)

SYSTEM = """You are the intent router for a Windows desktop assistant named Emma.
Decide whether the user's message is a SYSTEM COMMAND (control the computer or trusted home network) or normal English-practice conversation.
Return ONLY valid JSON with this exact shape:
{"command": true, "action": "launch", "target": "brave", "confidence": 0.9}

Allowed actions:
- "launch": open a program/application
- "close": close a running application
- "network_status": show status of trusted home devices (TV, server, phones...)
- "wake": turn on a device with Wake-on-LAN
- "shutdown_device": power off a REMOTE trusted device (never the local PC)
- "study_plan": create or show the user's English study plan
- "ack": the user gives an instruction/order to the assistant that is not a specific action (e.g. "stop", "wait", "be brief", "obey me"); confirm briefly
- "none": not a system command

Rules:
- target must be a short lowercase app or device name (e.g. "brave", "spotify", "tv samsung", "core0").
- If the message is English practice, grammar questions, conversation starters, or role-play, set command=false, action="none".
- Never choose shutdown_device for the local computer named VICTORYMAR.
"""


def should_classify(text):
    low = (text or "").lower()
    return any(c in low for c in _CUES)


def classify(client, cfg, text):
    """Devuelve {"action","target"} si es comando, o None."""
    if not text or not should_classify(text):
        return None
    try:
        raw = chat(client, cfg,
                   [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": text}],
                   temperature=0.0, json_mode=True)
        data = parse_json(raw) or {}
    except Exception:
        return None
    if not data.get("command"):
        return None
    action = str(data.get("action") or "none").lower()
    if action not in ACTIONS:
        return None
    try:
        confidence = float(data.get("confidence") or 0)
    except Exception:
        confidence = 0.0
    if confidence < 0.55:
        return None
    return {"action": action, "target": str(data.get("target") or "").strip()}
