import sys
import os

# Change to project root
os.chdir(r"C:\Users\Usuario\LocalNetworkAgent")

# Insert path first
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

# Monkey-patch tts_kokoro BEFORE any other imports
import tts_kokoro

def debug_init(self, model_path=None, voices_path=None):
    base = r"C:\Users\Usuario\LocalNetworkAgent"
    model_path = model_path or os.getenv("KOKORO_MODEL", os.path.join(base, "kokoro-v1.0.onnx"))
    voices_path = voices_path or os.getenv("KOKORO_VOICES", os.path.join(base, "voices-v1.0.bin"))
    print(f"[DEBUG] Model path: {model_path}")
    print(f"[DEBUG] Voices path: {voices_path}")
    print(f"[DEBUG] Model exists: {os.path.exists(model_path)}")
    print(f"[DEBUG] Voices exists: {os.path.exists(voices_path)}")
    from kokoro_onnx import Kokoro
    self.kokoro = Kokoro(model_path, voices_path)
    print("[OK] Kokoro TTS cargado")
    self.voices = {
        "es": "ef_dora",
        "en": "af_bella",
        "es_male": "em_alex",
        "en_male": "am_michael"
    }

tts_kokoro.KokoroTTS.__init__ = debug_init
print("Patched tts_kokoro")

# Now import the rest
from stt_faster_whisper import FasterWhisperSTT
from llm_openrouter import OpenRouterLLM

print("Imports done, running voice_loop...")

# Now run the actual script
exec(open(r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python\voice_loop.py").read())