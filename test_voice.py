import sys
import os
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

print("HABLA AHORA por 3 segundos...")
rec = sd.rec(int(16000*3), samplerate=16000, channels=1, device=1)
sd.wait()
rms = np.sqrt(np.mean(rec**2))
print(f'RMS: {rms:.6f}')
if rms > 0.001:
    print('MICRÓFONO OK - listo para la prueba')
else:
    print('MICRÓFONO: sin señal detectada')
"