"""Wrapper for Kokoro TTS."""
import numpy as np
import time
import os
from kokoro_onnx import Kokoro

class KokoroTTS:
    def __init__(self, model_path: str = None, voices_path: str = None, output_device: int = None):
        base = r"C:\Users\Usuario\LocalNetworkAgent"
        model_path = model_path or os.getenv("KOKORO_MODEL", os.path.join(base, "kokoro-v1.0.onnx"))
        voices_path = voices_path or os.getenv("KOKORO_VOICES", os.path.join(base, "voices-v1.0.bin"))
        
        print(f"[LOAD] Cargando Kokoro TTS...")
        print(f"  Model path: {model_path}")
        print(f"  Voices path: {voices_path}")
        print(f"  Model exists: {os.path.exists(model_path)}")
        print(f"  Voices exists: {os.path.exists(voices_path)}")
        self.kokoro = Kokoro(model_path, voices_path)
        print("[OK] Kokoro TTS cargado")
        
        # Detectar dispositivo de auriculares si no se especifica
        if output_device is None:
            output_device = self._find_headphones_device()
        self.output_device = output_device
        print(f"  Output device: {output_device}")
        
        # Voces disponibles
        self.voices = {
            "es": "ef_dora",
            "en": "af_bella",
            "es_male": "em_alex",
            "en_male": "am_michael"
        }
    
    def _find_headphones_device(self) -> int:
        """Detectar dispositivo de auriculares automáticamente."""
        import sounddevice as sd
        try:
            # Usar dispositivo por defecto (más confiable)
            default_out = sd.default.device[1]
            print(f"  Usando dispositivo por defecto: {default_out}")
            return default_out
        except Exception as e:
            print(f"  Error detectando auriculares: {e}, usando default")
            return sd.default.device[1]
    
    def synthesize(self, text: str, lang: str = "es") -> np.ndarray:
        start = time.perf_counter()
        voice = self.voices.get(lang, self.voices["es"])
        audio, _ = self.kokoro.create(text, voice=voice, speed=1.0)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"   [TTS] Kokoro: {elapsed:.0f}ms - {len(audio)} samples")
        return audio
    
    def play(self, audio: np.ndarray, sample_rate: int = 24000):
        import sounddevice as sd
        sd.play(audio, sample_rate, device=self.output_device)
        sd.wait()