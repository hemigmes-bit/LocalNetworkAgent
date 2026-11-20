import sounddevice as sd
import numpy as np

print("Testing all input devices:")
for i, dev in enumerate(sd.query_devices()):
    if dev['max_input_channels'] > 0:
        try:
            rec = sd.rec(int(16000*2), samplerate=16000, channels=1, device=dev['index'])
            sd.wait()
            rms = np.sqrt(np.mean(rec**2))
            print(f'Device {dev["index"]}: {dev["name"]} - RMS: {rms:.6f}')
        except Exception as e:
            print(f'Device {dev["index"]}: {dev["name"]} - ERROR: {e}')