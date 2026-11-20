import os
base = r"C:\Users\Usuario\LocalNetworkAgent"
import sys
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")
import tts_kokoro
import os
print('base:', base)
print('os.path.join:', os.path.join(base, 'voices-v1.0.bin'))
print('exists:', os.path.exists(os.path.join(base, 'voices-v1.0.bin')))
print('getenv:', os.getenv('KOKORO_VOICES'))
print('getenv with default:', os.getenv('KOKORO_VOICES', os.path.join(base, 'voices-v1.0.bin')))