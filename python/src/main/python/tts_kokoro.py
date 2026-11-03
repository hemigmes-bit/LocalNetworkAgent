"""Wrapper for Kokoro TTS."""
import numpy as np
import time
import os
from kokoro_onnx import Kokoro

class KokoroTTS:
    def __init__(self, model_path: str = None, voices_path: str = None):
        model_path = model_path or os.getenv("KOKORO_MODEL", "kokoro-v1.0.onnx")
        voices_path = voices_path or os.getenv("KOKORO_VOICES", "voices.json")
        
        print(f"🔄 Cargando Kokoro TTS...")
        self.kokoro = Kokoro(model_path, voices_path)
        print("✅ Kokoro TTS cargado")
        
        # Voces disponibles
        self.voices = {
            "es": "ef_dora",
            "en": "af_bella",
            "es_male": "em_alex",
            "en_male": "am_michael"
        }
    
    def synthesize(self, text: str, lang: str = "es") -> np.ndarray:
        start = time.perf_counter()
        voice = self.voices.get(lang, self.voices["es"])
        audio, _ = self.kokoro.create(text, voice=voice, speed=1.0)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"   ⏱️ TTS (Kokoro): {elapsed:.0f}ms - {len(audio)} samples")
        return audio
    
    def play(self, audio: np.ndarray, sample_rate: int = 24000):
        import sounddevice as sd
        sd.play(audio, sample_rate)
        sd.wait()