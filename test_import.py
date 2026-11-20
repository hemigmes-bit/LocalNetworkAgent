import sys
import os

# Force reimport of tts_kokoro with debug
if 'tts_kokoro' in sys.modules:
    del sys.modules['tts_kokoro']
if 'voice_loop' in sys.modules:
    del sys.modules['voice_loop']

sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

# Check what's in the module before import
import tts_kokoro
with open(tts_kokoro.__file__, 'r') as f:
    content = f.read()
    idx = content.find('voices-v1.0.bin')
    print(f'Source has voices-v1.0.bin: {idx >= 0}')
    idx = content.find('voices.json')
    print(f'Source has voices.json: {idx >= 0}')

# Now import the actual module
import importlib
importlib.reload(tts_kokoro)

from tts_kokoro import KokoroTTS

# Test instantiation
print("Creating KokoroTTS...")
k = KokoroTTS()
print("SUCCESS!")