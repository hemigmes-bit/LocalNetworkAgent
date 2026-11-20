import sys
sys.path.insert(0, r'c:\Users\Usuario\LocalNetworkAgent\english-tutor')

from config import load_config, DB_PATH
from providers import make_client
from tutor import Tutor
from db import Store

cfg = load_config()
client = make_client(cfg)
store = Store(DB_PATH)
tutor = Tutor(store, client, cfg, store.start_session('free'))

tests = [
    'abre brave hazlo ya',
    'busca en internet que es la inteligencia artificial',
    'que es la inteligencia artificial',
    'cierra chrome',
]

for t in tests:
    result = tutor.turn(t)
    print('Input:', repr(t))
    print('Reply:', result['reply'][:100])
    print('Language:', result.get('language'))
    print('---')