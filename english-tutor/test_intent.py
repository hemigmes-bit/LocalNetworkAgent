import sys
sys.path.insert(0, r'c:\Users\Usuario\LocalNetworkAgent\english-tutor')

from config import load_config
from providers import make_client, chat, parse_json
import json

cfg = load_config()
client = make_client(cfg)

SYSTEM = """You are the intent router for a Windows desktop assistant named Emma.
Decide whether the user's message is a SYSTEM COMMAND (control the computer or trusted home network) or normal English-practice conversation.
Return ONLY valid JSON with this exact shape:
{"command": true, "action": "launch", "target": "brave", "confidence": 0.9}

Allowed actions:
- "launch": open a program/application
- "close": close a running application
- "network_status": show status of trusted home devices
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

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "abre brave hazlo ya"}
]

from providers import make_client, chat, parse_json
from config import load_config

cfg = load_config()
client = make_client(cfg)

raw = chat(client, cfg, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "abre brave hazlo ya"}], temperature=0.0, json_mode=True)
print('Raw response:', repr(raw))

data = parse_json(raw) or {}
print('Parsed:', json.dumps(data, indent=2, ensure_ascii=False))