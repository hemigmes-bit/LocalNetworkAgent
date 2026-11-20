import sys
import os

# Add path FIRST
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

print("=== BEFORE IMPORT ===")
print("sys.path[0]:", sys.path[0])
print("tts_kokoro in sys.modules:", "tts_kokoro" in sys.modules)

import tts_kokoro
print("=== AFTER IMPORT ===")
print("Module file:", tts_kokoro.__file__)

with open(tts_kokoro.__file__, 'r') as f:
    content = f.read()
    print("Has voices-v1.0.bin:", 'voices-v1.0.bin' in content)
    print("Has voices.json:", 'voices.json' in content)

from tts_kokoro import KokoroTTS
print("Imported KokoroTTS")

print("Creating KokoroTTS...")
try:
    k = KokoroTTS()
    print("SUCCESS!")
except Exception as e:
    print("ERROR:", e)