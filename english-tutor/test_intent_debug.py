import sys
sys.path.insert(0, r'c:\Users\Usuario\LocalNetworkAgent\english-tutor')

from config import load_config
from providers import make_client, chat, parse_json
import intent

cfg = load_config()
client = make_client(cfg)

SYSTEM = intent.SYSTEM

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "abre brave hazlo ya"}
]

from providers import chat, parse_json
from config import load_config

cfg = load_config()
client = make_client(cfg)

raw = chat(client, cfg, messages, temperature=0.0, json_mode=True)
print('Raw response:', repr(raw))

data = parse_json(raw) or {}
print('Parsed:', data)